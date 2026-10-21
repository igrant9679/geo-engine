"""Polite sitemap crawler: records status, redirects, title, meta description, H1s, word count, canonical."""
import re
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

import requests

from common import log, now

L = log("crawl")
UA = "GEO-Audit/1.0 (+contact: site owner's agency)"
NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


class _Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title, self.meta_desc, self.canonical, self.h1 = "", "", "", 0
        self._in_title, self._skip, self.text = False, 0, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta" and (a.get("name") or "").lower() == "description":
            self.meta_desc = a.get("content") or ""
        elif tag == "link" and (a.get("rel") or "").lower() == "canonical":
            self.canonical = a.get("href") or ""
        elif tag == "h1":
            self.h1 += 1
        elif tag in ("script", "style", "nav", "footer"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in ("script", "style", "nav", "footer") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.text.append(data)


def sitemap_urls(root_url, cap=500):
    todo, urls, seen = [root_url], [], set()
    while todo and len(urls) < cap:
        sm = todo.pop()
        if sm in seen:
            continue
        seen.add(sm)
        try:
            xml = ET.fromstring(requests.get(sm, headers={"User-Agent": UA}, timeout=30).content)
        except Exception as e:
            L.warning("sitemap %s failed: %s", sm, e)
            continue
        for loc in xml.iter(f"{NS}loc"):
            u = (loc.text or "").strip()
            (todo if xml.tag.endswith("sitemapindex") else urls).append(u)
    return urls[:cap]


def crawl(con, cfg, cap=500, delay=0.5):
    slug, domain = cfg["slug"], cfg["domain"]
    sitemap = cfg.get("site", {}).get("sitemap") or f"https://{domain}/sitemap.xml"
    for url in sitemap_urls(sitemap, cap):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30, allow_redirects=True)
            p = _Page()
            if "html" in r.headers.get("content-type", ""):
                p.feed(r.text)
            words = len(re.findall(r"\w+", " ".join(p.text)))
            row = (r.status_code, r.url, len(r.history), p.title.strip()[:300], p.meta_desc.strip()[:500],
                   p.h1, words, p.canonical, now())
        except Exception as e:
            L.warning("%s fetch failed: %s", url, e)
            row = (0, url, 0, "", "", 0, 0, "", now())
        con.execute(
            "INSERT INTO pages(client,url,status,final_url,redirects,title,meta_desc,h1_count,words,canonical,crawled_at,first_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(client,url) DO UPDATE SET status=excluded.status, "
            "final_url=excluded.final_url, redirects=excluded.redirects, title=excluded.title, meta_desc=excluded.meta_desc, "
            "h1_count=excluded.h1_count, words=excluded.words, canonical=excluded.canonical, crawled_at=excluded.crawled_at",
            (slug, url, *row, now()))
        time.sleep(delay)
    con.commit()
