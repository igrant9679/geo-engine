"""Daily data collection for every client (runs once per client per day unless --force).

python collect.py [--client acme] [--full] [--force]
"""
import argparse
import datetime as dt

import crawl
import dataforseo
import gsc
import mentions
from common import all_clients, client_cfg, db, kv_get, kv_set, log, settings, today

L = log("collect")


def _step(name, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except Exception as e:  # one failing source must not stop the others
        L.exception("step %s failed: %s", name, e)


def collect(cfg, full=False, force=False):
    con = db()
    slug = cfg["slug"]
    if kv_get(con, f"collected:{slug}") == today() and not force:
        return
    s = settings()
    full = full or dt.date.today().strftime("%a") == s["mentions"]["weekly_full_day"]
    has_pages = con.execute("SELECT 1 FROM pages WHERE client=? LIMIT 1", (slug,)).fetchone()

    if full or not has_pages:
        _step("crawl", crawl.crawl, con, cfg)
    if cfg.get("gsc", {}).get("property"):
        _step("gsc", gsc.pull, con, cfg)
        _step("inspect", gsc.inspect, con, cfg, s["gsc"]["inspect_per_day"])
    _step("mentions", mentions.run, con, cfg, full)
    if full and dataforseo.enabled():
        _step("serp", dataforseo.track, con, cfg)
    if cfg.get("google", {}).get("enabled", True):
        import gdocs
        _step("client-docs", gdocs.sync_client_docs, con, cfg)
    kv_set(con, f"collected:{slug}", today())
    L.info("%s collected (full=%s)", slug, full)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--client")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    for c in ([client_cfg(a.client)] if a.client else all_clients()):
        collect(c, a.full, a.force)
