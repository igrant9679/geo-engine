"""The scheduled job (3x a day): collect data, plan, run tasks, back up the database.

python daily.py [--client acme] [--collect-only]
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import pathlib
import sqlite3

import collect
import runner
from common import DATA, all_clients, client_cfg, log, settings

L = log("daily")


def one_client(cfg, collect_only):
    collect.collect(cfg)
    if not collect_only:
        runner.run_client(cfg)


def backup():
    target = settings().get("backup", {}).get("dir")
    if not target:
        return
    folder = pathlib.Path(target)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"geo-{dt.date.today():%a}.db"  # 7 rolling copies, nothing is ever deleted
    with sqlite3.connect(DATA / "geo.db") as src, sqlite3.connect(dest) as dst:
        src.backup(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client")
    ap.add_argument("--collect-only", action="store_true")
    a = ap.parse_args()
    clients = [client_cfg(a.client)] if a.client else all_clients()
    with cf.ThreadPoolExecutor(max_workers=settings()["runner"]["parallel_clients"]) as pool:
        for f in [pool.submit(one_client, c, a.collect_only) for c in clients]:
            try:
                f.result()
            except Exception:
                L.exception("client failed")
    try:
        backup()
    except Exception:
        L.exception("backup failed")


if __name__ == "__main__":
    main()
