---
name: retitle
description: Rewrite a page's title tag and meta description when its click-through rate is far below normal for its Google position. Use for GEO tasks of type retitle.
---
# Rewrite title + meta description

1. Read the page and the `top_queries` in the task context. Search the top query and look at the titles of the
   results around this page's position.
2. Write 3 title options (≤ 60 characters, main query near the front, a concrete benefit or specific detail,
   brand at the end if room) and 2 meta descriptions (140-160 characters, answer + reason to click, no
   clickbait, facts from truth.yaml only).
3. Apply the best option:
   - Git sites: change the title/description front matter or SEO fields only.
   - WordPress: write `out/<task>/post.md` with front matter only: title, meta_description, type,
     `wp_id`, and `content_unchanged: true`. The body stays as it is on the site.
4. List all options and your reasoning in `out/<task>/notes.md` so the reviewer can swap one in.
5. Keep the H1 consistent with the new title's promise. Don't change the URL.
6. Validate.
