"""Set up a new client: ops repo from templates, skills, site clone, Google folder + questionnaire.

Git-based site:
  python new_client.py acme --name "Acme" --domain acme.com --git-repo https://github.com/acme/website.git ^
      --gsc "sc-domain:acme.com" --contacts founder@acme.com --channels telegram,email --competitors "Zendesk,Freshdesk"
WordPress site:
  python new_client.py hope-fcu --name "Hope FCU" --domain hopefcu.org --wordpress https://hopefcu.org ^
      --gsc "sc-domain:hopefcu.org" --contacts marketing@hopefcu.org --channels teams,email
Add --no-google to skip creating the Google folder/questionnaire.
"""
import argparse
import json
import shutil
import subprocess

import db as dbmod
from common import CLIENTS, SKILLS, TEMPLATES, client_cfg


def fill(text, values):
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--name", required=True)
    ap.add_argument("--domain", required=True)
    ap.add_argument("--git-repo")
    ap.add_argument("--default-branch", default="main")
    ap.add_argument("--wordpress")
    ap.add_argument("--gsc", default="")
    ap.add_argument("--contacts", default="")
    ap.add_argument("--channels", default="email")
    ap.add_argument("--competitors", default="")
    ap.add_argument("--no-google", action="store_true")
    a = ap.parse_args()
    if not (a.git_repo or a.wordpress):
        raise SystemExit("Give --git-repo or --wordpress")

    base = CLIENTS / a.slug
    ops = base / "ops"
    if ops.exists():
        raise SystemExit(f"{ops} already exists")
    lst = lambda s: json.dumps([x.strip() for x in s.split(",") if x.strip()])  # JSON list == valid TOML array
    values = {"SLUG": a.slug, "NAME": a.name, "DOMAIN": a.domain, "GSC": a.gsc,
              "KIND": "git" if a.git_repo else "wordpress", "WP_URL": a.wordpress or "",
              "DEFAULT_BRANCH": a.default_branch, "CONTACTS": lst(a.contacts), "CHANNELS": lst(a.channels),
              "COMPETITORS": lst(a.competitors), "GOOGLE": "false" if a.no_google else "true"}

    # 1. ops folder from templates
    for src in (TEMPLATES / "ops").rglob("*"):
        if src.is_file():
            dest = ops / src.relative_to(TEMPLATES / "ops")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(fill(src.read_text(encoding="utf-8"), values), encoding="utf-8")
    shutil.copytree(SKILLS, ops / ".claude" / "skills")
    for d in ("out", "reports", "research/sources", "research/client-docs"):
        (ops / d).mkdir(parents=True, exist_ok=True)

    # 2. version control for your private ops repo
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=ops, check=True)
    subprocess.run(["git", "add", "-A"], cwd=ops, check=True)
    subprocess.run(["git", "commit", "-q", "-m", f"Onboard {a.name}"], cwd=ops, check=True)

    # 3. the client's website repo
    if a.git_repo:
        subprocess.run(["git", "clone", a.git_repo, str(base / "site")], check=True)

    # 4. database + Google Docs
    dbmod.init()
    cfg = client_cfg(a.slug)
    if not a.no_google:
        import gdocs
        print("Questionnaire:", gdocs.questionnaire(cfg))

    print(f"""
Created {ops}
Next:
  1. Fill in research/truth.yaml, prompts.csv, keyword-map.csv (or run the onboarding skill, see the guide).
  2. Telegram: add the bot to the client's group and send  /link {a.slug}
     Teams: run  python msgraph.py teams  and paste the IDs into client.toml [comms].
  3. Optional: create a private GitHub repo for this ops folder and `git remote add origin <url>`.
  4. Dry run:  python collect.py --client {a.slug} --force  then  python planner.py --client {a.slug} --dry-run
""")


if __name__ == "__main__":
    main()
