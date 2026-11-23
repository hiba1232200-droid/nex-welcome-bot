import os
import json
from http.server import BaseHTTPRequestHandler
import urllib.request

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            update = json.loads(body.decode('utf-8'))
            
            if "chat_member" in update:
                chat_member = update["chat_member"]
                old_status = chat_member["old_chat_member"]["status"]
                new_status = chat_member["new_chat_member"]["status"]
                user = chat_member["new_chat_member"]["user"]

                if old_status in ["left", "kicked"] and new_status == "member" and not user.get("is_bot", False):
                    chat_id = chat_member["chat"]["id"]
                    first_name = user.get("first_name", "عضو").replace("<", "&lt;").replace(">", "&gt;")
                    mention = f'<a href="tg://user?id={user["id"]}">{first_name}</a>'

                    text = (
                        f"أهلاً وسهلاً بك يا {mention} في <b>𓆩NEX DEV AI𓆪</b>! 💻🤖\n"
                        f"نورت مجتمع المطورين وصناع حلول الذكاء الاصطناعي. سعيدون جداً بانضمامك إلينا! ⚡"
                    )

                    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                    payload = json.dumps({
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML"
                    }).encode('utf-8')

                    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
                    urllib.request.urlopen(req)
        except Exception:
            pass

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"NEX DEV AI Welcome Bot is running!")
