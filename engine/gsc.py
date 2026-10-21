"""Google Search Console pulls: daily totals, page-by-day, 28-day query x page, URL inspection, sitemaps."""
import datetime as dt

from common import days_ago, log, now, today
from google_auth import service

L = log("gsc")
LAG_DAYS = 3  # Search Console data is ~2-3 days behind


def _query(svc, prop, body):
    rows, start = [], 0
    while True:
        resp = svc.searchanalytics().query(siteUrl=prop, body={**body, "rowLimit": 25000, "startRow": start}).execute()
        batch = resp.get("rows", [])
        rows += batch
        if len(batch) < 25000:
            return rows
        start += 25000


def pull(con, cfg, days=35):
    prop = cfg["gsc"]["property"]
    svc = service("searchconsole", "v1")
    end, start = days_ago(LAG_DAYS), days_ago(LAG_DAYS + days)
    slug = cfg["slug"]

    for r in _query(svc, prop, {"startDate": start, "endDate": end, "dimensions": ["date"]}):
        con.execute("INSERT OR REPLACE INTO gsc_daily VALUES (?,?,?,?,?,?)",
                    (slug, r["keys"][0], r["clicks"], r["impressions"], r["ctr"], r["position"]))

    for r in _query(svc, prop, {"startDate": start, "endDate": end, "dimensions": ["date", "page"]}):
        con.execute("INSERT OR REPLACE INTO gsc_page_daily VALUES (?,?,?,?,?,?)",
                    (slug, r["keys"][0], r["keys"][1], r["clicks"], r["impressions"], r["position"]))

    qp_start = days_ago(LAG_DAYS + 28)
    rows = _query(svc, prop, {"startDate": qp_start, "endDate": end, "dimensions": ["query", "page"]})
    con.execute("DELETE FROM gsc_qp WHERE client=?", (slug,))
    con.executemany("INSERT INTO gsc_qp VALUES (?,?,?,?,?,?,?,?)",
                    [(slug, r["keys"][0], r["keys"][1], r["clicks"], r["impressions"], r["ctr"], r["position"], today())
                     for r in rows])
    con.commit()
    L.info("%s: %d query/page rows", slug, len(rows))


def inspect(con, cfg, limit=60):
    """Check index status for the pages inspected longest ago (quota ~2,000/day per property)."""
    prop, slug = cfg["gsc"]["property"], cfg["slug"]
    svc = service("searchconsole", "v1")
    urls = [r["url"] for r in con.execute(
        "SELECT url FROM pages WHERE client=? AND (status IS NULL OR status < 400) "
        "ORDER BY COALESCE(inspected_at, '') LIMIT ?", (slug, limit))]
    for url in urls:
        try:
            res = svc.urlInspection().index().inspect(body={"inspectionUrl": url, "siteUrl": prop}).execute()
            coverage = res["inspectionResult"]["indexStatusResult"].get("coverageState", "unknown")
        except Exception as e:  # quota or permission errors: log and stop for today
            L.warning("%s inspect failed at %s: %s", slug, url, e)
            break
        con.execute("UPDATE pages SET coverage=?, inspected_at=? WHERE client=? AND url=?", (coverage, now(), slug, url))
    con.commit()


def submit_sitemap(cfg, sitemap_url):
    service("searchconsole", "v1").sitemaps().submit(siteUrl=cfg["gsc"]["property"], feedpath=sitemap_url).execute()


def weekly_totals(con, slug, weeks_back=0):
    """Clicks/impressions for a 7-day window ending LAG_DAYS ago (weeks_back=1 -> the week before)."""
    end = dt.date.today() - dt.timedelta(days=LAG_DAYS + 7 * weeks_back)
    start = end - dt.timedelta(days=6)
    row = con.execute("SELECT SUM(clicks) c, SUM(impressions) i, AVG(position) p FROM gsc_daily "
                      "WHERE client=? AND date BETWEEN ? AND ?", (slug, start.isoformat(), end.isoformat())).fetchone()
    return {"start": start.isoformat(), "end": end.isoformat(),
            "clicks": row["c"] or 0, "impressions": row["i"] or 0, "position": round(row["p"] or 0, 1)}
