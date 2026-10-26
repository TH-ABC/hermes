"""
Nhờ Muse viết / sửa code qua REST API, chạy được trong cmd.

  # Viết code mới -> lưu ra file txt
  python tools/muse_code.py new "Viết hàm Python đọc CSV và tính tổng cột price" -o ketqua.txt

  # Đọc file có sẵn + yêu cầu sửa -> ghi ra main.py.muse (file gốc không đổi)
  python tools/muse_code.py edit main.py "Thêm try/except và type hints"

  # Ghi đè thẳng file gốc (tự backup thành main.py.bak)
  python tools/muse_code.py edit main.py "Đổi sang async" --inplace

  # Đọc nhiều file làm ngữ cảnh
  python tools/muse_code.py edit main.py utils.py "Gộp hàm trùng lặp" --inplace

Biến môi trường: MUSE_BASE_URL (mặc định http://127.0.0.1:8770), MUSE_API_KEY.
Trong cmd: set MUSE_BASE_URL=http://100.126.145.3:8770
"""

import argparse
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from client import muse_api  # noqa: E402

CODE_BLOCK = re.compile(r"```[\w+-]*\n(.*?)```", re.S)


def ask(prompt: str) -> str:
    res = muse_api.generate(prompt, timeout_s=240)
    if not res.get("ok"):
        sys.exit(f"Lỗi: {res.get('error') or res.get('content')}")
    return res.get("content", "")


def extract_code(text: str) -> str:
    blocks = CODE_BLOCK.findall(text)
    return max(blocks, key=len).rstrip() + "\n" if blocks else text.strip() + "\n"


def read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def cmd_new(args) -> None:
    reply = ask(args.instruction + "\n\nTrả lời bằng một khối code duy nhất.")
    write(args.output, reply if args.raw else extract_code(reply))
    print(f"Đã lưu: {args.output}")


def cmd_edit(args) -> None:
    *paths, instruction = args.items
    if not paths:
        sys.exit("Cần ít nhất một file và một yêu cầu sửa.")
    target = paths[0]
    context = "\n\n".join(f"### File: {p}\n```\n{read(p)}\n```" for p in paths)
    prompt = (
        f"{context}\n\nYêu cầu: {instruction}\n\n"
        f"Trả về TOÀN BỘ nội dung mới của file {target} trong một khối code duy nhất, "
        "không rút gọn, không giải thích bên ngoài khối code."
    )
    new_code = extract_code(ask(prompt))
    if args.inplace:
        shutil.copyfile(target, target + ".bak")
        write(target, new_code)
        print(f"Đã sửa {target} (backup: {target}.bak)")
    else:
        write(target + ".muse", new_code)
        print(f"Đã lưu bản sửa: {target}.muse  (so sánh: fc {target} {target}.muse)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="viết code mới")
    p_new.add_argument("instruction")
    p_new.add_argument("-o", "--output", default="muse_output.txt")
    p_new.add_argument("--raw", action="store_true", help="lưu nguyên câu trả lời, không tách khối code")
    p_new.set_defaults(func=cmd_new)

    p_edit = sub.add_parser("edit", help="đọc file và sửa theo yêu cầu (file đầu là file được sửa)")
    p_edit.add_argument("items", nargs="+", help="file1 [file2 ...] \"yêu cầu\"")
    p_edit.add_argument("--inplace", action="store_true")
    p_edit.set_defaults(func=cmd_edit)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
