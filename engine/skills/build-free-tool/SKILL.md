---
name: build-free-tool
description: Build a small free tool (calculator, generator, checker, template) on the client's site that people search for and AI assistants recommend, with tests and an explainer. Use for GEO tasks of type build-free-tool.
---
# Build a free tool

1. **Spec first.** Write `out/<task>/spec.md` covering:
   - who searches for this and what input and output they expect
   - the formula or logic, with sources
   - edge cases
   - what the top-ranking existing tools do and what's missing from them

   If the logic depends on a product fact or a regulated number (rates, fees, tax), it must come from
   truth.yaml or a cited official source.
2. **Git sites.** Build it as a component or page in the site's framework, matching existing code style.
   - Pure functions for the math, with unit tests next to them (follow the repo's test setup; if there is
     none, add the lightest option the stack supports and note it).
   - Accessible: labeled inputs, keyboard usable, results announced (aria-live), works without login.
   - No external calls or tracking beyond what the site already uses.
   - Run the tests and the build (`npm test`, `npm run build`, or the repo's equivalents) until they pass.
3. **WordPress sites.** Write a self-contained HTML+JS snippet to `out/<task>/tool.html` (no external
   libraries; scoped CSS), plus the explainer in `out/<task>/post.md` with `format: html` and the snippet
   embedded in a Custom HTML block (`<!-- wp:html -->...<!-- /wp:html -->`).
4. **Explainer.** Around the tool, write a short page:
   - what it calculates
   - how to use it
   - the method, with sources
   - an FAQ
   - a link to the client's product where relevant
5. Add it to the keyword map (intent `tool`). Validate.
