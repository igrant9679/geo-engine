"""Readers for a client's research files (ops/research/*)."""
import csv

import yaml

from common import ops_dir


def _csv(slug, name):
    path = ops_dir(slug) / "research" / name
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(f)]


def prompts(slug):
    """Columns: prompt, kind (category|problem|comparison|fact), frequency (daily|weekly), expect (regex), target_url"""
    return [r for r in _csv(slug, "prompts.csv") if r.get("prompt")]


def keyword_map(slug):
    """Columns: query, intent (info|commercial|comparison|tool), volume, url, status (planned|live|skip)"""
    return [r for r in _csv(slug, "keyword-map.csv") if r.get("query")]


def truth(slug):
    with open(ops_dir(slug) / "research" / "truth.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
