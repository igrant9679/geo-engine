"""Monday report per client: numbers by code, a short plain-English summary by Claude, published as a
Google Doc in the client's folder. You get a preview with a "Send to client" button.

python weekly_report.py [--client acme]
"""
import argparse
import html
import json
import re
import subprocess

import comms
import gsc
import mentions
import planner
from common import client_cfg, all_clients, days_ago, db, kv_get, kv_set, log, ops_dir, settings, today

L = log("report")


def metrics(con, cfg):
    slug = cfg["slug"]
    this, prev = gsc.weekly_totals(con, slug, 0), gsc.weekly_totals(con, slug, 1)
    base = json.loads(kv_get(con, f"baseline:{slug}", "null") or "null")
    if not base and this["impressions"]:
        base = this
        kv_set(con, f"baseline:{slug}", json.dumps(base))
    ai_now = mentions.overall(con, slug, days_ago(7))
    ai_prev = mentions.overall(con, slug, days_ago(14), days_ago(8))
    now_rates, prev_rates = mentions.rates(con, slug, days_ago(7)), mentions.rates(con, slug, days_ago(14), days_ago(8))
    prompts = sorted(({"prompt": p, "now": round(s["mention_rate"], 2),
                       "before": round(prev_rates.get(p, {}).get("mention_rate", 0), 2)}
                      for p, s in now_rates.items() if s["kind"] != "fact"), key=lambda x: x["before"] - x["now"])
    shipped = [dict(r) for r in con.execute(
        "SELECT id, title, skill, preview_url FROM tasks WHERE client=? AND status='merged' AND merged_at >= ?",
        (slug, days_ago(7)))]
    movers = [dict(r) for r in con.execute(
        """SELECT page, SUM(CASE WHEN date > ? THEN clicks ELSE 0 END) AS clicks_now,
                  SUM(CASE WHEN date <= ? THEN clicks ELSE 0 END) AS clicks_before
           FROM gsc_page_daily WHERE client=? AND date > ? GROUP BY page
           ORDER BY (clicks_now - clicks_before) DESC LIMIT 5""",
        (days_ago(10), days_ago(10), slug, days_ago(17)))]
    examples = []
    for r in con.execute("SELECT engine, prompt, answer FROM mention_samples WHERE client=? AND mentioned=1 AND kind!='fact' "
                         "AND run_on >= ? ORDER BY id DESC LIMIT 20", (slug, days_ago(7))):
        i = r["answer"].lower().find(cfg["name"].lower())
        if i >= 0 and len(examples) < 2:
            examples.append({"engine": r["engine"], "prompt": r["prompt"], "excerpt": r["answer"][max(0, i - 150): i + 200]})
    waiting = [dict(r) for r in con.execute("SELECT id, text FROM questions WHERE client=? AND status='open'", (slug,))]
    return {"client": cfg["name"], "week": this, "previous_week": prev, "baseline": base,
            "ai_visibility": {"this_week": ai_now, "last_week": ai_prev}, "prompts": prompts[:12],
            "shipped": shipped, "top_pages": movers, "ai_answer_examples": examples, "waiting_on_you": waiting,
            "next_up": [c["title"] for c in planner.candidates(con, cfg)[:5]]}


def narrative(m):
    from runner import claude_bin
    prompt = ("Write the summary paragraph for this weekly search & AI-visibility report. 4-6 plain sentences for a busy "
              "founder: what moved and the likely reason, what shipped, and anything waiting on them. No hype, no "
              "promises, no invented numbers; use only this data. If data is thin (first weeks), say that plainly.\n\n"
              + json.dumps(m, indent=1, default=str))
    r = subprocess.run([claude_bin(), "-p", "--model", settings()["report"]["model"], "--permission-mode", "dontAsk"],
                       input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    return r.stdout.strip() or "Summary unavailable this week; numbers below."


def pct(a, b):
    return f"{(a - b) / b:+.0%}" if b else "new"


def render(m, summary):
    e = html.escape
    w, p, b = m["week"], m["previous_week"], m["baseline"] or m["week"]
    ai, ai_p = m["ai_visibility"]["this_week"], m["ai_visibility"]["last_week"]
    rows = lambda items: "".join(items) or "<tr><td colspan=3>None this week</td></tr>"
    return f"""<h1>{e(m['client'])}: weekly report ({e(w['start'])} to {e(w['end'])})</h1>
<p>{e(summary)}</p>
<h2>Numbers</h2>
<table border=1 cellpadding=6>
<tr><th></th><th>This week</th><th>vs last week</th><th>vs start</th></tr>
<tr><td>Google clicks</td><td>{w['clicks']:.0f}</td><td>{pct(w['clicks'], p['clicks'])}</td><td>{pct(w['clicks'], b['clicks'])}</td></tr>
<tr><td>Google impressions</td><td>{w['impressions']:.0f}</td><td>{pct(w['impressions'], p['impressions'])}</td><td>{pct(w['impressions'], b['impressions'])}</td></tr>
<tr><td>Average position</td><td>{w['position']}</td><td>{p['position']}</td><td>{b['position']}</td></tr>
<tr><td>Named in AI answers</td><td>{ai['mention_rate']:.0%}</td><td>{ai_p['mention_rate']:.0%}</td><td></td></tr>
<tr><td>Cited (linked) in AI answers</td><td>{ai['citation_rate']:.0%}</td><td>{ai_p['citation_rate']:.0%}</td><td></td></tr>
</table>
<h2>What shipped</h2><table border=1 cellpadding=6><tr><th>#</th><th>Change</th><th>Link</th></tr>
{rows(f"<tr><td>{s['id']}</td><td>{e(s['title'])}</td><td>{e(s['preview_url'] or '')}</td></tr>" for s in m['shipped'])}</table>
<h2>AI answers: how often you're named, by question</h2><table border=1 cellpadding=6><tr><th>Question</th><th>This week</th><th>Last week</th></tr>
{rows(f"<tr><td>{e(x['prompt'])}</td><td>{x['now']:.0%}</td><td>{x['before']:.0%}</td></tr>" for x in m['prompts'])}</table>
<h2>Examples of AI answers naming you</h2>
{''.join(f"<p><b>{e(x['engine'])}</b>, asked <i>{e(x['prompt'])}</i>: \"…{e(x['excerpt'])}…\"</p>" for x in m['ai_answer_examples']) or '<p>None yet.</p>'}
<h2>Waiting on you</h2><ul>{''.join(f"<li>{e(q['text'])}</li>" for q in m['waiting_on_you']) or '<li>Nothing.</li>'}</ul>
<h2>Next up</h2><ul>{''.join(f"<li>{e(t)}</li>" for t in m['next_up']) or '<li>Planning from new data.</li>'}</ul>"""


def report(cfg):
    con = db()
    m = metrics(con, cfg)
    summary = narrative(m)
    page = render(m, summary)
    out = ops_dir(cfg["slug"]) / "reports"
    out.mkdir(exist_ok=True)
    (out / f"{today()}.html").write_text(page, encoding="utf-8")
    link = str(out / f"{today()}.html")
    if cfg.get("google", {}).get("enabled", True):
        import gdocs
        link = gdocs.create_doc(con, cfg, "report", f"{cfg['name']} - weekly report {today()}", page)
    kv_set(con, f"pending_report:{cfg['slug']}", f"Your weekly report is ready: {link}\n\n{re.sub(r'\s+', ' ', summary)[:900]}")
    comms.notify_admin(f"📊 Report ready for {cfg['name']}:\n{link}\n\n{summary[:900]}",
                       [[("📤 Send to client", f"sendreport:{cfg['slug']}")]])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--client")
    a = ap.parse_args()
    for c in ([client_cfg(a.client)] if a.client else all_clients()):
        try:
            report(c)
        except Exception:
            L.exception("report failed for %s", c["slug"])
