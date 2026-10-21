---
name: page-fixes
description: Fix a batch of technical SEO problems found by the crawler (broken pages in the sitemap, redirect chains, missing or duplicate titles and meta descriptions, wrong H1 count). Use for GEO tasks of type page-fixes.
---
# Technical page fixes

The task context lists `pages` with `problems`. Fix what you can safely; explain the rest.

| Problem | Fix |
|---|---|
| HTTP 4xx/5xx but in sitemap | If the page moved: add a redirect to the best live URL (framework redirect config). If it's gone: remove it from the sitemap source. Never redirect everything to the home page. |
| Redirect chain | Point internal links and redirects straight at the final URL. |
| Missing or duplicate title | Write a unique title (≤ 60 characters) from the page's content and its keyword-map query. |
| Missing meta description | Write one (140-160 characters, facts from truth.yaml). |
| 0 or multiple H1 | Exactly one H1 that matches the title's promise; demote the extras to H2. |

- **Git sites:** make the edits, keeping the diff small and focused.
- **WordPress:**
  - Title and meta changes go in `out/<task>/post.md` (one page per task; list the rest in `notes.md`).
  - Redirects and sitemap fixes go in `out/<task>/notes.md` as exact steps for the reviewer, e.g. "Redirection
    plugin: /old → /new (301)".

Write a summary table (URL | problem | fix | done/manual) in `out/<task>/notes.md`. Validate.
