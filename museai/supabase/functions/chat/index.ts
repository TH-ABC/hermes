// Authenticated proxy to the Agent 3T Global bridge on the VPS.
// The VPS URL and API key live in public.a3t_settings (service role only) and never reach the browser.
import { createClient } from "npm:@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const token = (req.headers.get("Authorization") ?? "").replace(/^Bearer /, "");
  const { data: u } = await db.auth.getUser(token);
  if (!u?.user) return json({ error: "unauthorized" }, 401);
  const uid = u.user.id;
  const { data: me } = await db.from("profiles").select("disabled").eq("id", uid).single();
  if (!me || me.disabled) return json({ error: "forbidden" }, 403);

  const { data: rows } = await db.from("a3t_settings").select("key, value");
  const cfg = Object.fromEntries((rows ?? []).map((r) => [r.key, r.value]));
  const base = (cfg.bridge_url ?? "").replace(/\/$/, "");
  if (!base) return json({ error: "Chưa cấu hình bridge_url" }, 500);
  const headers = { "X-API-Key": cfg.bridge_key ?? "" };

  // GET ?media=/media/xxx.mp4 -> stream a generated file (only paths under /media/).
  if (req.method === "GET") {
    const path = new URL(req.url).searchParams.get("media") ?? "";
    if (!/^\/media\/[\w.\-]+$/.test(path)) return json({ error: "bad path" }, 400);
    const r = await fetch(base + path, { headers });
    return new Response(r.body, {
      status: r.status,
      headers: { ...cors, "Content-Type": r.headers.get("Content-Type") ?? "application/octet-stream" },
    });
  }

  let b: any;
  try { b = await req.json(); } catch { return json({ error: "invalid json" }, 400); }
  const prompt = String(b.prompt ?? "").trim();
  const files: string[] = Array.isArray(b.files) ? b.files.slice(0, 6) : [];
  if (!files.every((x) => typeof x === "string" && x.startsWith("data:image/"))) return json({ error: "file không hợp lệ" }, 400);
  if (!prompt && !files.length) return json({ error: "prompt trống" }, 400);

  // Conversation must belong to the caller; otherwise start a new one.
  let convId: string | null = b.conversation_id ?? null;
  if (convId) {
    const { data: c } = await db.from("conversations").select("id").eq("id", convId).eq("user_id", uid).maybeSingle();
    if (!c) return json({ error: "conversation not found" }, 404);
  } else {
    const { data: c, error } = await db.from("conversations")
      .insert({ user_id: uid, title: (prompt || "Hình ảnh").slice(0, 60) }).select("id").single();
    if (error) return json({ error: error.message }, 500);
    convId = c.id;
  }
  await db.from("messages").insert({ conversation_id: convId, user_id: uid, role: "user", content: prompt || `[${files.length} ảnh đính kèm]` });

  let reply = "", media: string[] = [], ok = true;
  try {
    const r = await fetch(base + "/v1/chat", {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, files }),
      signal: AbortSignal.timeout(145_000),
    });
    const d = await r.json();
    ok = !!d.ok;
    reply = d.content ?? d.error ?? "";
    media = d.media ?? [];
  } catch (e) {
    ok = false;
    reply = "Không kết nối được tới hệ thống Agent: " + (e as Error).message;
  }
  await db.from("messages").insert({ conversation_id: convId, user_id: uid, role: "assistant", content: reply, media });
  await db.from("conversations").update({ updated_at: new Date().toISOString() }).eq("id", convId);
  return json({ ok, conversation_id: convId, content: reply, media });
});
