---
name: onboard-research
description: Build a new client's research foundation (truth.yaml, voice, ICP, competitors, AI prompt set, keyword map) from their website, help docs and questionnaire. Run interactively with the operator during onboarding.
---
# Onboarding research

Work with the operator in the chat. Show drafts before overwriting files.

1. **Ingest the site.** Fetch the sitemap (https://<domain>/sitemap.xml) and read the home, pricing, product or
   features, integrations, about, and customers pages, plus the help-center index and top 10 help articles.
   Save a one-paragraph summary of each with its URL in `research/sources/site/`.
2. **Read the questionnaire** in `research/client-docs/questionnaire.txt` if it exists.
3. **Draft `research/truth.yaml`.** Fill in only facts you saw on the site or in the questionnaire. Put the source
   URL in a YAML comment next to each. List anything uncertain in `research/open-questions.md`.
   Add `checks:` entries for numbers likely to be repeated (integration count, customer count, uptime).
4. **Voice, ICP, competitors.** Fill in `voice.md`, `icp.md` and `competitors.md`. For each competitor, fetch
   their pricing page and record the prices with the URL and today's date.
5. **AI prompt set (`research/prompts.csv`): 30-60 rows**:
   - category: "best <category> for <audience>" variations (10-20). Mark the 5 most valuable `daily`.
   - comparison: "<competitor> alternatives", "<brand> vs <competitor>" (one per main competitor).
   - problem: questions buyers ask before they know the category (10-15).
   - fact: "how much does <brand> cost", "does <brand> integrate with X", "is <brand> SOC 2 compliant".
     Put a regex in `expect` that a correct answer must contain (e.g. `\$19`).
   - Fill `target_url` when an existing page should win that prompt.
6. **Keyword map (`research/keyword-map.csv`).**
   - List every existing indexable page with its primary query (status `live`).
   - Then list gaps: queries buyers search that no page answers (status `planned`, url empty). Set intent to
     info, commercial, comparison or tool.
   - Estimate volume from Search Console data or DataForSEO if available. Otherwise leave it blank.
7. Summarize for the operator what you drafted and the open questions to send the client.
