"""AI-visibility tracking: ask each enabled AI engine every prompt N times and record who gets named."""
import json
import re
from collections import Counter, defaultdict
from urllib.parse import urlparse

import research
from ai_engines import enabled
from common import log, settings, today

L = log("mentions")


def domain_of(u):
    u = (u or "").strip().lower()
    host = urlparse(u).netloc if "://" in u else u.split("/")[0]
    return host.removeprefix("www.")


def _named(name, text):
    return re.search(r"(?<![\w-])" + re.escape(name.lower()) + r"(?![\w-])", text) is not None


def score(answer, cites, cfg, row):
    text = answer.lower()
    domain = cfg["domain"].lower()
    names = [cfg["name"], *cfg.get("brand_aliases", [])]
    mentioned = any(_named(n, text) for n in names) or domain in text
    domains = sorted({domain_of(c) for c in cites if c})
    cited = any(d == domain or d.endswith("." + domain) for d in domains)
    competitors = [c for c in cfg.get("competitors", []) if _named(c, text)]
    fact_ok = None
    if row.get("kind") == "fact" and row.get("expect") and mentioned:
        fact_ok = int(re.search(row["expect"], answer, re.I) is not None)
    return int(mentioned), int(cited), competitors, domains, fact_ok


def run(con, cfg, full=False):
    engines = enabled()
    if not engines:
        L.info("no AI engine keys set; skipping mention tracking")
        return
    samples = settings()["mentions"]["samples"]
    rows = [r for r in research.prompts(cfg["slug"]) if full or r.get("frequency", "weekly") == "daily"]
    for row in rows:
        for name, (fn, model) in engines.items():
            for i in range(samples):
                try:
                    answer, cites = fn(row["prompt"], model)
                except Exception as e:
                    L.warning("%s/%s failed for %r: %s", cfg["slug"], name, row["prompt"], e)
                    continue
                m, c, comps, doms, fact_ok = score(answer, cites, cfg, row)
                con.execute(
                    "INSERT INTO mention_samples(client,run_on,engine,prompt,kind,sample,mentioned,cited,competitors,"
                    "cited_domains,fact_ok,answer) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cfg["slug"], today(), name, row["prompt"], row.get("kind", ""), i, m, c,
                     json.dumps(comps), json.dumps(doms), fact_ok, answer[:8000]))
        con.commit()
    L.info("%s: tracked %d prompts x %d engines x %d samples", cfg["slug"], len(rows), len(engines), samples)


def rates(con, slug, since, until="9999-12-31"):
    """Per-prompt stats between two dates: n, mention rate, competitor rate, citation rate, fact accuracy, cited domains."""
    out = defaultdict(lambda: {"n": 0, "mentioned": 0, "cited": 0, "comp": 0, "fact_n": 0, "fact_ok": 0,
                               "kind": "", "engines": Counter(), "domains": Counter(), "competitors": Counter()})
    for r in con.execute("SELECT * FROM mention_samples WHERE client=? AND run_on BETWEEN ? AND ?", (slug, since, until)):
        s = out[r["prompt"]]
        s["kind"] = r["kind"]
        s["n"] += 1
        s["mentioned"] += r["mentioned"]
        s["cited"] += r["cited"]
        comps = json.loads(r["competitors"] or "[]")
        s["comp"] += 1 if comps else 0
        s["competitors"].update(comps)
        s["domains"].update(json.loads(r["cited_domains"] or "[]"))
        if r["mentioned"]:
            s["engines"][r["engine"]] += 1
        if r["fact_ok"] is not None:
            s["fact_n"] += 1
            s["fact_ok"] += r["fact_ok"]
    for s in out.values():
        s["mention_rate"] = s["mentioned"] / s["n"] if s["n"] else 0
        s["comp_rate"] = s["comp"] / s["n"] if s["n"] else 0
        s["fact_rate"] = s["fact_ok"] / s["fact_n"] if s["fact_n"] else None
    return dict(out)


def overall(con, slug, since, until="9999-12-31"):
    row = con.execute("SELECT COUNT(*) n, SUM(mentioned) m, SUM(cited) c FROM mention_samples "
                      "WHERE client=? AND run_on BETWEEN ? AND ? AND kind != 'fact'", (slug, since, until)).fetchone()
    n = row["n"] or 0
    return {"samples": n, "mention_rate": (row["m"] or 0) / n if n else 0, "citation_rate": (row["c"] or 0) / n if n else 0}
