---
name: refresh-page
description: Improve an existing page so it ranks higher for queries where it sits in positions 4-20, or so AI assistants name the client for a tracked prompt. Use for GEO tasks of type refresh-page.
---
# Refresh an existing page

Follow `seo-geo-core`. The task context says `goal`: `search` (striking-distance queries listed) or
`ai-answers` (a tracked prompt where competitors get named and the client doesn't).

1. Read the current page.
   - Git sites: read the source file.
   - WordPress: find the post ID in the page HTML (e.g. `postid-123` in the body class). Then run
     `python "<engine>/wp.py" fetch --client <slug> --id <ID> --out out/<task>/original.html`
     (the engine path is in your task prompt). This gives the exact stored content, including block markup.
2. **Gap analysis.** Save it to `research/sources/<task-id>/`.
   - Search goal: search each listed query; compare the top 3 results with this page. What questions, sections,
     data or examples do they have that this page lacks? Is the query's intent answered in the first screen?
   - AI goal: ask yourself the prompt with web search and read what gets cited ("sources_ai_cites" in the
     context). What do those pages say that this page doesn't? Is there a quotable sentence that directly
     answers the prompt and names the brand and category?
3. **Edit.** Keep the URL. Keep what works. Make these changes:
   - Make the opening answer the main query directly.
   - Add missing sections and facts (from truth.yaml only), plus a table or list where it helps quoting.
   - Update stale dates and numbers. Show "Updated <month year>" if the site displays dates.
   - Improve the title and meta description if they don't match the queries.
   - Add 2-4 internal links to and from related pages.
   - Don't rewrite for the sake of it: a focused diff is easier to review and to measure.
4. WordPress: write the full updated page to `out/<task>/post.md` with `wp_id` set to the existing post ID and
   `format: html`. Edit the fetched original markup rather than retyping it, so blocks and page-builder
   shortcodes (Avada/Fusion etc.) survive. If the page is built with a page builder and you can't edit it
   safely, write the changes as instructions in `out/<task>/notes.md` instead.
5. Validate with the command in your task prompt.
