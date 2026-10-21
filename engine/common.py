"""Shared paths, settings, secrets, database connection and logging for the GEO engine."""
import datetime as dt
import logging
import os
import pathlib
import sqlite3
import sys
import tomllib

ENGINE = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(os.environ.get("GEO_ROOT", ENGINE.parent))
CLIENTS = ROOT / "clients"
DATA = ROOT / "data"
LOGS = ROOT / "logs"
TEMPLATES = ENGINE / "templates"
SKILLS = ENGINE / "skills"


def load_env(path=ENGINE / ".env"):
    """Minimal .env loader (KEY=value lines). Real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            value = value.split(" #", 1)[0].strip().strip('"').strip("'")
            if value:
                os.environ.setdefault(key.strip(), value)


load_env()


def env(key, default=None, required=False):
    value = os.environ.get(key, default)
    if required and not value:
        raise SystemExit(f"Missing {key} in engine/.env")
    return value


def settings():
    with open(ENGINE / "settings.toml", "rb") as f:
        return tomllib.load(f)


def ops_dir(slug):
    return CLIENTS / slug / "ops"


def site_dir(slug):
    return CLIENTS / slug / "site"


def client_cfg(slug):
    with open(ops_dir(slug) / "client.toml", "rb") as f:
        cfg = tomllib.load(f)
    cfg["slug"] = slug
    return cfg


def all_clients(active_only=True):
    out = []
    for path in sorted(CLIENTS.glob("*/ops/client.toml")):
        cfg = client_cfg(path.parent.parent.name)
        if not active_only or cfg.get("active", True):
            out.append(cfg)
    return out


def db():
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DATA / "geo.db", timeout=60)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def kv_get(con, key, default=None):
    row = con.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def kv_set(con, key, value):
    con.execute("INSERT INTO kv(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)))
    con.commit()


def log(name):
    LOGS.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        fh = logging.FileHandler(LOGS / f"{name}.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        if sys.stdout is not None:  # pythonw (scheduled tasks) has no console
            sh = logging.StreamHandler(sys.stdout)
            sh.setFormatter(fmt)
            logger.addHandler(sh)
        logger.setLevel(logging.INFO)
    return logger


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def today():
    return dt.date.today().isoformat()


def days_ago(n):
    return (dt.date.today() - dt.timedelta(days=n)).isoformat()
