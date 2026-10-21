---
name: seo-geo-core
description: Core rules for search (SEO) and AI-answer visibility (AEO/GEO) work on this client. Read before any content, page-fix, or research task; other GEO skills build on it.
---
# SEO + AI-visibility core rules

## Read first, every task
- `research/truth.yaml`: the only source of product facts.
- `research/voice.md`, `research/icp.md`, `research/competitors.md`.
- `research/keyword-map.csv`: one primary query per URL.
- `CLAUDE.md` in this folder: client-specific limits.

## How AI engines pick what to say (write for this)
1. They retrieve a handful of pages from a search index (Bing for ChatGPT and Copilot, Google for Gemini and
   AI Overviews, their own index for Perplexity), then summarize. So you must be **findable**: indexed, ranking,
   linked from the site's main pages.
2. They quote passages that answer the question directly. Put the answer in the **first 2 sentences** under a
   heading phrased like the question. Plain declarative sentences, no throat-clearing.
3. They favor **clear entities**. Say "<Brand> is a <category> for <audience>" verbatim somewhere on key pages.
   Use the same product name every time.
4. They trust **specifics with sources**: numbers, dates, named standards, links to primary sources.
5. They repeat what **many sites** say. That's why third-party mentions and fixing wrong facts elsewhere matter.

## Writing rules
- Answer first, then explain. Short paragraphs. Descriptive H2/H3 headings that match real questions.
- Every product claim must match `truth.yaml`. Missing fact → ask the client (see your task prompt), then stop.
- Competitor claims need a source link and the date you checked. Be fair, and say where they're the better fit.
- Never invent statistics, customers, quotes, reviews, awards, or test results.
- Prefer improving an existing page over creating a new one. Never create two pages for one query.
- Internal links: 3-8 relevant ones per article, with descriptive anchor text, plus one link back from an
  existing related page to any new page (so it gets crawled).
- Add or keep structured data where the site supports it: Article (author, dates), FAQPage only for real
  on-page Q&A, Product/SoftwareApplication where relevant, Organization on the home page.
- Titles: under ~60 characters, primary query near the front, brand at the end if room. Meta descriptions:
  140-160 characters, state the answer or benefit, no clickbait.

## Never
- Reddit, forum or social astroturfing; fake reviews; hidden text; doorway pages; mass-produced thin pages.
- Promises of rankings or AI mentions in anything client-facing.
