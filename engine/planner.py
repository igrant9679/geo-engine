"""Decide what is most impactful today, per client.

Code generates and scores candidates from the collected data (deterministic, explainable);
Claude only does the work. `python planner.py --client acme --dry-run` prints the ranking.
"""
import argparse
import datetime as dt
import json
from collections import Counter, defaultdict

import mentions
import research
from common import client_cfg, db, days_ago, kv_get, log, now, settings

L = log("planner")
OPEN = ("planned", "running", "blocked", "review")
EXPECTED_CTR = {1: .28, 2: .16, 3: .11, 4: .08, 5: .06, 6: .05, 7: .04, 8: .03, 9: .025, 10: .02}


def expected_ctr(position):
    return EXPECTED_CTR.get(max(1, round(position)), 0.01)


def cand(skill, title, opportunity, confidence=0.7, target_url="", target_query="", **context):
    return {"skill": skill, "title": title, "opportunity": float(opportunity), "confidence": confidence,
            "target_url": target_url, "target_query": target_query, "context": context}


# ---------- candidate generators ----------

def from_search_console(con, slug, s):
    min_impr = s["planner"]["min_impressions"]
    rows = con.execute("SELECT * FROM gsc_qp WHERE client=?", (slug,)).fetchall()
    by_query, by_page = defaultdict(list), defaultdict(list)
    for r in rows:
        by_query[r["query"]].append(r)
        by_page[r["page"]].append(r)
    out = []

    # Striking distance: queries at positions 4-20 with real impressions -> refresh the ranking page
    striking = defaultdict(list)
    for q, rs in by_query.items():
        impr = sum(r["impressions"] for r in rs)
        if impr < min_impr:
            continue
        pos = sum(r["position"] * r["impressions"] for r in rs) / impr
        best = max(rs, key=lambda r: r["impressions"])
        if 4 <= pos <= 20:
            striking[best["page"]].append((q, impr, pos))
    for page, qs in striking.items():
        qs.sort(key=lambda x: -x[1])
        opp = sum(i * (expected_ctr(3) - expected_ctr(p)) for _, i, p in qs)
        out.append(cand("refresh-page", f"Refresh page for striking-distance queries ({qs[0][0]})", opp, 0.7,
                        target_url=page, target_query=qs[0][0],
                        goal="search", queries=[{"query": q, "impressions": int(i), "position": round(p, 1)} for q, i, p in qs[:10]]))

    # Low CTR for its position -> rewrite title + meta description
    for page, rs in by_page.items():
        impr = sum(r["impressions"] for r in rs)
        if impr < 3 * min_impr:
            continue
        clicks = sum(r["clicks"] for r in rs)
        pos = sum(r["position"] * r["impressions"] for r in rs) / impr
        ctr, exp = clicks / impr, expected_ctr(pos)
        if pos <= 10 and ctr < 0.5 * exp:
            top = sorted(rs, key=lambda r: -r["impressions"])[:5]
            out.append(cand("retitle", f"Rewrite title/meta (CTR {ctr:.1%} vs ~{exp:.0%} expected)", impr * (exp - ctr), 0.6,
                            target_url=page, ctr=round(ctr, 4), position=round(pos, 1), top_queries=[r["query"] for r in top]))

    # Cannibalization: two+ pages splitting one query -> human-reviewed recommendation
    for q, rs in by_query.items():
        impr = sum(r["impressions"] for r in rs)
        shares = [r for r in rs if impr and r["impressions"] / impr >= 0.2]
        if impr >= 2 * min_impr and len(shares) >= 2:
            out.append(cand("cannibalization-review", f"Pages competing for '{q}'", impr * 0.02, 0.5, target_query=q,
                            pages=[{"page": r["page"], "impressions": int(r["impressions"]), "position": round(r["position"], 1)} for r in shares]))
    return out


def from_ai_answers(con, slug, cfg):
    out = []
    stats = mentions.rates(con, slug, days_ago(14))
    prompt_rows = {p["prompt"]: p for p in research.prompts(slug)}
    for prompt, st in stats.items():
        row = prompt_rows.get(prompt)
        if not row or st["n"] < 3:
            continue
        weight = 2 if row.get("frequency") == "daily" else 1
        ctx = {"prompt": prompt, "mention_rate": round(st["mention_rate"], 2), "samples": st["n"],
               "competitors_named": [c for c, _ in st["competitors"].most_common(5)],
               "sources_ai_cites": [d for d, _ in st["domains"].most_common(10)]}
        if row.get("kind") == "fact":
            if st["fact_n"] >= 2 and st["fact_rate"] is not None and st["fact_rate"] < 0.5:
                wrong = con.execute("SELECT engine, answer FROM mention_samples WHERE client=? AND prompt=? AND fact_ok=0 "
                                    "ORDER BY id DESC LIMIT 2", (slug, prompt)).fetchall()
                out.append(cand("correction-research", f"AI states wrong facts for '{prompt}'", 300, 0.8,
                                target_query=prompt, expected_pattern=row.get("expect"),
                                wrong_answers=[{"engine": w["engine"], "answer": w["answer"][:1500]} for w in wrong], **ctx))
            continue
        if st["mention_rate"] < 0.34 and st["comp_rate"] >= 0.5:
            opp = 150 * (1 - st["mention_rate"]) * weight
            if row.get("target_url"):
                out.append(cand("refresh-page", f"Get named for '{prompt}' (existing page)", opp, 0.6,
                                target_url=row["target_url"], target_query=prompt, goal="ai-answers", **ctx))
            elif row.get("kind") == "comparison":
                out.append(cand("comparison-page", f"Comparison page for '{prompt}'", opp, 0.6, target_query=prompt, **ctx))
            else:
                out.append(cand("write-article", f"Article answering '{prompt}'", opp, 0.55, target_query=prompt, **ctx))
    return out


def from_keyword_map(slug):
    out = []
    skill_for = {"tool": "build-free-tool", "comparison": "comparison-page"}
    for r in research.keyword_map(slug):
        if r.get("url") or r.get("status", "planned") != "planned":
            continue
        vol = float(r.get("volume") or 0)
        skill = skill_for.get(r.get("intent", ""), "write-article")
        out.append(cand(skill, f"New {skill.replace('-', ' ')}: '{r['query']}'", max(vol * 0.03, 10), 0.5,
                        target_query=r["query"], intent=r.get("intent"), volume=vol))
    return out


def from_crawl(con, slug):
    out = []
    old = days_ago(14)
    unindexed = [r["url"] for r in con.execute(
        "SELECT url, coverage FROM pages WHERE client=? AND status=200 AND coverage IS NOT NULL AND first_seen < ?",
        (slug, old)) if not r["coverage"].lower().startswith(("submitted and indexed", "indexed"))]
    if unindexed:
        out.append(cand("index-fix", f"{len(unindexed)} pages not indexed", 15 * min(len(unindexed), 10), 0.6,
                        urls=unindexed[:10]))

    issues = []
    titles = Counter(r["title"] for r in con.execute("SELECT title FROM pages WHERE client=? AND title != ''", (slug,)))
    for r in con.execute("SELECT * FROM pages WHERE client=?", (slug,)):
        problems = []
        if r["status"] == 0 or (r["status"] or 0) >= 400:
            problems.append(f"HTTP {r['status']} but listed in sitemap")
        if (r["redirects"] or 0) > 1:
            problems.append(f"redirect chain ({r['redirects']} hops)")
        if r["status"] == 200:
            if not r["title"]:
                problems.append("missing <title>")
            elif titles[r["title"]] > 1:
                problems.append("duplicate <title>")
            if not r["meta_desc"]:
                problems.append("missing meta description")
            if r["h1_count"] != 1:
                problems.append(f"{r['h1_count']} H1 tags")
        if problems:
            issues.append({"url": r["url"], "problems": problems})
    if issues:
        out.append(cand("page-fixes", f"Technical fixes on {len(issues)} pages", 8 * min(len(issues), 15), 0.8,
                        pages=issues[:15]))
    return out


# ---------- filtering + scoring ----------

def _blocked_by_history(con, slug, c, cooldown):
    key_url, key_q = c["target_url"], c["target_query"]
    rows = con.execute("SELECT status, created_at, merged_at FROM tasks WHERE client=? AND skill=? AND "
                       "((target_url != '' AND target_url=?) OR (target_query != '' AND target_query=?))",
                       (slug, c["skill"], key_url, key_q)).fetchall()
    for r in rows:
        if r["status"] in OPEN:
            return True
        if r["status"] == "rejected" and r["created_at"] >= days_ago(30):
            return True
        if r["merged_at"] and r["merged_at"] >= days_ago(cooldown):
            return True
    if key_url:
        touched = con.execute("SELECT last_touched FROM pages WHERE client=? AND url=?", (slug, key_url)).fetchone()
        if touched and touched["last_touched"] and touched["last_touched"] >= days_ago(cooldown):
            return True
    return False


def _over_monthly_cap(con, slug, skill, limits):
    cap = limits.get(skill)
    if cap is None:
        return False
    month = dt.date.today().strftime("%Y-%m")
    used = con.execute("SELECT COUNT(*) FROM tasks WHERE client=? AND skill=? AND substr(created_at,1,7)=? "
                       "AND status NOT IN ('rejected','failed')", (slug, skill, month)).fetchone()[0]
    return used >= cap


def score(con, c, s):
    lift = float(kv_get(con, f"lift:{c['skill']}", s["planner"]["lift"].get(c["skill"], 0.3)))
    effort = s["planner"]["effort"].get(c["skill"], 30)
    boost = s["planner"].get("boost", {}).get(c["skill"], 1.0)
    return round(c["opportunity"] * lift * c["confidence"] * boost / max(effort, 5), 3)


def candidates(con, cfg):
    s, slug = settings(), cfg["slug"]
    cands = from_search_console(con, slug, s) + from_ai_answers(con, slug, cfg) + from_keyword_map(slug) + from_crawl(con, slug)
    cooldown = s["runner"]["cooldown_days"]
    keep = []
    for c in cands:
        if _blocked_by_history(con, slug, c, cooldown) or _over_monthly_cap(con, slug, c["skill"], cfg.get("limits", {})):
            continue
        c["score"] = score(con, c, s)
        keep.append(c)
    return sorted(keep, key=lambda c: -c["score"])


def plan(cfg, n=None):
    """Queue up to n tasks for this run; returns the planned task rows (highest score first)."""
    con, s, slug = db(), settings(), cfg["slug"]
    n = n or s["runner"]["tasks_per_run"]

    # Blocked tasks whose questions are all answered go back in the queue (they resume their Claude session).
    for t in con.execute("SELECT id FROM tasks WHERE client=? AND status='blocked'", (slug,)).fetchall():
        if not con.execute("SELECT 1 FROM questions WHERE task_id=? AND status IN ('draft','open')", (t["id"],)).fetchone():
            con.execute("UPDATE tasks SET status='planned', updated_at=? WHERE id=?", (now(), t["id"]))
    con.commit()

    queued = con.execute("SELECT COUNT(*) FROM tasks WHERE client=? AND status='planned'", (slug,)).fetchone()[0]
    for c in candidates(con, cfg)[: max(0, n - queued)]:
        con.execute("INSERT INTO tasks(client,created_at,updated_at,type,skill,title,target_url,target_query,context,score,status) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?, 'planned')",
                    (slug, now(), now(), c["skill"], c["skill"], c["title"], c["target_url"], c["target_query"],
                     json.dumps(c["context"]), c["score"]))
    con.commit()
    return con.execute("SELECT * FROM tasks WHERE client=? AND status='planned' ORDER BY score DESC LIMIT ?",
                       (slug, n)).fetchall()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", required=True)
    ap.add_argument("--dry-run", action="store_true", help="print ranked candidates without queuing")
    a = ap.parse_args()
    cfg = client_cfg(a.client)
    if a.dry_run:
        for c in candidates(db(), cfg)[:25]:
            print(f"{c['score']:>8}  {c['skill']:<24} {c['title']}")
    else:
        for t in plan(cfg):
            print(t["id"], t["skill"], t["title"])
