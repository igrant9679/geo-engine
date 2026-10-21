"""Client-facing Google Docs: questionnaire, facts sheet, content previews, weekly reports.

Docs are created by this app in YOUR Google Drive (folder per client) and shared with the client's
contacts. The app can only see files it created (drive.file scope).

python gdocs.py questionnaire --client acme     create + share the onboarding questionnaire
python gdocs.py facts --client acme             create + share "Facts we'll use about you" from truth.yaml
python gdocs.py sync --client acme              pull edited docs into ops/research/client-docs/
"""
import argparse
import hashlib
import io

import markdown
import yaml

import research
from common import TEMPLATES, client_cfg, db, log, now, ops_dir

L = log("gdocs")
FOLDER = "application/vnd.google-apps.folder"
GDOC = "application/vnd.google-apps.document"


def _drive():
    from google_auth import service
    return service("drive", "v3")


def md_to_html(text):
    return markdown.markdown(text, extensions=["tables", "fenced_code"])


def share(file_id, emails, role):
    drive = _drive()
    for e in emails:
        drive.permissions().create(fileId=file_id, sendNotificationEmail=True,
                                   body={"type": "user", "role": role, "emailAddress": e}).execute()


def folder(con, cfg):
    row = con.execute("SELECT doc_id FROM docs WHERE client=? AND kind='folder'", (cfg["slug"],)).fetchone()
    if row:
        return row["doc_id"]
    f = _drive().files().create(body={"name": f"{cfg['name']} - Search & AI visibility", "mimeType": FOLDER},
                                fields="id,webViewLink").execute()
    con.execute("INSERT INTO docs VALUES (?,?,?,?,?,?,?)", (cfg["slug"], "folder", f["id"], f["webViewLink"], "folder", now(), None))
    con.commit()
    share(f["id"], cfg.get("google", {}).get("share_with", []), "reader")  # reports inside are readable
    return f["id"]


def create_doc(con, cfg, kind, title, html, role=None):
    """Create a Google Doc from HTML in the client's folder; optionally share it with edit/comment rights."""
    from googleapiclient.http import MediaIoBaseUpload

    media = MediaIoBaseUpload(io.BytesIO(html.encode("utf-8")), mimetype="text/html", resumable=False)
    f = _drive().files().create(body={"name": title, "mimeType": GDOC, "parents": [folder(con, cfg)]},
                                media_body=media, fields="id,webViewLink").execute()
    text_hash = _hash(export_text(f["id"]))
    con.execute("INSERT INTO docs VALUES (?,?,?,?,?,?,?)", (cfg["slug"], kind, f["id"], f["webViewLink"], title, now(), text_hash))
    con.commit()
    if role:
        share(f["id"], cfg.get("google", {}).get("share_with", []), role)
    return f["webViewLink"]


def export_text(file_id):
    data = _drive().files().export(fileId=file_id, mimeType="text/plain").execute()
    return data.decode("utf-8-sig") if isinstance(data, bytes) else data


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sync_client_docs(con, cfg):
    """Pull questionnaire/facts docs the client may have edited; queue an ingest task when they change."""
    out_dir = ops_dir(cfg["slug"]) / "research" / "client-docs"
    changed = []
    for d in con.execute("SELECT * FROM docs WHERE client=? AND kind IN ('questionnaire','facts')", (cfg["slug"],)).fetchall():
        text = export_text(d["doc_id"])
        h = _hash(text)
        if h != d["last_text_hash"]:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{d['kind']}.txt").write_text(text, encoding="utf-8")
            con.execute("UPDATE docs SET last_text_hash=? WHERE doc_id=?", (h, d["doc_id"]))
            changed.append(d["kind"])
    open_task = con.execute("SELECT 1 FROM tasks WHERE client=? AND skill='ingest-client-docs' AND status IN "
                            "('planned','running','blocked','review')", (cfg["slug"],)).fetchone()
    if changed and not open_task:
        con.execute("INSERT INTO tasks(client,created_at,updated_at,type,skill,title,target_url,target_query,context,score,status) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?, 'planned')",
                    (cfg["slug"], now(), now(), "ingest-client-docs", "ingest-client-docs",
                     f"Client updated: {', '.join(changed)}", "", "", '{"files": ["research/client-docs/"]}', 999))
    con.commit()
    if changed:
        L.info("%s: client docs changed: %s", cfg["slug"], changed)


def questionnaire(cfg):
    html = (TEMPLATES / "questionnaire.html").read_text(encoding="utf-8").replace("{{NAME}}", cfg["name"])
    return create_doc(db(), cfg, "questionnaire", f"{cfg['name']} - onboarding questions", html, role="writer")


def facts(cfg):
    t = research.truth(cfg["slug"])
    body = (f"# Facts we will use about {cfg['name']}\n\nEvery article and page we write is checked against this list. "
            "Please correct anything wrong directly in this document (or leave a comment).\n\n"
            f"```\n{yaml.safe_dump(t, sort_keys=False, allow_unicode=True)}\n```\n")
    return create_doc(db(), cfg, "facts", f"{cfg['name']} - facts we will use", md_to_html(body), role="writer")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["questionnaire", "facts", "sync"])
    ap.add_argument("--client", required=True)
    a = ap.parse_args()
    c = client_cfg(a.client)
    if a.action == "sync":
        sync_client_docs(db(), c)
    else:
        print({"questionnaire": questionnaire, "facts": facts}[a.action](c))
