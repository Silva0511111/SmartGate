import os, threading
import requests

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def configured():
    return bool(TOKEN and CHAT_ID)

def _send(text, photo_path=None):
    base = f"https://api.telegram.org/bot{TOKEN}"
    try:
        if photo_path and os.path.exists(photo_path):
            with open(photo_path, "rb") as f:
                r = requests.post(f"{base}/sendPhoto",
                                  data={"chat_id": CHAT_ID, "caption": text},
                                  files={"photo": f}, timeout=15)
        else:
            r = requests.post(f"{base}/sendMessage",
                              data={"chat_id": CHAT_ID, "text": text}, timeout=15)
        if not r.ok:
            print("Telegram error:", r.status_code, r.text[:200])
        return r.ok
    except requests.RequestException as e:
        # the error text can contain the bot token, so mask it
        print("Telegram alert failed:", str(e).replace(TOKEN, "***"))
        return False

def send_alert(text, photo_path=None):
    """Runs in a background thread so the camera loop never freezes."""
    if not configured():
        return
    threading.Thread(target=_send, args=(text, photo_path), daemon=True).start()

if __name__ == "__main__":
    if not configured():
        print("Set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID first (see setup steps).")
    else:
        print("Sent!" if _send("Smart Gate test alert") else "Failed.")