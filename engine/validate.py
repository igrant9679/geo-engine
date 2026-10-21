"""Deterministic checks every change must pass before it reaches human review.

python validate.py --client acme --git            (files changed on the current branch of the site repo)
python validate.py --client acme --files out/12/post.md
Prints JSON {ok, errors, warnings}; exit code 0 = pass. Skills tell Claude to run this before finishing,
and the runner runs it again itself (Claude's word is not trusted).
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

import research
from common import client_cfg, settings, site_dir

CONTENT_EXT = (".md", ".mdx", ".html", ".htm", ".astro", ".njk", ".liquid")
PLACEHOLDERS = re.compile(r"\bTODO\b|lorem ipsum|\[insert|\bXX%|\{\{\s*fill", re.I)
LINK = re.compile(r"\]\((?!#)[^)]+\)|href=[\"'](?!#)[^\"']+[\"']")


def changed_files(cfg):
    site = site_dir(cfg["slug"])
    base = cfg["site"].get("default_branch", "main")
    git = lambda *a: subprocess.run(["git", "-C", str(site), *a], capture_output=True, text=True).stdout
    names = git("diff", "--name-only", f"{base}...HEAD").split()
    names += [line[3:].split(" -> ")[-1] for line in git("status", "--porcelain").splitlines()]
    return [site / n for n in dict.fromkeys(names) if (site / n).is_file()]


def split_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[3:end], text[end + 4:]
    return "", text


def allowed_prices(truth):
    prices = set(map(float, truth.get("allowed_prices", [])))
    for plan in truth.get("pricing", {}).get("plans", []):
        for k in ("price_month", "price_year", "price"):
            if plan.get(k) is not None:
                prices.add(float(plan[k]))
    return prices


def check_file(path, cfg, truth, limits, errors, warnings):
    raw = path.read_text(encoding="utf-8", errors="replace")
    fm, body = split_frontmatter(raw)
    name = path.name
    words = max(len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", body))), 1)

    required = cfg["site"].get("required_frontmatter") or (
        ["title", "meta_description"] if cfg["site"].get("kind") == "wordpress" else [])
    for key in required:
        if not re.search(rf"^{re.escape(key)}\s*:", fm, re.M):
            errors.append(f"{name}: front matter is missing '{key}'")

    n_links = len(LINK.findall(body))
    if n_links / words * 1000 > limits["max_links_per_1000_words"]:
        errors.append(f"{name}: {n_links} links in {words} words is too dense "
                      f"(max {limits['max_links_per_1000_words']}/1000 words)")

    if PLACEHOLDERS.search(body):
        errors.append(f"{name}: contains placeholder text ({PLACEHOLDERS.search(body).group(0)!r})")

    prices = allowed_prices(truth)
    names = [truth.get("company", {}).get("name") or cfg["name"], *cfg.get("brand_aliases", [])]
    for brand in filter(None, names):
        for m in re.finditer(re.escape(brand) + r"[^.\n]{0,80}?\$\s?(\d[\d,]*(?:\.\d{1,2})?)", body):
            value = float(m.group(1).replace(",", ""))
            if prices and value not in prices:
                errors.append(f"{name}: price ${m.group(1)} stated for {brand} is not in truth.yaml")

    for phrase in truth.get("claims_forbidden", []):
        if phrase.lower() in body.lower():
            errors.append(f"{name}: forbidden claim '{phrase}'")

    for chk in truth.get("checks", []):
        for m in re.finditer(chk["pattern"], body, re.I):
            found = m.group(1) if m.groups() else m.group(0)
            if str(found).replace(",", "") != str(chk["expect"]):
                errors.append(f"{name}: says '{m.group(0)}' but truth.yaml says {chk['expect']} ({chk.get('note', '')})")

    for para in re.split(r"\n\s*\n", body):
        has_link = LINK.search(para)
        if re.search(r"\d+(\.\d+)?\s?%", para) and not has_link:
            warnings.append(f"{name}: statistic without a source link: {para.strip()[:90]!r}")
        for comp in cfg.get("competitors", []):
            if comp in para and "$" in para and not has_link:
                errors.append(f"{name}: competitor price for {comp} without a source link")


def run_cmd(cmd, cwd, label, errors):
    if not cmd:
        return
    r = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        errors.append(f"{label} failed: {(r.stdout + r.stderr)[-1500:]}")


def validate(cfg, files, build=True):
    truth = research.truth(cfg["slug"])
    limits = settings()["validator"]
    errors, warnings = [], []
    content = [pathlib.Path(f) for f in files if str(f).lower().endswith(CONTENT_EXT)]
    for f in content:
        check_file(f, cfg, truth, limits, errors, warnings)
    if build and cfg["site"].get("kind") == "git":
        run_cmd(cfg["site"].get("build_cmd"), site_dir(cfg["slug"]), "build", errors)
        run_cmd(cfg["site"].get("test_cmd"), site_dir(cfg["slug"]), "tests", errors)
    return {"ok": not errors, "files_checked": [str(f) for f in content], "errors": errors, "warnings": warnings}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", required=True)
    ap.add_argument("--git", action="store_true")
    ap.add_argument("--files", nargs="*", default=[])
    ap.add_argument("--no-build", action="store_true")
    a = ap.parse_args()
    cfg = client_cfg(a.client)
    files = changed_files(cfg) if a.git else a.files
    result = validate(cfg, files, build=not a.no_build)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)
