"""One interface for talking to clients (Telegram, Teams, email) and to you (Telegram, else email).

Client channel = the first entry of [comms] channels in client.toml.
With [comms] hold_for_review = true (default), every client-bound message waits for your Send button.
"""
import html
import json
import re

import telegram_api as tg
from common import client_cfg, db, env, kv_get, log, now, settings

L = log("comms")
APPROVED = re.compile(r"^\s*(approved?|yes|yep|looks good|lgtm|ok(ay)?|go ahead|ship it)\b", re.I)


def _html(text):
    return "<p>" + html.escape(text).replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"


def _strip_html(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


def _primary(cfg):
    return cfg.get("comms", {}).get("channels", ["email"])[0]


def _deliver(cfg, text, qid=None):
    """Send a message on the client's primary channel. Returns (channel, external_ref)."""
    c, ch = cfg.get("comms", {}), _primary(cfg)
    first_line = text.strip().splitlines()[0][:80]
    if ch == "telegram":
        chat = kv_get(db(), f"tg_chat:{cfg['slug']}")
        if not chat:
            raise RuntimeError(f"No Telegram group linked for {cfg['slug']}. In the client's group, send: /link {cfg['slug']}")
        suffix = "\n\n↩️ Reply to this message to answer." if qid else ""
        return ch, {"chat_id": int(chat), "message_id": tg.send(int(chat), text + suffix)}
    import msgraph
    if ch == "teams":
        suffix = "<p><i>Reply in this thread to answer.</i></p>" if qid else ""
        mid = msgraph.teams_post(c["teams_team_id"], c["teams_channel_id"], _html(text) + suffix, subject=first_line)
        return ch, {"team": c["teams_team_id"], "channel": c["teams_channel_id"], "message_id": mid}
    if ch == "email":
        subject = (f"[Q{qid}] " if qid else "") + f"{cfg['name']}: {first_line}"
        suffix = "<p><i>Just reply to this email to answer.</i></p>" if qid else ""
        return ch, {"conversation_id": msgraph.mail_send(c["emails"], subject, _html(text) + suffix)}
    raise RuntimeError(f"unknown channel {ch}")


def _hold():
    return settings()["comms"].get("hold_for_review", True)


# ---------- to you ----------

def notify_admin(text, buttons=None):
    L.info("ADMIN: %s", text.replace("\n", " | ")[:300])
    admin = env("TELEGRAM_ADMIN_ID")
    try:
        if admin and env("TELEGRAM_BOT_TOKEN"):
            return tg.send(int(admin), text, buttons)
        if env("ADMIN_EMAIL"):
            import msgraph
            msgraph.mail_send([env("ADMIN_EMAIL")], "GEO engine: " + text.splitlines()[0][:80], _html(text))
    except Exception as e:
        L.warning("could not notify admin: %s", e)


def notify_review(cfg, task, detail=""):
    text = (f"🔎 Review: {cfg['name']} #{task['id']} ({task['skill']})\n{task['title']}\n"
            f"{task['preview_url'] or ''}\n\n{detail[:1800]}")
    notify_admin(text, [[("✅ Approve & ship", f"approve:{task['id']}"), ("❌ Reject", f"reject:{task['id']}")],
                        [("✏️ Request changes", f"changes:{task['id']}")]])


# ---------- to clients ----------

def ask(cfg, task_id, text, kind="question"):
    con = db()
    open_n = con.execute("SELECT COUNT(*) FROM questions WHERE task_id=? AND status IN ('draft','open')", (task_id,)).fetchone()[0]
    if kind == "question" and open_n >= settings()["comms"]["max_questions_per_task"]:
        raise SystemExit("Too many open questions on this task already; proceed without this fact or stop.")
    cur = con.execute("INSERT INTO questions(client,task_id,kind,channel,text,asked_at,status) VALUES (?,?,?,?,?,?,?)",
                      (cfg["slug"], task_id, kind, _primary(cfg), text, now(), "draft"))
    con.commit()
    qid = cur.lastrowid
    if _hold():
        notify_admin(f"📝 Draft {kind} for {cfg['name']} (task #{task_id}) via {_primary(cfg)}:\n\n{text}",
                     [[("📤 Send", f"sendq:{qid}"), ("🗑 Drop", f"dropq:{qid}")]])
    else:
        send_question(qid)
    return qid


def send_question(qid):
    con = db()
    q = con.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    cfg = client_cfg(q["client"])
    channel, ref = _deliver(cfg, q["text"], qid)
    con.execute("UPDATE questions SET channel=?, external_ref=?, asked_at=?, status='open' WHERE id=?",
                (channel, json.dumps(ref), now(), qid))
    con.commit()


def drop_question(qid):
    """You decided the client should not be asked; the task resumes and must proceed without it."""
    con = db()
    con.execute("UPDATE questions SET status='answered', answer=?, answered_by='reviewer', answered_at=? WHERE id=?",
                ("(Not asked. Proceed without this fact: leave the claim out or keep it general.)", now(), qid))
    con.commit()


def tell_client(cfg, text):
    """Non-question message (shipped notice, report link)."""
    try:
        _deliver(cfg, text)
    except Exception as e:
        notify_admin(f"⚠️ Could not message {cfg['name']}: {e}")


def request_client_approval(cfg, task, files):
    """Put the draft in a Google Doc the client can comment on, and ask them to approve it."""
    import gdocs
    parts = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        parts.append(text if f.suffix in (".html", ".htm") else gdocs.md_to_html(text))
    url = gdocs.create_doc(db(), cfg, "preview", f"Preview - {task['title'][:80]}", "<hr>".join(parts), role="commenter")
    ask(cfg, task["id"], f"Before we publish \"{task['title']}\", please review:\n{url}\n\n"
                         "Reply \"approved\", or tell us what to change (comments in the doc work too).", kind="approval")


def record_answer(qid, answer, by):
    con = db()
    q = con.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    if not q or q["status"] != "open":
        return
    cfg = client_cfg(q["client"])
    if q["kind"] == "approval":
        if APPROVED.match(answer):
            con.execute("UPDATE questions SET status='closed', answer=?, answered_by=?, answered_at=? WHERE id=?",
                        (answer, by, now(), qid))
            con.commit()
            notify_admin(f"👍 {cfg['name']} approved task #{q['task_id']}. It's yours to ship.",
                         [[("✅ Approve & ship", f"approve:{q['task_id']}")]])
        else:
            con.execute("UPDATE questions SET status='closed', answer=?, answered_by=?, answered_at=? WHERE id=?",
                        (answer, by, now(), qid))
            con.commit()
            import runner
            runner.request_changes(q["task_id"], f"Client feedback: {answer}")
            notify_admin(f"✏️ {cfg['name']} asked for changes on #{q['task_id']}:\n{answer[:800]}\nIt will be revised next run.")
        return
    con.execute("UPDATE questions SET status='answered', answer=?, answered_by=?, answered_at=? WHERE id=?",
                (answer, by, now(), qid))
    con.commit()
    notify_admin(f"💬 {cfg['name']} answered Q{qid} (task #{q['task_id']}):\n{answer[:800]}")


def poll_external():
    """Check Teams threads and email conversations for replies to open questions."""
    con = db()
    for q in con.execute("SELECT * FROM questions WHERE status='open' AND channel IN ('teams','email')").fetchall():
        ref = json.loads(q["external_ref"] or "{}")
        try:
            import msgraph
            if q["channel"] == "teams":
                replies = msgraph.teams_replies(ref["team"], ref["channel"], ref["message_id"])
                replies = [{"author": r["author"], "text": _strip_html(r["html"])} for r in replies]
            else:
                replies = msgraph.mail_replies(ref["conversation_id"])
        except Exception as e:
            L.warning("poll Q%s failed: %s", q["id"], e)
            continue
        if replies:
            record_answer(q["id"], "\n\n".join(r["text"] for r in replies), replies[0]["author"])
