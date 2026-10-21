---
name: ingest-client-docs
description: Fold the client's answers from their Google Docs (questionnaire, facts sheet) into research files. Use for GEO tasks of type ingest-client-docs.
---
# Ingest client document updates

1. Read `research/client-docs/questionnaire.txt` and `research/client-docs/facts.txt` (whichever exist).
2. Compare with `research/truth.yaml`, `voice.md`, `icp.md`, `competitors.md` and `prompts.csv`.
3. Update the research files with what the client wrote.
   - Client statements override your earlier drafts.
   - Keep YAML valid.
   - Add `checks:` entries for any new numeric facts.
   - Add the client's "questions you want AI to answer with your name" to prompts.csv (kind category,
     frequency daily).
4. List every change (old → new) in `out/<task>/notes.md`, plus anything contradictory or unclear. Unclear
   items become one combined question via the ask command in your task prompt.
5. If pricing or features changed, list the site pages that now state outdated facts. The next runs pick them
   up as fix tasks.
