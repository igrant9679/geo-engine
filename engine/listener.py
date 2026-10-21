"""Always-on process: your Telegram control panel + client replies from Telegram, Teams and email.

python listener.py

Your private chat with the bot (TELEGRAM_ADMIN_ID):
  buttons on review / draft-question / report messages
  /queue    tasks waiting for your review      /status   task counts per client
  /run acme start a run for one client now     /help
In a client's Telegram group (you must be the one sending it):
  /link acme   connect this group to client 'acme'
"""
import subprocess
import sys
import time

import comms
import runner
import telegram_api as tg
from common import ENGINE, all_clients, client_cfg, db, env, kv_get, kv_set, log, now, settings

L = log("listener")
ADMIN = int(env("TELEGRAM_ADMIN_ID", "0") or 0)
awaiting = {}  # admin is typing feedback for: {"changes": task_id} or {"reject": task_id}


def handle_callback(cb):
    tg.call("answerCallbackQuery", callback_query_id=cb["id"], text="Working…")
    if cb["from"]["id"] != ADMIN:
        return
    action, arg = cb["data"].split(":", 1)
    msg = cb["message"]
    tg.clear_buttons(msg["chat"]["id"], msg["message_id"])
    try:
        if action == "approve":
            url = runner.approve(int(arg))
            tg.send(ADMIN, f"✅ #{arg} shipped. {url or ''}")
        elif action == "reject":
            awaiting.clear()
            awaiting["reject"] = int(arg)
            tg.send(ADMIN, f"Why reject #{arg}? (one line, or /skip)")
        elif action == "changes":
            awaiting.clear()
            awaiting["changes"] = int(arg)
            tg.send(ADMIN, f"What should change in #{arg}? Send your notes as one message.")
        elif action == "sendq":
            comms.send_question(int(arg))
            tg.send(ADMIN, f"📤 Q{arg} sent.")
        elif action == "dropq":
            comms.drop_question(int(arg))
            tg.send(ADMIN, f"🗑 Q{arg} dropped; the task will continue without it.")
        elif action == "sendreport":
            cfg = client_cfg(arg)
            con = db()
            comms.tell_client(cfg, kv_get(con, f"pending_report:{arg}", "Your weekly report is ready."))
            tg.send(ADMIN, f"📊 Report sent to {cfg['name']}.")
    except Exception as e:
        L.exception("callback %s failed", cb["data"])
        tg.send(ADMIN, f"⚠️ {action} {arg} failed: {str(e)[:500]}")


def admin_command(text):
    con = db()
    if "changes" in awaiting and not text.startswith("/"):
        tid = awaiting.pop("changes")
        runner.request_changes(tid, text)
        return tg.send(ADMIN, f"Noted. #{tid} will be revised on the next run.")
    if "reject" in awaiting:
        tid = awaiting.pop("reject")
        runner.reject(tid, "" if text == "/skip" else text)
        return tg.send(ADMIN, f"❌ #{tid} rejected.")
    if text.startswith("/queue"):
        rows = con.execute("SELECT * FROM tasks WHERE status='review' ORDER BY client, id").fetchall()
        if not rows:
            return tg.send(ADMIN, "Nothing waiting for review.")
        for t in rows[:15]:
            comms.notify_review(client_cfg(t["client"]), t, (t["result"] or "")[:600])
    elif text.startswith("/status"):
        lines = []
        for c in all_clients():
            counts = dict(con.execute("SELECT status, COUNT(*) FROM tasks WHERE client=? GROUP BY status", (c["slug"],)).fetchall())
            openq = con.execute("SELECT COUNT(*) FROM questions WHERE client=? AND status='open'", (c["slug"],)).fetchone()[0]
            lines.append(f"{c['name']}: " + ", ".join(f"{k} {v}" for k, v in counts.items()) + f" | open questions {openq}")
        tg.send(ADMIN, "\n".join(lines) or "No clients yet.")
    elif text.startswith("/run"):
        parts = text.split()
        args = [sys.executable, str(ENGINE / "runner.py")] + (["--client", parts[1]] if len(parts) > 1 else [])
        subprocess.Popen(args, cwd=ENGINE)
        tg.send(ADMIN, f"▶️ Started: {' '.join(parts[1:]) or 'all clients'}")
    else:
        tg.send(ADMIN, __doc__)


def handle_message(m):
    chat, user = m["chat"], m.get("from", {})
    text = m.get("text") or m.get("caption") or ""
    con = db()
    if chat["type"] == "private":
        if user.get("id") == ADMIN:
            admin_command(text)
        return
    if text.startswith("/link"):
        if user.get("id") != ADMIN or len(text.split()) < 2:
            return
        slug = text.split()[1]
        cfg = client_cfg(slug)  # raises if the client doesn't exist
        kv_set(con, f"tg_chat:{slug}", chat["id"])
        kv_set(con, f"tg_client:{chat['id']}", slug)
        tg.send(chat["id"], f"Connected to {cfg['name']}. Questions and updates will be posted here.")
        return
    slug = kv_get(con, f"tg_client:{chat['id']}")
    if not slug or user.get("is_bot"):
        return
    reply_to = (m.get("reply_to_message") or {}).get("message_id")
    if reply_to:
        q = con.execute("SELECT id FROM questions WHERE client=? AND channel='telegram' AND status='open' "
                        "AND json_extract(external_ref, '$.message_id')=?", (slug, reply_to)).fetchone()
        if q:
            comms.record_answer(q["id"], text, user.get("first_name", "client"))
            tg.send(chat["id"], "Thanks, got it.", reply_to=m["message_id"])
            return
    con.execute("INSERT INTO inbox(client,channel,author,text,received_at) VALUES (?,?,?,?,?)",
                (slug, "telegram", user.get("first_name", "?"), text, now()))
    con.commit()
    comms.notify_admin(f"💬 {client_cfg(slug)['name']} ({user.get('first_name', '?')}): {text[:800]}")


def main():
    con = db()
    offset = int(kv_get(con, "tg_offset", "0") or 0)
    last_poll = 0.0
    use_tg = bool(env("TELEGRAM_BOT_TOKEN"))
    L.info("listener started (telegram=%s)", use_tg)
    while True:
        try:
            if use_tg:
                for u in tg.updates(offset):
                    offset = u["update_id"] + 1
                    kv_set(con, "tg_offset", offset)
                    try:
                        if "callback_query" in u:
                            handle_callback(u["callback_query"])
                        elif "message" in u:
                            handle_message(u["message"])
                    except Exception:
                        L.exception("update %s failed", u.get("update_id"))
            else:
                time.sleep(30)
            if time.time() - last_poll > settings()["comms"]["poll_seconds"]:
                comms.poll_external()
                last_poll = time.time()
        except Exception:
            L.exception("listener loop error")
            time.sleep(15)


if __name__ == "__main__":
    main()
