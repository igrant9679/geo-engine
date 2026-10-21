"""SQLite schema. Run `python db.py` once to create data/geo.db (safe to re-run)."""
from common import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);

-- Search Console: site totals per day, page totals per day, and the latest 28-day query x page snapshot
CREATE TABLE IF NOT EXISTS gsc_daily (
  client TEXT, date TEXT, clicks REAL, impressions REAL, ctr REAL, position REAL,
  PRIMARY KEY (client, date));
CREATE TABLE IF NOT EXISTS gsc_page_daily (
  client TEXT, date TEXT, page TEXT, clicks REAL, impressions REAL, position REAL,
  PRIMARY KEY (client, date, page));
CREATE TABLE IF NOT EXISTS gsc_qp (
  client TEXT, query TEXT, page TEXT, clicks REAL, impressions REAL, ctr REAL, position REAL,
  pulled_on TEXT, PRIMARY KEY (client, query, page));

-- Pages found in the sitemap, with crawl + index status
CREATE TABLE IF NOT EXISTS pages (
  client TEXT, url TEXT, status INTEGER, final_url TEXT, redirects INTEGER,
  title TEXT, meta_desc TEXT, h1_count INTEGER, words INTEGER, canonical TEXT,
  crawled_at TEXT, coverage TEXT, inspected_at TEXT, first_seen TEXT, last_touched TEXT,
  PRIMARY KEY (client, url));

-- AI answer samples (one row per engine x prompt x sample)
CREATE TABLE IF NOT EXISTS mention_samples (
  id INTEGER PRIMARY KEY AUTOINCREMENT, client TEXT, run_on TEXT, engine TEXT,
  prompt TEXT, kind TEXT, sample INTEGER, mentioned INTEGER, cited INTEGER,
  competitors TEXT, cited_domains TEXT, fact_ok INTEGER, answer TEXT);
CREATE INDEX IF NOT EXISTS ix_ms ON mention_samples(client, run_on);

-- Google rank checks (optional, DataForSEO)
CREATE TABLE IF NOT EXISTS serp (
  client TEXT, date TEXT, keyword TEXT, rank INTEGER, url TEXT, top_domains TEXT,
  PRIMARY KEY (client, date, keyword));

-- Work items
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT, client TEXT, created_at TEXT, updated_at TEXT,
  type TEXT, skill TEXT, title TEXT, target_url TEXT, target_query TEXT, context TEXT,
  score REAL, status TEXT,            -- planned|running|blocked|review|merged|rejected|failed|done
  session_id TEXT, branch TEXT, pr_url TEXT, wp_draft_id INTEGER, preview_url TEXT,
  cost_usd REAL DEFAULT 0, result TEXT, merged_at TEXT);
CREATE INDEX IF NOT EXISTS ix_tasks ON tasks(client, status);

-- Questions and approvals sent to clients, and their answers
CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, client TEXT, task_id INTEGER, kind TEXT DEFAULT 'question',
  channel TEXT, text TEXT, external_ref TEXT, asked_at TEXT,
  answer TEXT, answered_by TEXT, answered_at TEXT, status TEXT DEFAULT 'open');

-- Unprompted client messages
CREATE TABLE IF NOT EXISTS inbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT, client TEXT, channel TEXT, author TEXT,
  text TEXT, received_at TEXT, handled INTEGER DEFAULT 0);

-- Google Docs created per client (questionnaire, facts, reports, previews)
CREATE TABLE IF NOT EXISTS docs (
  client TEXT, kind TEXT, doc_id TEXT, url TEXT, title TEXT, created_at TEXT, last_text_hash TEXT,
  PRIMARY KEY (client, kind, doc_id));
"""


def init():
    con = db()
    con.executescript(SCHEMA)
    con.commit()
    return con


if __name__ == "__main__":
    init()
    print("Database ready.")
