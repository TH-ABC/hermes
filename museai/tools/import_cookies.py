#!/usr/bin/env python3
"""
Bulk-import Muse.ai cookies into cookies/<account>.json (Playwright format, chmod 600).

Accepted inputs (files or folders, mix freely):
  - Cookie-Editor / EditThisCookie / Playwright JSON export: [ {name, value, domain, ...}, ... ]  -> 1 account
  - Simple dict JSON: {"hatch_sess": "...", ...}                                                 -> 1 account
  - Multi-account JSON: {"acc01": [...] | {...}, "acc02": ...}  or  [[...], [...]]
  - .txt: one account per line, either "name=value; name2=value2" (a Cookie header)
          or "label<TAB>name=value; ..." / "label | name=value; ..."

Cookie values are never printed. Accounts without the session cookie are skipped,
duplicates (same session) are skipped.

  python tools/import_cookies.py exports/*.json accounts.txt --out cookies [--prefix acc] [--dry-run]
"""

import argparse
import hashlib
import json
import os
import re
import sys

SESSION_COOKIE = os.environ.get("MUSE_SESSION_COOKIE", "hatch_sess")
SAMESITE = {"no_restriction": "None", "none": "None", "lax": "Lax", "strict": "Strict"}


def normalize(raw) -> list:
    """Returns Playwright cookies for muse.ai from a list-of-dicts or a name->value dict."""
    if isinstance(raw, dict):
        raw = [{"name": k, "value": v} for k, v in raw.items() if isinstance(v, str)]
    out = []
    for c in raw:
        if not isinstance(c, dict) or "name" not in c or "value" not in c:
            continue
        domain = c.get("domain") or ".muse.ai"
        if "muse.ai" not in domain:
            continue
        ck = {"name": c["name"], "value": str(c["value"]), "domain": domain,
              "path": c.get("path") or "/", "secure": bool(c.get("secure", True))}
        if c.get("httpOnly") is not None:
            ck["httpOnly"] = bool(c["httpOnly"])
        exp = c.get("expires", c.get("expirationDate"))
        if isinstance(exp, (int, float)) and exp > 0:
            ck["expires"] = float(exp)
        ss = SAMESITE.get(str(c.get("sameSite", "")).lower())
        if ss:
            ck["sameSite"] = ss
            if ss == "None":
                ck["secure"] = True
        out.append(ck)
    return out


def parse_header(line: str) -> dict:
    jar = {}
    for part in line.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            if k.strip():
                jar[k.strip()] = v.strip()
    return jar


def is_cookie_list(x) -> bool:
    return isinstance(x, list) and all(isinstance(c, dict) and "name" in c for c in x) and len(x) > 0


def is_flat_dict(x) -> bool:
    return isinstance(x, dict) and x and all(isinstance(v, str) for v in x.values())


def read_source(path: str):
    """Yields (label or None, raw cookies) for every account found in one file."""
    base = os.path.splitext(os.path.basename(path))[0]
    if path.lower().endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if is_cookie_list(data) or is_flat_dict(data):
            yield base, data
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if is_cookie_list(item) or is_flat_dict(item):
                    yield f"{base}_{i+1}", item
        elif isinstance(data, dict):
            for label, item in data.items():
                if is_cookie_list(item) or is_flat_dict(item):
                    yield str(label), item
        return
    with open(path, "r", encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^([\w.-]+)\s*(?:\t|\|)\s*(.+)$", line)
            if m and "=" not in m.group(1):
                yield m.group(1), parse_header(m.group(2))
            else:
                yield f"{base}_{n}", parse_header(line)


def safe_label(s: str) -> str:
    return re.sub(r"[^\w.-]", "_", s).strip("._") or "acc"


def main():
    ap = argparse.ArgumentParser(description="Bulk-import Muse.ai cookies")
    ap.add_argument("inputs", nargs="+", help="cookie export files or folders")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cookies"))
    ap.add_argument("--prefix", default=None, help="name accounts <prefix>01, <prefix>02... instead of source labels")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = []
    for p in args.inputs:
        if os.path.isdir(p):
            files += [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.lower().endswith((".json", ".txt"))]
        else:
            files.append(p)

    os.makedirs(args.out, exist_ok=True)
    os.chmod(args.out, 0o700)
    seen = set()
    for fn in os.listdir(args.out):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(args.out, fn), "r", encoding="utf-8") as f:
                    for c in normalize(json.load(f)):
                        if c["name"] == SESSION_COOKIE:
                            seen.add(hashlib.sha256(c["value"].encode()).hexdigest())
            except Exception:
                pass
    existing = {fn[:-5] for fn in os.listdir(args.out) if fn.endswith(".json")}
    counter = len(existing)

    written = skipped = 0
    for path in files:
        try:
            sources = list(read_source(path))
        except Exception as e:
            print(f"[skip] {path}: unreadable ({e.__class__.__name__})")
            continue
        for label, raw in sources:
            cookies = normalize(raw)
            sess = next((c["value"] for c in cookies if c["name"] == SESSION_COOKIE), None)
            if not sess:
                print(f"[skip] {label}: no '{SESSION_COOKIE}' session cookie")
                skipped += 1
                continue
            digest = hashlib.sha256(sess.encode()).hexdigest()
            if digest in seen:
                print(f"[skip] {label}: duplicate session (already imported)")
                skipped += 1
                continue
            seen.add(digest)
            if args.prefix:
                counter += 1
                name = f"{args.prefix}{counter:02d}"
            else:
                name = safe_label(label)
            while name in existing:
                name += "_new"
            existing.add(name)
            dest = os.path.join(args.out, f"{name}.json")
            if not args.dry_run:
                fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, indent=1)
            print(f"[ok]   {name}: {len(cookies)} cookies{' (dry-run)' if args.dry_run else ''}")
            written += 1
    print(f"\nImported {written}, skipped {skipped} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
