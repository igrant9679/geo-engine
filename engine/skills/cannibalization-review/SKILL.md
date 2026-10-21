---
name: cannibalization-review
description: Recommend how to resolve two or more pages competing for the same search query (merge, redirect, re-target, or leave). Recommendation only; makes no site changes. Use for GEO tasks of type cannibalization-review.
---
# Pages competing for one query

1. Read every page in the context and compare intent, depth, links and age.
2. Search the query: does Google want one page type (guide, product page, list)?
3. Recommend one option per page:
   - **merge** into the strongest page, then 301 the others
   - **re-target** a page to a different query (suggest one from the keyword map gaps)
   - **leave** it, if the pages serve genuinely different intents and both rank
4. Write the recommendation, with reasons and the exact steps, to `out/<task>/notes.md`. Update
   `research/keyword-map.csv` notes only. Make no site changes in this task.
