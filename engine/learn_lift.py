"""Learn which kinds of work actually move clicks: compares each shipped page's clicks in the 28 days
after the change with the 28 days before, per skill, and feeds the median back into the planner.

python learn_lift.py      (weekly is plenty)
"""
import datetime as dt
import statistics
from collections import defaultdict

from common import days_ago, db, kv_set, log

L = log("lift")


def main():
    con = db()
    ratios = defaultdict(list)
    for t in con.execute("SELECT client, skill, target_url, merged_at FROM tasks WHERE status='merged' "
                         "AND target_url != '' AND merged_at <= ?", (days_ago(31),)):
        m = dt.date.fromisoformat(t["merged_at"][:10])
        span = lambda a, b: con.execute(
            "SELECT COALESCE(SUM(clicks),0) FROM gsc_page_daily WHERE client=? AND page=? AND date BETWEEN ? AND ?",
            (t["client"], t["target_url"], (m + dt.timedelta(days=a)).isoformat(), (m + dt.timedelta(days=b)).isoformat())
        ).fetchone()[0]
        before, after = span(-28, -1), span(1, 28)
        if before + after >= 10:
            ratios[t["skill"]].append((after - before) / max(before, 5))
    for skill, rs in ratios.items():
        if len(rs) >= 5:
            lift = min(max(statistics.median(rs), 0.05), 2.0)
            kv_set(con, f"lift:{skill}", round(lift, 3))
            L.info("lift %s = %.3f from %d changes", skill, lift, len(rs))


if __name__ == "__main__":
    main()
