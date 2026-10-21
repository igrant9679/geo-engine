"""Microsoft Graph for Teams channel messages and Outlook email, signed in as you (delegated).

One-time:   python msgraph.py login     (device-code sign-in; token is cached in data/)
Find IDs:   python msgraph.py teams     (lists your teams and channels with their IDs)
Test mail:  python msgraph.py testmail you@example.com
"""
import functools
import sys

import msal
import requests

from common import DATA, env

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["User.Read", "Team.ReadBasic.All", "Channel.ReadBasic.All", "ChannelMessage.Send",
          "ChannelMessage.Read.All", "Mail.ReadWrite", "Mail.Send"]
CACHE = DATA / "ms_token_cache.json"


def _app():
    cache = msal.SerializableTokenCache()
    if CACHE.exists():
        cache.deserialize(CACHE.read_text(encoding="utf-8"))
    app = msal.PublicClientApplication(
        env("MS_CLIENT_ID", required=True),
        authority=f"https://login.microsoftonline.com/{env('MS_TENANT_ID', required=True)}",
        token_cache=cache)
    return app, cache


def _save(cache):
    if cache.has_state_changed:
        DATA.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(cache.serialize(), encoding="utf-8")


def token():
    app, cache = _app()
    accounts = app.get_accounts()
    result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
    _save(cache)
    if not result or "access_token" not in result:
        raise RuntimeError("Microsoft sign-in needed: run `python msgraph.py login`")
    return result["access_token"]


def login():
    app, cache = _app()
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise SystemExit(f"Could not start sign-in: {flow}")
    print(flow["message"])
    result = app.acquire_token_by_device_flow(flow)
    _save(cache)
    print("Signed in as", result.get("id_token_claims", {}).get("preferred_username") if "access_token" in result else result)


def g(method, path, headers=None, **kw):
    h = {"Authorization": f"Bearer {token()}", **(headers or {})}
    r = requests.request(method, GRAPH + path, headers=h, timeout=60, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"Graph {method} {path}: {r.status_code} {r.text[:400]}")
    return r.json() if r.content else {}


@functools.cache
def me():
    m = g("GET", "/me", params={"$select": "id,mail,userPrincipalName,displayName"})
    m["address"] = (m.get("mail") or m["userPrincipalName"]).lower()
    return m


# ---------- Teams ----------

def teams_post(team_id, channel_id, html, subject=None):
    body = {"body": {"contentType": "html", "content": html}}
    if subject:
        body["subject"] = subject[:250]
    return g("POST", f"/teams/{team_id}/channels/{channel_id}/messages", json=body)["id"]


def teams_reply(team_id, channel_id, message_id, html):
    return g("POST", f"/teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies",
             json={"body": {"contentType": "html", "content": html}})["id"]


def teams_replies(team_id, channel_id, message_id):
    """Replies in the thread that are not from you: [{author, html, created}]"""
    out = []
    for r in g("GET", f"/teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies").get("value", []):
        user = (r.get("from") or {}).get("user") or {}
        if user.get("id") and user["id"] != me()["id"]:
            out.append({"author": user.get("displayName", "client"), "html": r["body"]["content"],
                        "created": r["createdDateTime"]})
    return sorted(out, key=lambda x: x["created"])


# ---------- Email ----------

def mail_send(to, subject, html, cc=None):
    """Sends from your mailbox; returns the conversationId used to find replies."""
    msg = g("POST", "/me/messages", json={
        "subject": subject, "body": {"contentType": "HTML", "content": html},
        "toRecipients": [{"emailAddress": {"address": a}} for a in to],
        "ccRecipients": [{"emailAddress": {"address": a}} for a in cc or []]})
    g("POST", f"/me/messages/{msg['id']}/send")
    return msg["conversationId"]


def mail_replies(conversation_id):
    """Messages in the conversation not sent by you: [{author, text, created}] (only the new part of each reply)."""
    res = g("GET", "/me/messages", headers={"Prefer": 'outlook.body-content-type="text"'},
            params={"$filter": f"conversationId eq '{conversation_id}'",
                    "$select": "from,uniqueBody,receivedDateTime,isDraft", "$top": "50"})
    out = []
    for m in res.get("value", []):
        sender = ((m.get("from") or {}).get("emailAddress") or {}).get("address", "").lower()
        if not m.get("isDraft") and sender and sender != me()["address"]:
            out.append({"author": sender, "text": m["uniqueBody"]["content"].strip(), "created": m["receivedDateTime"]})
    return sorted(out, key=lambda x: x["created"])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "login":
        login()
    elif cmd == "teams":
        for t in g("GET", "/me/joinedTeams").get("value", []):
            print(f"TEAM {t['displayName']}\n  teams_team_id = \"{t['id']}\"")
            for c in g("GET", f"/teams/{t['id']}/channels").get("value", []):
                print(f"    channel {c['displayName']}: teams_channel_id = \"{c['id']}\"")
    elif cmd == "testmail" and len(sys.argv) > 2:
        print("conversationId:", mail_send([sys.argv[2]], "GEO engine test", "<p>It works.</p>"))
    else:
        print(__doc__)
