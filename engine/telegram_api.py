"""Tiny Telegram Bot API client (free, no message-history limits)."""
import requests

from common import env


def call(method, http_timeout=40, **params):
    token = env("TELEGRAM_BOT_TOKEN", required=True)
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=http_timeout)
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(f"Telegram {method}: {j.get('description')}")
    return j["result"]


def send(chat_id, text, buttons=None, reply_to=None):
    """buttons: [[(label, callback_data), ...], ...]  -> returns the sent message_id"""
    params = {"chat_id": chat_id, "text": text[:4000], "link_preview_options": {"is_disabled": True}}
    if buttons:
        params["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]}
    if reply_to:
        params["reply_parameters"] = {"message_id": reply_to}
    return call("sendMessage", **params)["message_id"]


def updates(offset, wait=25):
    return call("getUpdates", http_timeout=wait + 15, offset=offset, timeout=wait,
                allowed_updates=["message", "callback_query"])


def clear_buttons(chat_id, message_id):
    try:
        call("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id, reply_markup={"inline_keyboard": []})
    except RuntimeError:
        pass
