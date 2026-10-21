"""WordPress delivery: Claude writes ops/out/<task>/post.md; this turns it into a WordPress DRAFT for review.

Credentials per client in engine/.env:  WP_<SLUG>_USER=...  WP_<SLUG>_APP_PASSWORD=...
(Users > Profile > Application Passwords in wp-admin; use an Editor-role account, not an admin.)

post.md front matter:
  title, slug, meta_description, type (post|page)
  wp_id: 123            update an existing post/page (a draft copy is reviewed; the original changes on approval)
  format: html          body is raw HTML / block markup (keep Gutenberg comments); default is markdown
  content_unchanged: true   only title/excerpt change (retitle tasks); the body is ignored

Claude can read an existing post's stored content (block markup included) with:
  python wp.py fetch --client <slug> --id 123 --out out/<task>/original.html
"""
import argparse
import pathlib
import re

import markdown
import requests
import yaml

from common import client_cfg, env
from validate import split_frontmatter


def _auth(cfg):
    key = cfg["slug"].upper().replace("-", "_")
    return env(f"WP_{key}_USER", required=True), env(f"WP_{key}_APP_PASSWORD", required=True)


def _api(cfg, path):
    return cfg["site"]["wp_url"].rstrip("/") + "/wp-json/wp/v2/" + path


def _kind(meta):
    return "pages" if meta.get("type") == "page" else "posts"


def read_post(path):
    fm, body = split_frontmatter(pathlib.Path(path).read_text(encoding="utf-8"))
    meta = yaml.safe_load(fm) or {}
    if meta.get("content_unchanged"):
        return meta, None
    html = body.strip() if meta.get("format") == "html" else markdown.markdown(body, extensions=["tables", "fenced_code"])
    return meta, html


def fetch_raw(cfg, post_id, kind="posts"):
    r = requests.get(_api(cfg, f"{kind}/{post_id}"), params={"context": "edit"}, auth=_auth(cfg), timeout=60)
    if r.status_code == 404 and kind == "posts":
        return fetch_raw(cfg, post_id, "pages")
    r.raise_for_status()
    j = r.json()
    return {"title": j["title"]["raw"], "content": j["content"]["raw"], "excerpt": j["excerpt"]["raw"], "link": j["link"]}


def _fields(cfg, meta, html):
    if html is None:  # retitle: keep the live body
        html = fetch_raw(cfg, meta["wp_id"], _kind(meta))["content"]
    return {"content": html, "excerpt": meta.get("meta_description", "")}


def create_draft(cfg, post_md):
    """Create a draft. For an update (wp_id), the draft is a copy; the live post changes only when you approve."""
    meta, html = read_post(post_md)
    title = f"[GEO update] {meta['title']}" if meta.get("wp_id") else meta["title"]
    body = {"title": title, "status": "draft", **_fields(cfg, meta, html)}
    if meta.get("slug") and not meta.get("wp_id"):
        body["slug"] = meta["slug"]
    r = requests.post(_api(cfg, _kind(meta)), auth=_auth(cfg), json=body, timeout=60)
    r.raise_for_status()
    draft = r.json()
    return draft["id"], cfg["site"]["wp_url"].rstrip("/") + f"/?p={draft['id']}&preview=true"


def update_draft(cfg, post_md, draft_id):
    meta, html = read_post(post_md)
    title = f"[GEO update] {meta['title']}" if meta.get("wp_id") else meta["title"]
    r = requests.post(_api(cfg, f"{_kind(meta)}/{draft_id}"), auth=_auth(cfg), timeout=60,
                      json={"title": title, **_fields(cfg, meta, html)})
    r.raise_for_status()


def publish(cfg, post_md, draft_id):
    meta, html = read_post(post_md)
    auth, kind = _auth(cfg), _kind(meta)
    if meta.get("wp_id"):  # update the live post, then move the draft copy to the trash (recoverable)
        body = {"title": meta["title"], "excerpt": meta.get("meta_description", "")}
        if html is not None:
            body["content"] = html
        r = requests.post(_api(cfg, f"{kind}/{meta['wp_id']}"), auth=auth, json=body, timeout=60)
        r.raise_for_status()
        requests.delete(_api(cfg, f"{kind}/{draft_id}"), auth=auth, timeout=60)
        return r.json()["link"]
    r = requests.post(_api(cfg, f"{kind}/{draft_id}"), auth=auth, json={"status": "publish"}, timeout=60)
    r.raise_for_status()
    return r.json()["link"]


def discard(cfg, post_md, draft_id):
    meta, _ = read_post(post_md)
    requests.delete(_api(cfg, f"{_kind(meta)}/{draft_id}"), auth=_auth(cfg), timeout=60)  # moves to trash


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["fetch"])
    ap.add_argument("--client", required=True)
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    post = fetch_raw(client_cfg(a.client), a.id)
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"<!-- title: {post['title']} | link: {post['link']} | excerpt: {post['excerpt']} -->\n{post['content']}",
                   encoding="utf-8")
    print(f"Saved {out}")
