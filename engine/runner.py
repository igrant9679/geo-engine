"""Execute planned tasks: one fresh headless Claude Code session per task, checked by code,
delivered as a GitHub PR (git sites) or a WordPress draft, then sent to you for approval.

python runner.py [--client acme] [--task 42]
"""
import argparse
import concurrent.futures as cf
import json
import os
import pathlib
import shutil
import subprocess
import sys

import comms
import indexnow
import planner
import validate
import wp
from common import ENGINE, all_clients, client_cfg, db, log, now, ops_dir, settings, site_dir

L = log("runner")
ALLOWED = ["Read", "Edit", "Write", "Glob", "Grep", "WebSearch", "WebFetch",
           "Bash(python *)", "Bash(py *)", "Bash(git status*)", "Bash(git diff*)", "Bash(git log*)",
           "Bash(npm run *)", "Bash(npm test*)", "Bash(npx *)", "Bash(node *)"]


# ---------- helpers ----------

def _run(args, cwd, check=True):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode:
        raise RuntimeError(f"{' '.join(map(str, args))} failed: {(r.stdout + r.stderr)[-800:]}")
    return r.stdout.strip()


def git(repo, *args, check=True):
    return _run(["git", "-C", str(repo), *args], None, check)


def update(con, task_id, **fields):
    fields["updated_at"] = now()
    con.execute(f"UPDATE tasks SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?", (*fields.values(), task_id))
    con.commit()


def claude_bin():
    path = settings()["runner"].get("claude_bin") or shutil.which("claude")
    if not path:
        raise SystemExit("Claude Code CLI not found. Install it and run `claude` once to sign in.")
    return path


def run_claude(task, cfg, prompt, resume=None):
    s = settings()["runner"]
    site = site_dir(cfg["slug"])
    skill = task["skill"] if "skill" in task.keys() else None
    model = s.get("model_by_skill", {}).get(skill) or s["model"]
    cmd = [claude_bin(), "-p", "--output-format", "json", "--model", model,
           "--permission-mode", "dontAsk", "--allowedTools", ",".join(ALLOWED + s.get("extra_allowed_tools", []))]
    if site.exists():
        cmd += ["--add-dir", str(site)]
    if s.get("max_budget_usd"):
        cmd += ["--max-budget-usd", str(s["max_budget_usd"])]
    if resume:
        cmd += ["--resume", resume]
    env = {**os.environ, "GEO_CLIENT": cfg["slug"], "GEO_TASK_ID": str(task["id"]), "GEO_ENGINE": str(ENGINE),
           # `python` inside Claude's shell = this engine's Python (with its packages)
           "PATH": str(pathlib.Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")}
    try:  # prompt goes in on stdin: no Windows command-line quoting problems
        r = subprocess.run(cmd, input=prompt, cwd=ops_dir(cfg["slug"]), env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=s["task_timeout_min"] * 60)
    except subprocess.TimeoutExpired:
        return {"is_error": True, "result": "timed out"}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"is_error": True, "result": (r.stdout + r.stderr)[-2000:]}


def build_prompt(task, cfg):
    slug, tid = cfg["slug"], task["id"]
    ctx = json.loads(task["context"] or "{}")
    if cfg["site"]["kind"] == "git":
        where = (f"The site repo is {site_dir(slug)} (already on branch {task['branch']}). Make your changes there; "
                 f"content lives in {cfg['site'].get('content_dir', '?')}.")
        check = f'python "{ENGINE / "validate.py"}" --client {slug} --git'
    else:
        where = (f"This is a WordPress site ({cfg['site'].get('wp_url')}). Do not try to log in to WordPress. Write the "
                 f"deliverable to out/{tid}/post.md with YAML front matter: title, slug, meta_description, type (post|page), "
                 f"and wp_id when you are updating an existing post. To read an existing post's stored content run: "
                 f'python "{ENGINE / "wp.py"}" fetch --client {slug} --id <POST_ID> --out out/{tid}/original.html')
        check = f'python "{ENGINE / "validate.py"}" --client {slug} --files out/{tid}/post.md'
    return f"""Client: {cfg['name']} ({cfg['domain']}). Use the `{task['skill']}` skill.

Task #{tid}: {task['title']}
Target URL: {task['target_url'] or '-'}
Target query / prompt: {task['target_query'] or '-'}
Data behind this task (JSON):
{json.dumps(ctx, indent=1)}

{where}

Rules:
- research/truth.yaml is the only source of product facts. If you need a fact that is not there, run
  python "{ENGINE / 'ask_client.py'}" "<one clear question for the client>"
  then stop and summarize what you did so far. The task resumes when the client answers.
- If the task only needs a recommendation (no file changes), write it to out/{tid}/notes.md.
- Before finishing, run: {check}
  and fix every error it reports.
- Do not commit, push, or open pull requests. The runner does that.
- Append one line to worklog.md: date, task #{tid}, what changed, the metric to watch.
- Final reply: 2-4 plain sentences: what you changed, why, and which metric should move."""


def resume_prompt(con, task):
    rows = con.execute("SELECT kind, text, answer FROM questions WHERE task_id=? AND status='answered'", (task["id"],)).fetchall()
    lines = [f"- {r['kind']}: {r['text']}\n  reply: {r['answer']}" for r in rows]
    con.execute("UPDATE questions SET status='closed' WHERE task_id=? AND status='answered'", (task["id"],))
    con.commit()
    return ("New input on this task:\n" + "\n".join(lines) +
            "\n\nIf a reply contains product facts, add them to research/truth.yaml first. Then finish (or revise) "
            "the task, re-run the validator, and give your final 2-4 sentence summary.")


def delivered_files(cfg, task):
    if cfg["site"]["kind"] == "git":
        return validate.changed_files(cfg)
    post = ops_dir(cfg["slug"]) / "out" / str(task["id"]) / "post.md"
    return [post] if post.exists() else []


def commit_ops(cfg, message):
    ops = ops_dir(cfg["slug"])
    git(ops, "add", "-A")
    git(ops, "commit", "-m", message, check=False)


def prepare_branch(cfg, task):
    site, base = site_dir(cfg["slug"]), cfg["site"].get("default_branch", "main")
    if task["branch"]:
        git(site, "checkout", task["branch"])
        return task["branch"]
    if git(site, "status", "--porcelain"):
        raise RuntimeError("site repo has uncommitted changes; clean it up first")
    git(site, "fetch", "origin")
    git(site, "checkout", base)
    git(site, "pull", "--ff-only", "origin", base)
    branch = f"geo/{task['id']}-{wp.slugify(task['title'])[:40]}"
    git(site, "checkout", "-B", branch)
    return branch


# ---------- one task ----------

def execute(task, cfg):
    con, s = db(), settings()["runner"]
    tid, kind = task["id"], cfg["site"]["kind"]
    update(con, tid, status="running")
    try:
        if kind == "git":
            update(con, tid, branch=prepare_branch(cfg, task))
        task = con.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        prompt = resume_prompt(con, task) if task["session_id"] else build_prompt(task, cfg)
        res = run_claude(task, cfg, prompt, resume=task["session_id"])
        cost = (task["cost_usd"] or 0) + (res.get("total_cost_usd") or 0)
        update(con, tid, session_id=res.get("session_id") or task["session_id"], cost_usd=cost, result=res.get("result", ""))
        if res.get("is_error"):
            raise RuntimeError(f"Claude error: {res.get('result', '')[:500]}")

        if con.execute("SELECT 1 FROM questions WHERE task_id=? AND status IN ('draft','open')", (tid,)).fetchone():
            update(con, tid, status="blocked")
            commit_ops(cfg, f"task #{tid} waiting on client")
            return

        files = delivered_files(cfg, task)
        for attempt in range(s["max_fix_rounds"] + 1):
            check = validate.validate(cfg, files)
            if check["ok"]:
                break
            if attempt == s["max_fix_rounds"]:
                raise RuntimeError("validator still failing: " + "; ".join(check["errors"])[:1500])
            res = run_claude(task, cfg, "The validator found these problems. Fix all of them, re-run the validator, "
                                        "then give your final summary.\n" + json.dumps(check["errors"], indent=1),
                             resume=res.get("session_id"))
            cost += res.get("total_cost_usd") or 0
            update(con, tid, cost_usd=cost, result=res.get("result", ""))
            files = delivered_files(cfg, task)

        commit_ops(cfg, f"task #{tid}: {task['title']}")
        deliver(con, cfg, con.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone(), files, check)
    except Exception as e:
        L.exception("task %s failed", tid)
        update(con, tid, status="failed", result=str(e)[:2000])
        comms.notify_admin(f"❌ {cfg['name']} task #{tid} failed: {task['title']}\n{str(e)[:400]}")


def deliver(con, cfg, task, files, check):
    tid = task["id"]
    notes = ops_dir(cfg["slug"]) / "out" / str(tid) / "notes.md"
    summary = task["result"] or ""
    if notes.exists() and files:
        summary += "\n\nNotes:\n" + notes.read_text(encoding="utf-8")[:1200]
    warnings = "\n".join(f"- {w}" for w in check.get("warnings", [])) or "- none"

    if not files:
        if notes.exists():  # recommendation-only task
            update(con, tid, status="review", preview_url=str(notes))
            comms.notify_review(cfg, task, notes.read_text(encoding="utf-8")[:1500])
        else:
            update(con, tid, status="done")
        return

    if cfg["site"]["kind"] == "git":
        site = site_dir(cfg["slug"])
        git(site, "add", "-A")
        git(site, "commit", "-m", f"{task['title']} (GEO task #{tid})", check=False)
        git(site, "push", "-u", "origin", task["branch"])
        pr = task["pr_url"]
        if not pr:
            body = (f"{summary}\n\n**Why:** {task['title']}\n\n**Validator warnings:**\n{warnings}\n\n"
                    f"_Generated by the GEO engine, task #{tid}. Reviewed by a person before merge._")
            pr = _run(["gh", "pr", "create", "--title", task["title"][:120], "--body", body,
                       "--base", cfg["site"].get("default_branch", "main"), "--head", task["branch"]], site)
        update(con, tid, status="review", pr_url=pr, preview_url=pr)
    elif task["wp_draft_id"]:  # revision of an existing draft
        wp.update_draft(cfg, files[0], task["wp_draft_id"])
        update(con, tid, status="review")
    else:
        draft_id, preview = wp.create_draft(cfg, files[0])
        update(con, tid, status="review", wp_draft_id=draft_id, preview_url=preview)

    task = con.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    if task["skill"] in cfg.get("approvals", {}).get("client_must_approve", []):
        comms.request_client_approval(cfg, task, files)
    comms.notify_review(cfg, task, f"{summary}\n\nWarnings:\n{warnings}")


# ---------- approval actions (called from the listener) ----------

def approve(task_id):
    con = db()
    task = con.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    cfg = client_cfg(task["client"])
    live_url = task["target_url"]
    if task["pr_url"]:
        _run(["gh", "pr", "merge", task["pr_url"], "--squash", "--delete-branch"], site_dir(cfg["slug"]))
    elif task["wp_draft_id"]:
        live_url = wp.publish(cfg, ops_dir(cfg["slug"]) / "out" / str(task_id) / "post.md", task["wp_draft_id"])
    update(con, task_id, status="merged", merged_at=now())
    if live_url:
        con.execute("UPDATE pages SET last_touched=? WHERE client=? AND url=?", (now(), cfg["slug"], live_url))
        con.commit()
        indexnow.submit(cfg, [live_url])
    if cfg.get("comms", {}).get("announce_shipped", True):
        comms.tell_client(cfg, f"Shipped: {task['title']}" + (f"\n{live_url}" if live_url else ""))
    return live_url


def reject(task_id, reason=""):
    con = db()
    task = con.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    cfg = client_cfg(task["client"])
    if task["pr_url"]:
        _run(["gh", "pr", "close", task["pr_url"], "--delete-branch", "--comment", reason or "Rejected in review"],
             site_dir(cfg["slug"]), check=False)
    elif task["wp_draft_id"]:
        wp.discard(cfg, ops_dir(cfg["slug"]) / "out" / str(task_id) / "post.md", task["wp_draft_id"])
    update(con, task_id, status="rejected", result=(task["result"] or "") + f"\n[rejected] {reason}")


def request_changes(task_id, feedback):
    """Your feedback becomes an answered 'feedback' item; the next run resumes the same Claude session."""
    con = db()
    task = con.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    con.execute("INSERT INTO questions(client,task_id,kind,channel,text,asked_at,answer,answered_by,answered_at,status) "
                "VALUES (?,?,?,?,?,?,?,?,?, 'answered')",
                (task["client"], task_id, "reviewer feedback", "admin", "Reviewer requested changes", now(),
                 feedback, "reviewer", now()))
    update(con, task_id, status="blocked")


# ---------- entry point ----------

def run_client(cfg, task_id=None):
    con = db()
    tasks = ([con.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()] if task_id else planner.plan(cfg))
    for t in tasks:
        execute(t, cfg)
    if git(ops_dir(cfg["slug"]), "remote", check=False):
        git(ops_dir(cfg["slug"]), "push", check=False)


def main(client=None, task_id=None):
    if task_id:
        client = db().execute("SELECT client FROM tasks WHERE id=?", (task_id,)).fetchone()["client"]
    clients = [client_cfg(client)] if client else all_clients()
    with cf.ThreadPoolExecutor(max_workers=settings()["runner"]["parallel_clients"]) as pool:
        for f in [pool.submit(run_client, c, task_id) for c in clients]:
            try:
                f.result()
            except Exception:
                L.exception("client run failed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--client")
    ap.add_argument("--task", type=int)
    a = ap.parse_args()
    main(a.client, a.task)
