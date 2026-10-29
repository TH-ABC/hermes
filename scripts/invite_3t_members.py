import json
import urllib.request

group_id = "g:3385924780938036028"
members = ["3610362721214822619", "3622758563394626695", "6867397343268061836"]

for m in members:
    body = json.dumps({"group_id": group_id, "user_id": m}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:3050/invite-to-group", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"Invited {m}:", resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Error inviting {m}:", e)

# Send message to 3TGLOBAL - TIMELESS (g:6475407106699187228) with the invite link
link_msg = (
    "Dạ Sếp Hoàng vừa chỉ đạo khởi tạo nhóm mới 'Ae 3T' dành riêng cho anh em 3TGLOBAL!\n\n"
    "👉 Link tham gia nhóm 'Ae 3T': https://zalo.me/g/gmiojfezjqisejazxkoy\n\n"
    "Kính mời anh em nhấp vào link để tham gia nhóm mới ngay ạ! 🤝🚀"
)

msg_body = json.dumps({"chat_id": "g:6475407106699187228", "text": link_msg}).encode("utf-8")
req_msg = urllib.request.Request("http://127.0.0.1:3050/send", data=msg_body, headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req_msg, timeout=5) as resp:
        print("Sent link message to 3TGLOBAL - TIMELESS:", resp.read().decode('utf-8'))
except Exception as e:
    print("Error sending link message:", e)
