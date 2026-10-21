---
name: comparison-page
description: Create or improve an "alternatives to X" or "<client> vs X" page that is fair, sourced, and useful to buyers comparing options. Use for GEO tasks of type comparison-page.
---
# Comparison page

These pages win AI answers only when they're credible. Biased pages get ignored, and wrong claims about a
competitor are a legal risk.

1. Identify the format from the task: "alternatives to <competitor>" (list, client included) or
   "<client> vs <competitor>" (head-to-head).
2. For each competitor covered, fetch their current pricing and feature pages. Record facts with the URL and
   today's date in `research/competitors.md` and `research/sources/<task-id>/`.
3. Structure:
   - A two-sentence verdict: who each option is best for.
   - A comparison table (features, pricing, best for). Each competitor cell is sourced, with a footnote
     linking to the source and the "checked on" date.
   - Sections on key differences, migration (how to switch), and when to choose the competitor (be honest),
     then an FAQ.
4. Client facts come only from truth.yaml. No disparaging language. Neutral verbs ("offers", "doesn't list").
5. Place it like a new article (see write-article). Add it to the keyword map with intent `comparison`.
6. Validate. These pages usually need client approval; the runner handles that automatically.
