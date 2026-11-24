import os
import json
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "")
VERCEL_TOKEN = os.environ.get("VERCEL_TOKEN", "")
VERCEL_PROJECT_ID = os.environ.get("VERCEL_PROJECT_ID", "")

DEFAULT_WELCOME = "أهلاً بك {user} في <b>𓆩NEX DEV AI𓆪</b>، نورت مجتمعنا البرمجي."
CURRENT_WELCOME = os.environ.get("WELCOME_TEXT", DEFAULT_WELCOME)

# حالة انتظار نص الترحيب الجديد من الأدمن (بسيطة ومباشرة)
WAITING_FOR_WELCOME = {}


def tg_request(method: str, payload: dict):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def update_vercel_env(new_text: str) -> bool:
    """تحديث متغير WELCOME_TEXT في Vercel ليبقى محفوظاً دائماً"""
    global CURRENT_WELCOME
    CURRENT_WELCOME = new_text

    if not VERCEL_TOKEN or not VERCEL_PROJECT_ID:
        return False

    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        # البحث عن المتغير الحالي لمعرفة ID الخاص به
        list_url = f"https://api.vercel.com/v9/projects/{VERCEL_PROJECT_ID}/env"
        req = urllib.request.Request(list_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            envs = json.loads(resp.read().decode("utf-8")).get("envs", [])

        existing_id = None
        for env in envs:
            if env.get("key") == "WELCOME_TEXT":
                existing_id = env.get("id")
                break

        if existing_id:
            patch_url = f"https://api.vercel.com/v9/projects/{VERCEL_PROJECT_ID}/env/{existing_id}"
            payload = json.dumps({"value": new_text}).encode("utf-8")
            p_req = urllib.request.Request(patch_url, data=payload, headers=headers, method="PATCH")
            urllib.request.urlopen(p_req, timeout=10)
        else:
            post_url = f"https://api.vercel.com/v10/projects/{VERCEL_PROJECT_ID}/env"
            payload = json.dumps({
                "key": "WELCOME_TEXT",
                "value": new_text,
                "type": "plain",
                "target": ["production", "preview", "development"]
            }).encode("utf-8")
            c_req = urllib.request.Request(post_url, data=payload, headers=headers, method="POST")
            urllib.request.urlopen(c_req, timeout=10)

        return True
    except Exception:
        return False


def send_admin_panel(chat_id: int, message_id: int = None):
    panel_text = (
        "🛠 <b>لوحة تحكم أدمن — 𓆩NEX DEV AI𓆪</b>\n\n"
        "📝 <b>رسالة الترحيب الحالية:</b>\n"
        f"<code>{CURRENT_WELCOME}</code>\n\n"
        "💡 استخدم <code>{user}</code> في المكان الذي تريد أن يظهر فيه منشن العضو الجديد."
    )
    keyboard = {
        "inline_keyboard": [
            [{"text": "✏️ تغيير رسالة الترحيب", "callback_data": "edit_welcome"}],
            [{"text": "👁 معاينة الرسالة", "callback_data": "preview_welcome"}],
            [{"text": "🔄 استعادة الافتراضية", "callback_data": "reset_welcome"}]
        ]
    }
    if message_id:
        tg_request("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": panel_text,
            "parse_mode": "HTML",
            "reply_markup": keyboard
        })
    else:
        tg_request("sendMessage", {
            "chat_id": chat_id,
            "text": panel_text,
            "parse_mode": "HTML",
            "reply_markup": keyboard
        })


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        global CURRENT_WELCOME
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            update = json.loads(body.decode("utf-8"))

            # 1) ترحيب بالأعضاء الجدد في المجموعة
            if "chat_member" in update:
                chat_member = update["chat_member"]
                old_status = chat_member["old_chat_member"]["status"]
                new_status = chat_member["new_chat_member"]["status"]
                user = chat_member["new_chat_member"]["user"]

                if old_status in ["left", "kicked"] and new_status == "member" and not user.get("is_bot", False):
                    chat_id = chat_member["chat"]["id"]
                    first_name = user.get("first_name", "عضو").replace("<", "&lt;").replace(">", "&gt;")
                    mention = f'<a href="tg://user?id={user["id"]}">{first_name}</a>'

                    final_text = CURRENT_WELCOME.replace("{user}", mention)
                    tg_request("sendMessage", {
                        "chat_id": chat_id,
                        "text": final_text,
                        "parse_mode": "HTML"
                    })

            # 2) الضغط على أزرار لوحة الأدمن
            elif "callback_query" in update:
                cq = update["callback_query"]
                cq_id = cq["id"]
                from_id = str(cq["from"]["id"])
                chat_id = cq["message"]["chat"]["id"]
                msg_id = cq["message"]["message_id"]
                data = cq.get("data", "")

                if from_id != ADMIN_ID:
                    tg_request("answerCallbackQuery", {
                        "callback_query_id": cq_id,
                        "text": "هذا القسم مخصص للأدمن فقط.",
                        "show_alert": True
                    })
                else:
                    if data == "edit_welcome":
                        WAITING_FOR_WELCOME[from_id] = True
                        tg_request("answerCallbackQuery", {"callback_query_id": cq_id})
                        tg_request("sendMessage", {
                            "chat_id": chat_id,
                            "text": (
                                "✍️ أرسل الآن نص رسالة الترحيب الجديد.\n"
                                "يمكنك كتابة <code>{user}</code> لعمل منشن للعضو الجديد، ويدعم تنسيق HTML مثل <code>&lt;b&gt;نص عريض&lt;/b&gt;</code>.\n"
                                "أرسل /cancel للإلغاء."
                            ),
                            "parse_mode": "HTML"
                        })

                    elif data == "preview_welcome":
                        tg_request("answerCallbackQuery", {"callback_query_id": cq_id})
                        sample_mention = f'<a href="tg://user?id={from_id}">مثال_عضو</a>'
                        preview = CURRENT_WELCOME.replace("{user}", sample_mention)
                        tg_request("sendMessage", {
                            "chat_id": chat_id,
                            "text": f"👁 <b>معاينة الترحيب:</b>\n\n{preview}",
                            "parse_mode": "HTML"
                        })

                    elif data == "reset_welcome":
                        saved = update_vercel_env(DEFAULT_WELCOME)
                        tg_request("answerCallbackQuery", {
                            "callback_query_id": cq_id,
                            "text": "تمت استعادة الرسالة الافتراضية"
                        })
                        send_admin_panel(chat_id, msg_id)

            # 3) رسائل الأدمن في الخاص لفتح اللوحة أو استقبال النص الجديد
            elif "message" in update:
                msg = update["message"]
                chat_id = msg["chat"]["id"]
                chat_type = msg["chat"].get("type", "")
                from_id = str(msg.get("from", {}).get("id", ""))
                text = msg.get("text", "")

                # فتح لوحة الأدمن من الخاص عبر /admin أو /start
                if chat_type == "private" and from_id == ADMIN_ID:
                    if WAITING_FOR_WELCOME.get(from_id):
                        WAITING_FOR_WELCOME[from_id] = False
                        if text.strip() == "/cancel":
                            tg_request("sendMessage", {"chat_id": chat_id, "text": "تم إلغاء التعديل."})
                            send_admin_panel(chat_id)
                        elif text.strip():
                            persisted = update_vercel_env(text.strip())
                            status_note = "✅ تم الحفظ وتحديث المتغير في Vercel." if persisted else "✅ تم تحديث الرسالة في الجلسة الحالية (أضف VERCEL_TOKEN و VERCEL_PROJECT_ID للحفظ الدائم)."
                            tg_request("sendMessage", {
                                "chat_id": chat_id,
                                "text": f"{status_note}\n\n<b>الرسالة الجديدة:</b>\n<code>{CURRENT_WELCOME}</code>",
                                "parse_mode": "HTML"
                            })
                            send_admin_panel(chat_id)
                    elif text.strip() in ["/admin", "/start"]:
                        send_admin_panel(chat_id)

        except Exception:
            pass

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"NEX DEV AI Welcome Bot is running!")
