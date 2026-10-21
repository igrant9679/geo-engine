# Client: {{NAME}} ({{DOMAIN}})

You are doing search and AI-visibility work for this one client. Everything you need is in this folder.

- Facts: `research/truth.yaml` is the ONLY source of product facts (prices, features, numbers, customers).
  Never invent facts, statistics, customers, quotes or reviews. If a fact is missing, ask the client with the
  `ask_client.py` command given in your task prompt, then stop.
- Voice: `research/voice.md`. Audience: `research/icp.md`. Competitors: `research/competitors.md`.
- Keyword map: `research/keyword-map.csv`, one primary query per URL. Never create a page whose main query is
  already mapped to another URL; improve that page instead. Add new pages you create to the map.
- AI prompts we track: `research/prompts.csv`.
- Research you gather for a task: save summaries and source URLs under `research/sources/<task-id>/`.
- Log every change in `worklog.md` (one line: date, task #, what changed, metric to watch).
- Site kind: {{KIND}}. For git sites, edit only the site repo you were given; never touch product/app code,
  legal pages, or the pricing page unless the task says so. For WordPress, write to `out/<task-id>/post.md`.
- No Reddit/forum posting, no fake reviews, no astroturfing, no promises of rankings.
