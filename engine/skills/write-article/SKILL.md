---
name: write-article
description: Research and write one in-depth article that answers a question the client's buyers search for or ask AI assistants. Use for GEO tasks of type write-article.
---
# Write an article

Follow `seo-geo-core` throughout.

1. **Check the map.** The target query must not already be the primary query of another URL in
   `research/keyword-map.csv`. If it is, stop. Write `out/<task>/notes.md` recommending a refresh of that page.
2. **Research** and save notes plus URLs to `research/sources/<task-id>/`:
   - Search the web for the query and read the top results and any pages the task context lists as
     "sources_ai_cites". Note what they cover, what they miss, and what they get wrong.
   - Read the client's own relevant pages and help docs.
   - Find 2-5 primary sources (standards, official docs, studies) to cite.
3. **Outline.** H1 = the question or a clear promise. Then:
   - The direct answer in 2-3 sentences.
   - H2s that are the follow-up questions a buyer asks, in the order they'd ask them.
   - Where it fits naturally (not forced), a section on how the client's product solves it, with facts only
     from truth.yaml.
   - A short FAQ (3-5 real questions) if useful.
4. **Write** in the client's voice. 1,200-2,500 words unless the question needs less; never pad.
   Add a comparison table if choices are involved. Cite sources inline with links.
5. **Place it.**
   - Git sites: create the file in the content directory, matching existing files' format and front matter
     exactly (look at 2-3 existing posts first).
   - WordPress: write `out/<task>/post.md`.
   - Add internal links from 1-2 existing related pages to the new page (git sites).
   - Add the new URL to `research/keyword-map.csv` with status `live`.
6. **Validate** with the command in your task prompt; fix everything.
