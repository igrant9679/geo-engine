"""Optional: Google rank tracking for keyword-map terms via DataForSEO (pay-as-you-go).
Enabled only when DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD are set."""
import json

import requests

import research
from common import env, log, today
from mentions import domain_of

L = log("dataforseo")
API = "https://api.dataforseo.com/v3"


def enabled():
    return bool(env("DATAFORSEO_LOGIN") and env("DATAFORSEO_PASSWORD"))


def serp(keyword, location_code=2840, language_code="en", depth=20):
    r = requests.post(f"{API}/serp/google/organic/live/advanced", timeout=120,
                      auth=(env("DATAFORSEO_LOGIN"), env("DATAFORSEO_PASSWORD")),
                      json=[{"keyword": keyword, "location_code": location_code,
                             "language_code": language_code, "depth": depth}])
    r.raise_for_status()
    task = r.json()["tasks"][0]
    if task.get("status_code") != 20000:
        raise RuntimeError(task.get("status_message"))
    items = (task.get("result") or [{}])[0].get("items") or []
    return [i for i in items if i.get("type") == "organic"]


def track(con, cfg, limit=100):
    loc = cfg.get("dataforseo", {}).get("location_code", 2840)  # 2840 = United States
    domain = cfg["domain"].lower()
    for row in research.keyword_map(cfg["slug"])[:limit]:
        try:
            organic = serp(row["query"], location_code=loc)
        except Exception as e:
            L.warning("%s serp %r failed: %s", cfg["slug"], row["query"], e)
            continue
        mine = next((i for i in organic if domain_of(i.get("domain", "")).endswith(domain)), None)
        con.execute("INSERT OR REPLACE INTO serp VALUES (?,?,?,?,?,?)",
                    (cfg["slug"], today(), row["query"], mine["rank_group"] if mine else None,
                     mine["url"] if mine else None, json.dumps([i.get("domain") for i in organic[:10]])))
    con.commit()
