---
name: index-fix
description: Diagnose why pages are not indexed by Google (crawled/discovered but not indexed, noindex, canonical issues) and fix the causes. Use for GEO tasks of type index-fix.
---
# Get pages indexed

For each URL in the task context:
1. Fetch it and check for:
   - a `noindex` meta tag or X-Robots-Tag header
   - a canonical tag pointing elsewhere
   - a robots.txt block
   - whether it appears in the sitemap
   - how many internal links point to it (search the site repo, or the crawl data in your context)
   - thin or duplicate content compared with other pages on the site
2. Fix the causes:
   - Remove an accidental noindex or wrong canonical.
   - Add the URL to the sitemap.
   - Add 2-3 contextual internal links from relevant, well-linked pages.
   - Strengthen thin pages, or recommend merging them into a stronger page with a redirect.
3. Don't "request indexing" for pages that are thin or duplicate. Fix the content first.
4. Write a table (URL | likely cause | fix | done/manual) to `out/<task>/notes.md`. Validate.

(After you approve, the engine pings IndexNow for changed URLs. Google re-crawls from the sitemap and links.)
