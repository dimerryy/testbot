import os
import logging
import requests
from flask import Flask, request, abort

# --- Config via environment ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # required
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "hook")  # set your own
AUTO_SET_WEBHOOK = os.environ.get("AUTO_SET_WEBHOOK", "true").lower() == "true"

if not BOT_TOKEN:
    raise RuntimeError("Please set BOT_TOKEN env var (from @BotFather).")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")  # Render sets this automatically

# --- Logging ---
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("bot")

app = Flask(__name__)

@app.get("/")
def health():
    # Health check for Render
    return "ok", 200

@app.post(f"/webhook/<secret>")
def telegram_webhook(secret: str):
    if secret != WEBHOOK_SECRET:
        abort(403)

    update = request.get_json(silent=True) or {}
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return ("no message", 200)

    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()

    if text.startswith("/start"):
        _ = requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": "hello"})

    return ("ok", 200)

def set_webhook_if_possible():
    """
    Set Telegram webhook using the public URL. Safe to call multiple times.
    """
    if not RENDER_EXTERNAL_URL:
        log.warning("RENDER_EXTERNAL_URL not set yet; skip setWebhook. You can set it later via /setwebhook.")
        return

    url = f"{RENDER_EXTERNAL_URL.rstrip('/')}/webhook/{WEBHOOK_SECRET}"
    try:
        r = requests.post(f"{API}/setWebhook", data={"url": url}, timeout=10)
        if r.ok and r.json().get("ok"):
            log.info("setWebhook ok -> %s", url)
        else:
            log.error("setWebhook failed: status=%s body=%s", r.status_code, r.text)
    except Exception as e:
        log.exception("setWebhook error: %s", e)

@app.get("/setwebhook")
def setwebhook_endpoint():
    """
    Optional manual trigger: visit https://<your-service>/setwebhook (not secret)
    Useful if the first boot ran before RENDER_EXTERNAL_URL was ready.
    """
    set_webhook_if_possible()
    return "setWebhook attempted (check logs).", 200

@app.before_first_request
def _startup():
    if AUTO_SET_WEBHOOK:
        set_webhook_if_possible()

if __name__ == "__main__":
    # Local dev only (Render will run via gunicorn)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
