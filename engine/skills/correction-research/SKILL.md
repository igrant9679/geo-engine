---
name: correction-research
description: When AI assistants state wrong facts about the client (price, features, status), find the sources feeding the error, fix the client's own pages, and draft correction requests for third-party sites. Use for GEO tasks of type correction-research.
---
# Correct wrong facts in AI answers

The context has the prompt, the regex a correct answer must match, the wrong answers, and the domains AI cites.

1. **Find the source of the error.** For each cited domain, and by searching the wrong claim itself:
   - Find pages stating the wrong fact. Record URL, exact wrong text and page owner in
     `research/sources/<task-id>/errors.md`.
   - Check the client's own site too. Old blog posts, changelogs and help docs are the usual culprits.
2. **Fix the client's own pages (do this first).**
   - Correct outdated statements in the site repo, or in `post.md` for WordPress.
   - Make sure one canonical page (e.g. /pricing) states the fact plainly in text, not only in an image or
     JS widget, with a "last updated" date.
3. **Draft outreach, but don't send it.** For each third-party page, write in `out/<task>/notes.md`:
   - who to contact and how (contact page, author email, or the review-site profile owned by the client)
   - a short, polite email: what's wrong, the correct fact, and the link to the client's source page
   - for profiles the client controls (G2, Capterra, Crunchbase, LinkedIn, Google Business Profile, app
     marketplaces), the exact fields the client should update
4. Never post anything yourself. A person sends every message.
5. Validate any page edits.
