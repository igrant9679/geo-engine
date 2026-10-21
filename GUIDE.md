# GEO Engine: Build and Run Guide

**What this is:** a working, one-person "AI visibility + SEO" service engine, modeled on Josh Pigford's FirstIndex.
This version uses the free or already-owned stack you chose:

| Job | Tool | Cost |
|---|---|---|
| Client conversations | **Telegram**, **Microsoft Teams**, **email** (Outlook via Microsoft 365) | Free / already paid (M365) |
| Client-facing documents (questionnaire, facts sheet, approvals, weekly reports) | **Google Docs** | Free |
| Your control panel (approve / reject / request changes from your phone) | **Telegram bot** | Free |
| Internal database | **SQLite** (one file) | Free |
| Research, facts, work logs | **Plain files in a Git repo per client** | Free (private GitHub repos are free) |
| The worker | **Claude Code** (headless) on your PC | Your Claude plan |
| Search data | **Google Search Console API**, IndexNow | Free |
| AI-answer tracking | ChatGPT / Perplexity / Gemini / Claude APIs | Pay-per-use (pennies per answer; Gemini has a free tier) |
| Rank tracking (optional) | DataForSEO | Pay-per-use |

The code is in the `engine/` folder next to this guide. It is complete and tested (see "What was tested" at the
end). The steps below take you from nothing to a running service, then cover how you operate it every day.

---

## Contents
1. How it works (read once)
2. Part A: one-time setup on your PC (about half a day)
3. Part B: prove it on your own site first (client zero)
4. Part C: onboard a paying client (day 0 to day 7)
5. Part D: running it every day, week and month
6. Part E: reference (what each piece does)
7. Part F: customizing
8. Part G: troubleshooting
9. Part H: security, compliance, offboarding
10. Part I: costs and capacity
11. Command cheat sheet

---

## 1. How it works

```
 3x daily (Task Scheduler)                                   Always on (Task Scheduler at logon)
 ┌──────────────── daily.py ───────────────────┐             ┌──────────── listener.py ─────────────┐
 │ for each client (3 at a time):              │             │ Telegram bot: your buttons + client  │
 │  1 collect.py   GSC, crawl, index status,   │             │   group replies                      │
 │                 AI answers, Google Docs     │   SQLite    │ Every 2 min: Teams thread replies    │
 │  2 planner.py   score candidate tasks       │◄──geo.db───►│   and email replies (Graph API)      │
 │  3 runner.py    claude -p  (fresh session)  │             │ Approve → merge PR / publish WP draft│
 │                 → validate.py (code checks) │             │   → IndexNow → "Shipped" to client   │
 │                 → PR (git) or WP draft      │             └──────────────────────────────────────┘
 │                 → Telegram: "Review #12" ───┼──► you tap ✅ / ❌ / ✏️
 │  4 backup       geo.db → OneDrive folder    │
 └─────────────────────────────────────────────┘
 Mondays: weekly_report.py → Google Doc → you tap "Send to client"
 Sundays: learn_lift.py   → which kinds of work actually moved clicks → planner weights
```

**Rules the design follows (from the video):**
- **One client = one isolated folder** (`clients/<slug>/ops` = your private Git repo; `clients/<slug>/site` = the
  client's website repo if it's code-based). Claude runs inside one client's folder at a time, in a **fresh
  session per task**, so nothing bleeds between clients.
- **Code decides what to do and checks the work; Claude does the work.** The planner, validator, delivery and
  messaging are plain Python. They behave the same way every run.
- **A person approves everything** that ships or goes to a client: changes, questions, reports.
- **Skills are the standard operating procedures.** One `SKILL.md` per kind of work, copied into each client folder.

**Task lifecycle:**
```
planned → running → review ──✅──► merged (shipped)
             │         ├──❌──► rejected
             │         └──✏️──► blocked (your notes) → planned → running (same Claude session, revises)
             ├─ needs a fact → blocked (question drafted → you tap 📤 Send → client replies) → planned → running
             └─ error / validator still failing after 2 fix rounds → failed (you get a ❌ message)
```

---

## Part A: One-time setup on your PC

Do these steps in your own Windows Terminal / PowerShell window, **not inside a Claude session**. The Claude
desktop app is a Microsoft Store build, and its shells see a virtualized AppData. Scheduled tasks must be created
from a normal shell.

### A1. Put the kit in place
1. Copy the `geo-kit` folder to **`C:\geo`**. A short path avoids Windows path-length problems. You should have
   `C:\geo\engine\daily.py`, `C:\geo\scripts\register_tasks.ps1` and `C:\geo\GUIDE.md`.
2. Create the engine's own Python environment and install its packages:
   ```powershell
   python -m venv C:\geo\.venv
   C:\geo\.venv\Scripts\python -m pip install -r C:\geo\engine\requirements.txt
   ```
3. Create the database:
   ```powershell
   cd C:\geo\engine
   C:\geo\.venv\Scripts\python db.py
   ```
   From here on, "**run** `x.py`" means `C:\geo\.venv\Scripts\python x.py`, run from `C:\geo\engine`. To type
   it literally, add this line to your PowerShell profile (`notepad $PROFILE`):
   `function run { Push-Location C:\geo\engine; & C:\geo\.venv\Scripts\python.exe @args; Pop-Location }`
4. Copy `engine\.env.example` to `engine\.env`. You'll fill it in over the next steps. Keep comments on their own
   lines.
5. Make `C:\geo` a Git repo for **your engine code only**, so your changes are versioned. `clients\` and `data\`
   should not go in it:
   ```powershell
   cd C:\geo; git init; "clients/`ndata/`nlogs/`n.venv/`nengine/.env`nengine/google_client_secret.json" | Set-Content .gitignore -Encoding ascii
   ```

### A2. Claude Code (the worker)
1. Check that it's installed and signed in: `claude --version`, then run `claude` once and sign in with the plan
   you'll use. A Max plan is recommended at volume.
2. Find its full path with `(Get-Command claude).Source` (on this PC: `C:\Users\idris\.local\bin\claude.exe`).
   Put it in `engine\settings.toml` → `[runner] claude_bin = "C:/Users/idris/.local/bin/claude.exe"`. Scheduled
   tasks sometimes start with a shorter PATH, and this avoids the problem.
3. How the engine calls it, for reference: `claude -p --output-format json --model opus --permission-mode
   dontAsk --allowedTools "<list>" --add-dir <client site>`, with the task prompt on stdin. `dontAsk` means
   Claude can use **only** the allowed tools (read/edit files, web search, `python`, `git status/diff/log`,
   `npm run`, `npx`, `node`). It can't push, deploy or delete anything. The runner does git itself, after the
   validator passes and before your approval.

### A3. GitHub (for clients with code-based sites)
1. `gh auth login` (GitHub.com, HTTPS, browser). Set `git config --global user.name` and `user.email`.
2. Clients add your GitHub account as a **collaborator with Write access** on their site repo. Many clients have
   Vercel or Netlify preview deploys on pull requests. Ask them to keep that on, because the preview link is what
   you review.

### A4. Google (Search Console + Docs)
You'll create one OAuth "desktop app" so the engine can act as **your Google account**. Clients add this account
to their Search Console, and it owns the client Google Docs.

1. Decide which Google account: your own (idris.grant@gmail.com) or a dedicated agency Gmail such as
   `geo.lsimedia@gmail.com`. A dedicated one keeps client docs separate.
2. Go to <https://console.cloud.google.com> and create a project (e.g. "GEO Engine").
3. **APIs & Services → Library**: enable **Google Search Console API** and **Google Drive API**.
4. **APIs & Services → OAuth consent screen** (Google Auth Platform):
   - User type **External**. App name "GEO Engine". Add your email as support and developer contact.
   - Data access / scopes: add `.../auth/webmasters` and `.../auth/drive.file`.
   - Audience: add your Google account as a test user. **Then click "Publish app" (In production).** This
     step matters: in "Testing" mode, Google expires your sign-in every **7 days** and the engine stops
     collecting. You don't need Google verification for your own use; you'll just see an "unverified app"
     warning once when you sign in.
5. **Clients → Create client → Desktop app**, download the JSON and save it as
   `C:\geo\engine\google_client_secret.json`.
6. Sign in once with `run google_auth.py`. A browser opens: choose the account, click through the unverified
   warning (Advanced → Go to GEO Engine), and allow. The token is saved to `C:\geo\data\google_token.json`.
7. Test it with `run gsc.py`. Nothing should print and nothing should error, since it's only a module. The real
   test is in Part B.

> **About sharing Google Docs with clients:** people with a Google account (including work Google accounts) open
> them directly. Clients on Microsoft 365 without a Google account get an email invite and must create a free
> Google account with their work email to edit or comment. Mention this at kickoff. The questionnaire takes them
> one minute to open.

### A5. Microsoft 365 (Teams + email)
The engine sends and reads Teams channel messages and email **as you** (delegated access), through Microsoft
Graph.

1. Go to <https://entra.microsoft.com> → **App registrations → New registration**:
   - Name "GEO Engine", accounts "**this organizational directory only**", no redirect URI → Register.
   - Copy the **Application (client) ID** and **Directory (tenant) ID** into `.env` as `MS_CLIENT_ID` and
     `MS_TENANT_ID`.
2. **Authentication** → Advanced settings → **Allow public client flows: Yes** → Save. This enables the device-code
   sign-in.
3. **API permissions → Add → Microsoft Graph → Delegated**. Add:
   - `User.Read`
   - `Team.ReadBasic.All`
   - `Channel.ReadBasic.All`
   - `ChannelMessage.Send`
   - `ChannelMessage.Read.All`
   - `Mail.ReadWrite`
   - `Mail.Send`

   Then click **Grant admin consent for <your org>**. `ChannelMessage.Read.All` needs it, and you're the admin.
4. Sign in once with `run msgraph.py login`. It prints a code: open <https://microsoft.com/devicelogin>, enter
   it, and sign in as the mailbox that should send client mail. The token cache lives in `C:\geo\data\`.
5. Test email with `run msgraph.py testmail you@yourdomain.com`.
6. **Teams guest access** (so client people can join a team): in the Teams admin center → Users → Guest access →
   **On**. In Entra → External Identities → External collaboration settings, allow invitations from members (or
   at least admins).
7. Create one **team per client** later (Part C), e.g. "LSI × Hope FCU", with a channel "Website & AI search",
   and invite the client's people as guests. `run msgraph.py teams` prints the IDs to paste into the client's
   settings.

### A6. Telegram (your control panel, and client groups)
1. In Telegram, message **@BotFather** → `/newbot` → name "LSI GEO" → username e.g. `lsi_geo_bot`. Copy the
   token into `.env` as `TELEGRAM_BOT_TOKEN`.
2. Message **@userinfobot** to get your numeric user ID and put it in `.env` as `TELEGRAM_ADMIN_ID`. Only this ID
   can press buttons or run commands.
3. Open a chat with your new bot and press **Start**. Bots can't message you until you do.
4. **Group privacy:** by default the bot only sees commands and **replies to its own messages** in groups. That's
   all the question-and-answer flow needs, and it's the most private option, so leave it on unless you want every
   client message forwarded to you. To change it later: BotFather → `/mybots` → Bot Settings → Group Privacy →
   Turn off, then remove and re-add the bot to groups.

### A7. AI engines for mention tracking
Add keys only for engines you want to track. Each one adds coverage and cost:
- **OpenAI** (ChatGPT answers with web search): <https://platform.openai.com/api-keys> → `OPENAI_API_KEY`
- **Google Gemini** (Google-grounded answers; has a free tier): <https://aistudio.google.com/apikey> →
  `GEMINI_API_KEY`
- **Perplexity** (Sonar): <https://www.perplexity.ai/settings/api> → `PERPLEXITY_API_KEY`
- **Anthropic** (Claude with web search): <https://console.anthropic.com> → `ANTHROPIC_API_KEY`

Set a **monthly spending limit** in each console. A sensible start is **ChatGPT + Gemini**, with
`samples = 2` in `settings.toml` (Part I has the cost math). Model names are in `settings.toml [mentions]`, so
update them when the providers release new ones.

### A8. Optional: DataForSEO
Sign up at <https://dataforseo.com> (pay-as-you-go top-up) and put `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD` in
`.env`. With these set, the weekly full run records Google rank for every keyword-map query. Without them,
everything else still works from Search Console.

### A9. Review `engine\settings.toml`
These are the defaults to know:
- `[runner] tasks_per_run = 1`. With 3 runs a day, that's up to 3 tasks per client per day. Your review time is
  the limit, so raise it slowly.
- `[runner] model = "opus"`, with `[runner.model_by_skill]` using `sonnet` for routine fixes.
- `[comms] hold_for_review = true`. **Every** client-bound question waits for your 📤 Send. Keep it on.
- `[backup] dir`: where the 7 rolling daily database copies go. Point it at a synced OneDrive folder that exists
  on this PC, e.g. `C:/Users/idris/LSI Media LLC/LSI Media LLC General Activities - Documents/GEO backups`.

### A10. Start the services
1. Keep the PC awake. Settings → System → Power: **Sleep = Never** when plugged in. Stay signed in: the tasks run
   as you and only when you're signed in, because that's where Claude Code's sign-in lives. Locking the screen is
   fine.
2. Register the scheduled tasks:
   ```powershell
   powershell -ExecutionPolicy Bypass -File C:\geo\scripts\register_tasks.ps1
   Start-ScheduledTask -TaskPath '\GEO\' -TaskName 'GEO Listener'
   ```
   This creates these tasks under Task Scheduler → `\GEO\`:
   - **GEO Daily** at 06:00, 12:00 and 18:00
   - **GEO Weekly Report** on Monday at 07:00
   - **GEO Learn Lift** on Sunday at 21:00
   - **GEO Listener** at logon, restarted automatically if it stops
3. Test: send `/status` to your bot. It should answer "No clients yet." Logs are in `C:\geo\logs\`.

---

## Part B: Prove it on your own site first (client zero)

Josh ran his system on his own products for most of a year before selling it. Do the same with **lsi-media.com**
(WordPress) and/or **meyousocial.com**. You'll catch setup problems and come away with your own before/after chart.

1. Make sure the site is in **your** Search Console (the Google account from A4).
2. In wp-admin, create an **Editor**-role user for the engine (e.g. `geo-bot`). Then go to Users → Profile →
   **Application Passwords**, create one called "GEO", and add both to `.env`:
   ```
   WP_LSI_USER=geo-bot
   WP_LSI_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
   ```
3. Create the client (you're the "client", so use your own email and Telegram):
   ```powershell
   run new_client.py lsi --name "LSI Media" --domain lsi-media.com --wordpress https://lsi-media.com --gsc "sc-domain:lsi-media.com" --contacts idris.grant@gmail.com --channels telegram --competitors "Competitor A,Competitor B"
   ```
   This creates:
   - `C:\geo\clients\lsi\ops\`, with its own Git history
   - all 12 skills
   - your Google folder plus an onboarding questionnaire doc, shared with you
4. Build the research foundation **interactively** with Claude:
   ```powershell
   cd C:\geo\clients\lsi\ops
   claude
   ```
   Then say: *"Use the onboard-research skill for lsi-media.com."* Review what it drafts:
   - `research/truth.yaml`
   - `voice.md`, `icp.md`, `competitors.md`
   - `prompts.csv`: the questions you want AI to answer with "LSI Media", e.g. "AI automation consultant
     for credit unions", "AI readiness assessment for nonprofits"
   - `keyword-map.csv`

   Correct anything wrong. This is the most important hour of onboarding, because everything downstream is
   checked against these files.
5. Telegram: create a group "LSI GEO (self)", add your bot, and send `/link lsi` **from your own account**.
6. First data pull and a look at what the planner wants to do:
   ```powershell
   run collect.py --client lsi --force --full
   run planner.py --client lsi --dry-run
   ```
   The dry run prints the ranked candidates, e.g. "correction-research 9.6 AI states wrong facts…",
   "retitle 5.6 …". It should make sense to you. If it doesn't, adjust `prompts.csv`, the keyword map, or the
   weights in `settings.toml`.
7. First supervised run: `run runner.py --client lsi`. Watch the log. In Telegram you'll get "🔎 Review: LSI
   Media #1 …" with the WordPress **preview link** and buttons. Open the preview, then tap **✅ Approve & ship**,
   **❌ Reject** (it asks why), or **✏️ Request changes** (type your notes; the next run revises it in the same
   Claude session).
8. Let it run on schedule for **2–4 weeks**. Check `worklog.md` and the Monday report. The goal: you trust the
   reviews, the validator catches real problems, and Search Console shows movement you can put in a pitch.

---

## Part C: Onboard a paying client (day 0 to day 7)

### C1. Before kickoff (contract signed)
Send the client this **access checklist**. Put it in your welcome email or the first message on their channel.
1. **Search Console:** Settings → Users and permissions → Add user → *your Google account* → **Full**.
2. **Website:**
   - Code site: add your GitHub user as a collaborator (Write) on the site repo, and confirm which branch
     deploys to production.
   - WordPress: create an **Editor** user for you and send the username. You'll create the application password
     yourself after the first login. Never accept an admin account.
3. **Communication:** pick one of these.
   - **Teams:** accept the guest invite to "LSI × <Client>".
   - **Telegram:** join the group link you send.
   - **Email:** nothing to do. Questions come from your address with "[Q12]"-style subjects; they just reply.
4. **IndexNow (optional):**
   - Code site: add a file `<key>.txt` containing the key at the site root (generate a 32-character key at
     <https://www.bing.com/indexnow/getstarted>).
   - WordPress: install Microsoft's IndexNow plugin and leave the key blank in your settings; the plugin pings on
     publish.
5. **Who approves** what (comparison pages? pricing mentions?), and their turnaround time.

### C2. Create the client
Code-based site:
```powershell
run new_client.py acme --name "Acme" --domain acme.com --git-repo https://github.com/acme/website.git --gsc "sc-domain:acme.com" --contacts "founder@acme.com,marketing@acme.com" --channels teams,email --competitors "Zendesk,Freshdesk,Help Scout"
```
WordPress site: use `--wordpress https://site.org` instead of `--git-repo`, and add `WP_<SLUG>_USER` and
`WP_<SLUG>_APP_PASSWORD` to `.env` (slug uppercase, dashes become underscores).

Then open `clients\<slug>\ops\client.toml` and complete it:
- `brand_aliases`: other names AI might use
- **Git sites:** `content_dir`, `build_cmd` (e.g. `npm ci && npm run build`), `test_cmd`, and
  `required_frontmatter` (look at an existing post)
- `[comms]`: for Teams, run `run msgraph.py teams` and paste `teams_team_id` and `teams_channel_id`. The
  **first** channel listed is the one used.
- `[approvals] client_must_approve`: the skills the client signs off on
- `[limits]`: match what you sold (e.g. 12 articles a month)

Optionally, create a private GitHub repo for the ops folder and run
`git -C C:\geo\clients\<slug>\ops remote add origin <url>`. The engine pushes after each run, so your work for
that client is backed up and versioned.

### C3. Questionnaire (Google Doc)
`new_client.py` created "\<Client\> – onboarding questions" in their Google folder and shared it with the
contacts as **editor**; they get Google's email. Ask them to fill it in within 3 days. Each daily run pulls the
doc. When it changes, an **ingest-client-docs** task folds the answers into `truth.yaml`, `voice.md` and the
other research files, and you review that like any other change.

### C4. Research foundation
Same as Part B step 4: run `claude` in the client's ops folder, then use the **onboard-research** skill. Review
carefully, especially:
- `truth.yaml`, plus `checks:` entries for numbers that will repeat
- `prompts.csv`: 30–60 prompts, the top 5 marked `daily`, and `fact` prompts with an `expect` regex
- `keyword-map.csv`

### C5. Facts sheet (Google Doc)
`run gdocs.py facts --client <slug>` creates "\<Client\> – facts we will use", shared as editor. The client
corrects it directly. Changes come back automatically through the same ingest task as C3.

### C6. Link the channel
- **Telegram:** create a group "\<Client\> × LSI", add the client people and your bot, and send
  `/link <slug>` from your account. The bot confirms with "Connected to \<Client\>."
- **Teams:** check `client.toml` has the team and channel IDs. The first question posts in that channel; the
  client replies **in the thread**.
- **Email:** check `emails` in `client.toml`. The client just replies to the email.

### C7. Baseline and first run
```powershell
run collect.py --client <slug> --force --full
run planner.py --client <slug> --dry-run
run runner.py --client <slug>
```
The first Monday report records the **baseline** (week one) that every later report compares against. Tell the
client on the kickoff call: *"Search and AI answers take 6–12 weeks to move. You'll see work shipping every week,
and the numbers start moving after that."*

### C8. Hand over to the schedule
Nothing else to do. `active = true` is the default, so the 3x-daily job picks the client up.

---

## Part D: Running it

### Every day (about 15 minutes per 10 clients, twice a day)
Everything comes to your Telegram chat with the bot:

| Message | What to do |
|---|---|
| 🔎 **Review: Client #N** + link | Open the PR, preview deploy or WordPress preview. Check facts, tone, links and claims. Tap ✅, ❌ (you'll be asked why) or ✏️ (type notes). |
| 📝 **Draft question for Client** | Read it. Tap 📤 Send, or 🗑 Drop (the task continues without the fact). Good questions are specific and answerable in one line. |
| 💬 **Client answered Q12** | Nothing. The task resumes on the next run. |
| 👍 **Client approved #N** | Tap ✅ Approve & ship. |
| ✏️ **Client asked for changes** | Nothing. It's revised on the next run, then comes back for review. |
| ❌ **Task failed** | Read the reason. Usually a fact gap, a broken build, or a validator rule. Fix the cause, or ignore it and the planner moves on. |
| 💬 **Client (name): message** | An unprompted message. Answer it in the client's channel yourself. |

Commands: `/queue` re-sends everything waiting for review, `/status` shows task counts and open questions per
client, `/run <slug>` starts a run now.

**Review checklist (30–90 seconds each):**
- **Is it true?** The validator checked prices, numbers and forbidden phrases, but read the claims anyway.
- **Is it useful** to the buyer, and does it answer the question in the first two sentences?
- **Would you sign it?** No hype, fair to competitors, sources linked.
- **Does it fit the site?** Formatting, internal links, no broken layout in the preview.

### Every Monday
1. 07:00: reports are generated. For each client you get "📊 Report ready" with the Google Doc link and summary.
   Skim it and tap **📤 Send to client**. They get the link on their channel; the doc is in their shared folder.
2. Look at the planner's view of each client (`run planner.py --client <slug> --dry-run`). Does the top of the
   list match your judgment? If not, edit `prompts.csv` or the keyword map, or adjust the weights.
3. Spot-check the AI answers. In SQLite or the report's examples, see what ChatGPT and Gemini actually say about
   the client.

### Every month
- **Refresh facts:** ask each client "anything changed in pricing, features or team?" and update `truth.yaml`. The
  next runs fix pages that are now wrong.
- **Re-check competitor prices** in `competitors.md`. The comparison-page skill uses them.
- **Prune prompts:** drop prompts nobody asks and add new ones from the client's sales calls.
- Check API spend in each provider console against Part I.
- After 2–3 months, `learn_lift.py` replaces the guessed weights with measured ones. Check `C:\geo\logs\lift.log`.

### Offboarding a client
Set `active = false` in `client.toml`. Then:
- Revoke your access: Search Console user, GitHub collaborator, WordPress user/application password, Teams guests.
- Unshare or transfer the Google folder.
- Remove their `WP_*` lines from `.env`.

Keep the ops repo in case they return; it's your record of the work.

---

## Part E: Reference

### Files and folders
```
C:\geo\
  engine\                 the code (shared by all clients)
    settings.toml         global settings          .env   secrets (never share)
    daily.py              scheduled job: collect → plan → run → backup
    collect.py            crawl.py  gsc.py  mentions.py  ai_engines.py  dataforseo.py  gdocs.sync
    planner.py            candidate generation + scoring
    runner.py             Claude sessions, validation loop, PR/draft delivery, approve/reject/changes
    validate.py           deterministic checks
    comms.py              Telegram / Teams / email + admin notifications
    listener.py           always-on bot + reply polling
    weekly_report.py      learn_lift.py   new_client.py   ask_client.py   wp.py   indexnow.py
    telegram_api.py       msgraph.py      google_auth.py  gdocs.py        research.py  db.py  common.py
    skills\               the 12 SKILL.md procedures (copied into each client)
    templates\            files for new clients + questionnaire
  clients\<slug>\
    ops\                  YOUR private repo for this client
      client.toml  CLAUDE.md  worklog.md
      research\  truth.yaml voice.md icp.md competitors.md prompts.csv keyword-map.csv sources\ client-docs\
      out\<task>\         WordPress drafts, notes, specs
      reports\            HTML copy of each weekly report
      .claude\skills\     this client's copy of the skills
    site\                 the client's website repo (git clients only)
  data\geo.db             SQLite: GSC data, pages, AI answers, tasks, questions, docs
  logs\                   one log per component
```

### What gets collected (daily unless noted)
| Data | Source | Used for |
|---|---|---|
| Site clicks and impressions per day; page per day; query × page (28 days) | Search Console API | Planner, reports, lift learning |
| Index status for 60 pages a day, rotating | URL Inspection API | index-fix tasks |
| Sitemap crawl: status, redirects, title, meta, H1s, words, canonical (weekly, or first run) | crawl.py | page-fixes tasks |
| AI answers: daily prompts every day, all prompts on Mondays, N samples × each engine | ai_engines.py | ai-gap, fact-correction, reports |
| Google rank for keyword-map queries (Mondays, optional) | DataForSEO | reports, your judgment |
| Questionnaire and facts docs | Google Drive | ingest-client-docs tasks |

### How the planner decides (score = opportunity × lift × confidence × boost ÷ effort)
| Signal | Task (skill) | Opportunity |
|---|---|---|
| Query at position 4–20 with ≥ 100 impressions / 28 days | refresh-page (search goal) | extra clicks if it reached position 3 |
| Page CTR < half the expected CTR for its position (≤ 10) | retitle | missing clicks |
| 2+ pages each with ≥ 20% of a query's impressions | cannibalization-review (recommendation only) | 2% of impressions |
| Tracked prompt: client named < 34% of the time, competitors ≥ 50% | refresh-page (AI goal) if `target_url` set, else comparison-page or write-article | 150 × miss rate (× 2 for daily prompts) |
| Fact prompt answered wrongly ≥ half the time | correction-research (boost × 2) | 300 |
| Keyword-map row `planned` with no URL | write-article / comparison-page / build-free-tool (by intent) | 3% of volume |
| Pages in GSC but not indexed after 14 days | index-fix (batch of 10) | 15 per page |
| 404s in sitemap, redirect chains, missing or duplicate titles/meta, H1 ≠ 1 | page-fixes (batch of 15) | 8 per page |

**Filters applied before scoring:**
- No duplicate of an open task.
- Nothing touched in the last 14 days (`cooldown_days`).
- Nothing rejected in the last 30 days.
- Monthly caps from `[limits]`.

### Validator checks (validate.py)
**Hard fails:**
- A price within 80 characters after the brand name that isn't in `truth.yaml`
- Any `claims_forbidden` phrase
- A number matching a `checks:` pattern that differs from `expect`
- A competitor price with no source link in the same paragraph
- Placeholder text (TODO, lorem ipsum, "[insert")
- More than 13 links per 1,000 words
- Missing required front matter
- **Git sites:** a failing `build_cmd` or `test_cmd`

**Warnings** (shown in your review message): statistics with no source link.

Claude must run the validator itself, and the runner runs it again. If it fails, Claude gets the errors and up to
2 tries to fix them; after that the task fails.

### Skills (engine/skills)
| Skill | Produces |
|---|---|
| seo-geo-core | Shared rules (how AI engines pick sources, writing rules, never-do list) |
| onboard-research | truth.yaml, voice, ICP, competitors, prompt set, keyword map (interactive) |
| write-article | New article researched from top results and AI-cited sources |
| refresh-page | Targeted improvement of an existing page (search or AI goal) |
| retitle | New title and meta (3 options in notes) |
| comparison-page | Fair, sourced "alternatives" / "vs" page (client approves through a Google Doc) |
| build-free-tool | Calculator/generator with tests, plus an explainer page |
| page-fixes | Technical fixes, with a table of manual steps |
| index-fix | Diagnosis and fixes for unindexed pages |
| correction-research | Fixes the client's own pages; drafts outreach for third-party errors (never sent automatically) |
| cannibalization-review | Merge / re-target / leave recommendation |
| ingest-client-docs | Folds Google Doc edits into the research files |

### Channel behavior
| | Telegram | Teams | Email |
|---|---|---|---|
| Question appears as | Bot message in the client group | New post in the client's channel | Email from your mailbox, subject "[Q12] Client: …" |
| Client answers by | Replying to that message | Replying in the thread | Replying to the email |
| Picked up | Instantly (long polling) | Within 2 minutes | Within 2 minutes (only the new text of the reply) |
| Other messages | Forwarded to you (if group privacy is off) | Not read | Not read |

---

## Part F: Customizing

- **Add a skill:**
  1. Create `engine/skills/<name>/SKILL.md` with `name` and `description` front matter.
  2. Copy it into existing clients' `ops/.claude/skills/`.
  3. Add a generator in `planner.py` that emits `cand("<name>", …)`.
  4. Add lift and effort values in `settings.toml`.
- **Add a validator rule:** add it in `validate.check_file`. Errors block the change; warnings only show in your
  review.
- **Client-specific numeric rules:** add `checks:` entries in `truth.yaml`. No code needed.
- **Change cadence:** edit the triggers in `scripts/register_tasks.ps1` and re-run it.
- **Track more or fewer engines:** `[mentions] engines`, `samples`, and which keys are in `.env`.
- **Let questions go out without you:** set `[comms] hold_for_review = false`. Not recommended.

---

## Part G: Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Google token missing or revoked" | Re-run `google_auth.py`. If it recurs weekly, the consent screen is still in **Testing**; publish it (A4.4). |
| "Microsoft sign-in needed" | Run `msgraph.py login`. Refresh tokens last about 90 days without use, and tenant policies can shorten that. |
| Graph 403 on Teams | Admin consent not granted (A5.3), or you're not a member of that team. |
| Telegram buttons do nothing | Is the listener running? Check Task Scheduler → \GEO\GEO Listener → History, and `logs\listener.log`. Is `TELEGRAM_ADMIN_ID` your ID? |
| Client replies in Telegram aren't recorded | They must **reply to** the bot's question (swipe or right-click → Reply), or turn group privacy off. |
| "No Telegram group linked" | Send `/link <slug>` in the group, from your account. |
| Task failed: "site repo has uncommitted changes" | Someone edited `clients\<slug>\site` by hand. Commit or discard there, then `/run <slug>`. |
| Task failed: build failed | Run the client's `build_cmd` yourself in `site\`. Fix the dependency or Node version, or blank out `build_cmd`. |
| `gh pr create` fails | `gh auth status`; collaborator access; branch protection rules. |
| WordPress 401 | Wrong application password, or a security plugin blocks the REST API for that user. Allow REST for the Editor user. |
| Page-builder pages (Avada) get mangled | The refresh-page skill writes notes instead when it can't edit safely. Edit those by hand or with the Avada skill. |
| Nothing planned for a client | No data yet (GSC needs a few days), empty prompts and keyword map, or everything is in cooldown. Run `planner.py --dry-run` to see. |
| Mentions all 0 | Check the brand name and `brand_aliases`. Run one prompt by hand in ChatGPT to compare. |
| Spending too much on AI tracking | Lower `samples`, fewer `daily` prompts, fewer engines (Part I). |
| Claude usage limits hit | `tasks_per_run = 1`, more skills on `sonnet` in `model_by_skill`, fewer clients per run, or move to API billing with `max_budget_usd`. |

---

## Part H: Security, compliance, offboarding

- **Secrets** live only in `engine\.env`, `engine\google_client_secret.json`, and `data\*token*`. They're not in
  any repo. Back up `.env` to your password manager.
- **Least privilege:**
  - WordPress Editor (never Admin)
  - GitHub Write on one repo (no org admin)
  - Search Console Full user (not Owner)
  - Graph delegated scopes only
  - Google `drive.file` (the engine sees only files it created)
- **What Claude can do** in a task: read/edit files in that client's folders, search the web, run Python, npm/npx
  and node, and read git status. It cannot commit, push, publish, or message anyone. Your button does that.
  `Bash(python *)` effectively allows arbitrary code, so only install skills you've read.
- **Nothing reaches a client** without your tap (questions, reports), except "Shipped: …" notices after *you*
  approve a change (turn off with `announce_shipped = false`).
- **No astroturfing, no fake reviews, no ranking guarantees.** These are written into every skill and the
  contract.
- **Regulated clients (credit unions, banks):**
  - Add rate/APY wording rules and required disclosures to `truth.yaml` (`claims_forbidden`, `checks`).
  - Put **every** content skill in `client_must_approve` so their compliance officer signs off in the Google Doc.
- **Client data:**
  - It stays on your PC, in the client's own repos, and in Google Docs you share with them.
  - AI answers sampled from engines are public-style answers, not client data.
  - Don't put client customer data in prompts.

---

## Part I: Costs and capacity

**AI-answer tracking cost per client per week** ≈ answers × price per answer:
- Answers per week = (daily prompts × 6 days + all prompts) × engines × samples.
- Defaults (5 daily, 40 total, 4 engines, 3 samples): (30 + 40) × 12 = **840 answers/week**.
- At roughly 1–3¢ per search-grounded answer, that's **$8–25/week per client**.
- Lean start (5 daily, 40 total, 2 engines incl. Gemini's free tier, 2 samples): 280 answers/week, about
  **$2–6/week per client**.
- Check each provider's current pricing; search-tool charges change.

**Claude:**
- With `tasks_per_run = 1`, each client gets up to 3 task sessions a day.
- Opus for content, Sonnet for routine work. A Max plan covers a handful of clients. At 20–30 clients, expect to
  use API billing or several seats; track `cost_usd` per task in the database.

**Your time is the real limit:**
- Each review takes 1–2 minutes. At 3 tasks/day/client, that's about 5 minutes per client per day: 10 clients
  ≈ 1 hour/day, 30 clients ≈ 2.5 hours/day, plus Monday reports.
- **Hire an editor** before raising `tasks_per_run`. Give them their own Telegram account and add a second
  admin ID. That's a small code change in `listener.py`.

**Pricing anchor (from the video):** FirstIndex charges $1,500/month (12-month term) or $2,000/month
(month-to-month after 3 months). Start lower for your first 3–5 clients in exchange for a case study.

---

## Command cheat sheet
(`run` = `C:\geo\.venv\Scripts\python`, from `C:\geo\engine`)

| Do this | Command |
|---|---|
| New client | `run new_client.py <slug> --name … --domain … (--git-repo URL / --wordpress URL) --gsc … --contacts … --channels … --competitors …` |
| Pull data now | `run collect.py --client <slug> --force [--full]` |
| See what it would do | `run planner.py --client <slug> --dry-run` |
| Run tasks now | `run runner.py --client <slug>` (or `/run <slug>` in Telegram) |
| Re-run one task | `run runner.py --task <id>` |
| Check a file | `run validate.py --client <slug> --files path\to\post.md` / `--git` |
| Questionnaire / facts doc | `run gdocs.py questionnaire --client <slug>` / `run gdocs.py facts --client <slug>` |
| Report now | `run weekly_report.py --client <slug>` |
| Teams IDs | `run msgraph.py teams` |
| Re-sign in | `run google_auth.py` / `run msgraph.py login` |
| Look at the database | `sqlite3 C:\geo\data\geo.db` (or DB Browser for SQLite, free) |

---

## What was tested (Oct 21, 2026, on WINAI5)
- **39 automated checks passed** with every external API mocked:
  - client creation; parsing each AI engine's response format; mention scoring and wrong-fact detection
  - all 7 planner signals, plus "wrong facts rank first" and no duplicate tasks
  - questions held for your Send button → Telegram reply → task resumes with the answer
  - client approval replies; reviewer change requests
  - every validator rule; WordPress block-markup handling; the weekly report; lift learning
  - database backup; the crawler's HTML parsing
- **Live Claude Code check:** the runner's exact headless command edited a file through `--add-dir`, saw the
  task's client and task IDs, and resumed the same session afterwards.
- **Git delivery check** (using a local repo in place of GitHub; the `gh` call was simulated): it created branch
  `geo/<id>-<title>`, committed, pushed, recorded the PR, and sent the review message with buttons.
- **Not yet run against live services** (they need your accounts): Search Console, Google Drive/Docs, Microsoft
  Graph (Teams/Outlook), the Telegram API, the AI engine APIs, DataForSEO, WordPress REST, and `gh pr create` and
  `gh pr merge`. Part B is designed as that first live test, on your own site.
