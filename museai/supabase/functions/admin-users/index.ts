// Admin-only user management. Staff accounts are created here (no public signup).
import { createClient } from "npm:@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const token = (req.headers.get("Authorization") ?? "").replace(/^Bearer /, "");
  const { data: u } = await admin.auth.getUser(token);
  if (!u?.user) return json({ error: "unauthorized" }, 401);
  const { data: me } = await admin.from("profiles").select("role, disabled").eq("id", u.user.id).single();
  if (!me || me.role !== "admin" || me.disabled) return json({ error: "forbidden" }, 403);

  let b: any;
  try { b = await req.json(); } catch { return json({ error: "invalid json" }, 400); }

  switch (b.action) {
    case "list": {
      const { data, error } = await admin.from("profiles").select("*").order("created_at");
      return error ? json({ error: error.message }, 400) : json({ users: data });
    }
    case "create": {
      const email = String(b.email ?? "").trim().toLowerCase();
      const password = String(b.password ?? "");
      if (!email || password.length < 8) return json({ error: "Cần email và mật khẩu tối thiểu 8 ký tự" }, 400);
      const { data, error } = await admin.auth.admin.createUser({ email, password, email_confirm: true });
      if (error) return json({ error: error.message }, 400);
      const { error: e2 } = await admin.from("profiles").insert({
        id: data.user.id, email, full_name: String(b.full_name ?? ""), role: "staff",
      });
      if (e2) { await admin.auth.admin.deleteUser(data.user.id); return json({ error: e2.message }, 400); }
      return json({ ok: true, id: data.user.id });
    }
    case "set_password": {
      if (String(b.password ?? "").length < 8) return json({ error: "Mật khẩu tối thiểu 8 ký tự" }, 400);
      const { error } = await admin.auth.admin.updateUserById(b.id, { password: b.password });
      return error ? json({ error: error.message }, 400) : json({ ok: true });
    }
    case "set_disabled": {
      if (b.id === u.user.id) return json({ error: "Không thể tự khóa tài khoản admin" }, 400);
      const { error } = await admin.auth.admin.updateUserById(b.id, { ban_duration: b.disabled ? "876000h" : "none" });
      if (error) return json({ error: error.message }, 400);
      await admin.from("profiles").update({ disabled: !!b.disabled }).eq("id", b.id);
      return json({ ok: true });
    }
    case "delete": {
      if (b.id === u.user.id) return json({ error: "Không thể tự xóa tài khoản admin" }, 400);
      const { error } = await admin.auth.admin.deleteUser(b.id);
      return error ? json({ error: error.message }, 400) : json({ ok: true });
    }
    case "export_user": {
      const { data: prof } = await admin.from("profiles").select("email, full_name").eq("id", b.id).single();
      if (!prof) return json({ error: "Không tìm thấy người dùng" }, 404);
      const { data: convs } = await admin.from("conversations").select("id, title, created_at").eq("user_id", b.id).order("created_at");
      const { data: msgs } = await admin.from("messages").select("conversation_id, role, content, attachments").eq("user_id", b.id).order("id");
      let md = `# Lịch sử chat — ${prof.full_name || prof.email}\n\n`;
      for (const c of convs ?? []) {
        md += `## ${c.title}\n_${c.created_at}_\n\n`;
        for (const m of (msgs ?? []).filter((x) => x.conversation_id === c.id)) {
          const att = (m.attachments ?? []).length ? ` _(đính kèm: ${m.attachments.map((a: any) => a.name).join(", ")})_` : "";
          md += `**${m.role === "user" ? "Người dùng" : "Agent 3T"}:** ${m.content}${att}\n\n`;
        }
      }
      return json({ md, name: String(prof.email).split("@")[0] });
    }
    case "impersonate": {
      // Admin "log in as": a one-time magic-link token for the target user; their password is never touched.
      if (b.id === u.user.id) return json({ error: "Đây là tài khoản của bạn" }, 400);
      const { data: prof } = await admin.from("profiles").select("email, disabled").eq("id", b.id).single();
      if (!prof || prof.disabled) return json({ error: "Tài khoản không tồn tại hoặc đã bị khóa" }, 404);
      const { data, error } = await admin.auth.admin.generateLink({ type: "magiclink", email: prof.email });
      if (error || !data?.properties?.hashed_token) return json({ error: error?.message ?? "Không tạo được phiên" }, 400);
      return json({ token_hash: data.properties.hashed_token, email: prof.email });
    }
    case "get_rules": {
      const { data } = await admin.from("a3t_settings").select("value").eq("key", "rules_md").maybeSingle();
      const { data: en } = await admin.from("a3t_settings").select("value").eq("key", "rules_enabled").maybeSingle();
      return json({ rules: data?.value ?? "", enabled: en?.value !== "false" });
    }
    case "set_rules": {
      if (typeof b.enabled === "boolean") {
        await admin.from("a3t_settings").upsert({ key: "rules_enabled", value: b.enabled ? "true" : "false" });
        if (b.rules === undefined) return json({ ok: true });
      }
      const v = String(b.rules ?? "");
      if (v.length > 60000) return json({ error: "File quy chuẩn quá dài (tối đa 60.000 ký tự)" }, 400);
      const { error } = await admin.from("a3t_settings").upsert({ key: "rules_md", value: v });
      return error ? json({ error: error.message }, 400) : json({ ok: true });
    }
    default:
      return json({ error: "unknown action" }, 400);
  }
});
