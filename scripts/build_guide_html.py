"""Build GUIDE.html (one self-contained page: sidebar contents, copy buttons, dark mode, print-friendly)
from GUIDE.md. Re-run after editing GUIDE.md:

    C:\\geo\\.venv\\Scripts\\python C:\\geo\\scripts\\build_guide_html.py
    ... build_guide_html.py --artifact <out.html>   page body for a hosted claude.ai artifact (no print button)

Needs markdown-it-py (CommonMark, so code blocks inside numbered steps render correctly):
    C:\\geo\\.venv\\Scripts\\python -m pip install markdown-it-py
"""
import datetime as dt
import html
import pathlib
import re

from markdown_it import MarkdownIt

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "GUIDE.md", ROOT / "GUIDE.html"

CSS = """
:root{--bg:#fbfaf7;--panel:#ffffff;--text:#1d1f23;--muted:#5d6470;--line:#e4e1d9;--accent:#1f5fbf;--accent-soft:#e8effb;
--code-bg:#f3f1ec;--code-text:#1d1f23;--pre-bg:#16181d;--pre-text:#e8e6e1;--callout:#fff7e0;--callout-line:#e0b84a;--th:#f1efe9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121418;--panel:#191c21;--text:#e6e4df;--muted:#a1a7b0;
--line:#2b3038;--accent:#7fb0ff;--accent-soft:#1c2a40;--code-bg:#232830;--code-text:#e6e4df;--pre-bg:#0c0e11;--pre-text:#e6e4df;
--callout:#2a2414;--callout-line:#a8862e;--th:#1f2329;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#121418;--panel:#191c21;--text:#e6e4df;--muted:#a1a7b0;--line:#2b3038;--accent:#7fb0ff;
--accent-soft:#1c2a40;--code-bg:#232830;--code-text:#e6e4df;--pre-bg:#0c0e11;--pre-text:#e6e4df;--callout:#2a2414;--callout-line:#a8862e;--th:#1f2329;color-scheme:dark}
:root[data-theme="light"]{color-scheme:light}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:16px}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,
"Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-underline-offset:2px}
.layout{display:grid;grid-template-columns:290px minmax(0,1fr);max-width:1240px;margin:0 auto}
nav.toc{position:sticky;top:env(safe-area-inset-top,0px);align-self:start;height:100vh;overflow:auto;padding:28px 18px 40px 24px;border-right:1px solid var(--line);font-size:14px}
nav.toc .brand{font-weight:700;font-size:15px;margin:0 0 4px}
nav.toc .sub{color:var(--muted);font-size:12.5px;margin:0 0 18px}
nav.toc ol{list-style:none;margin:0;padding:0}
nav.toc li a{display:block;padding:4px 8px;border-radius:6px;color:var(--text);text-decoration:none;line-height:1.35}
nav.toc li a:hover{background:var(--accent-soft)}
nav.toc li.h3 a{padding-left:22px;color:var(--muted);font-size:13px}
nav.toc li a.active{background:var(--accent-soft);color:var(--accent);font-weight:600}
.tools{display:flex;gap:8px;margin:0 0 16px}
.tools button{font:inherit;font-size:12.5px;padding:5px 10px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--text);cursor:pointer}
main{padding-block:40px 80px;padding-left:max(48px,env(safe-area-inset-left,0px));
padding-right:max(48px,env(safe-area-inset-right,0px));max-width:900px;min-width:0}
header.top h1{font-size:34px;line-height:1.2;margin:0 0 6px;letter-spacing:-.01em}
header.top .meta{color:var(--muted);font-size:14px;margin:0 0 28px}
h2{font-size:25px;line-height:1.3;margin:56px 0 14px;padding-top:12px;border-top:1px solid var(--line)}
h3{font-size:19px;margin:34px 0 10px}
h2 .anchor,h3 .anchor{opacity:0;margin-left:8px;font-weight:400;text-decoration:none}
h2:hover .anchor,h3:hover .anchor{opacity:.6}
p,li{max-width:76ch}
li{margin:4px 0}
li>p{margin:6px 0}
hr{display:none}
code{font-family:ui-monospace,"Cascadia Code",Consolas,"SF Mono",Menlo,monospace;font-size:.88em;background:var(--code-bg);color:var(--code-text);
padding:.12em .38em;border-radius:5px;overflow-wrap:anywhere}
.codebox{position:relative;margin:12px 0 18px}
pre{margin:0;background:var(--pre-bg);color:var(--pre-text);padding:16px 18px;border-radius:10px;overflow-x:auto;font-size:13.5px;line-height:1.5}
pre code{background:none;color:inherit;padding:0;font-size:inherit;overflow-wrap:normal}
.copy{position:absolute;top:8px;right:8px;font:12px/1 inherit;font-family:inherit;padding:6px 9px;border-radius:6px;border:1px solid #3a3f48;
background:#22262d;color:#e6e4df;cursor:pointer;opacity:0;transition:opacity .15s}
.codebox:hover .copy,.copy:focus-visible{opacity:.9}
.copy:hover{opacity:1}
@media (hover:none){.copy{opacity:.85}}
.table-wrap{overflow-x:auto;margin:14px 0 20px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:14.5px}
th,td{text-align:left;vertical-align:top;padding:9px 12px;border-bottom:1px solid var(--line)}
th{background:var(--th);font-weight:600}
tr:last-child td{border-bottom:none}
blockquote{margin:16px 0;padding:12px 16px;background:var(--callout);border-left:4px solid var(--callout-line);border-radius:0 8px 8px 0}
blockquote p{margin:4px 0}
footer{margin-top:64px;color:var(--muted);font-size:13px;border-top:1px solid var(--line);padding-top:16px}
details.mobile-toc{display:none}
@media (max-width:900px){
 .layout{display:block}
 nav.toc{display:none}
 details.mobile-toc{display:block;margin:0 0 24px;border:1px solid var(--line);border-radius:10px;background:var(--panel);padding:10px 14px}
 details.mobile-toc summary{cursor:pointer;font-weight:600}
 details.mobile-toc ol{list-style:none;padding:8px 0 0;margin:0}
 details.mobile-toc li.h3{padding-left:14px;font-size:14px}
 main{padding-block:24px 60px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
 header.top h1{font-size:27px}
 h2{font-size:22px}
}
@media print{
 nav.toc,details.mobile-toc,.copy,.tools{display:none!important}
 .layout{display:block}
 main{max-width:none;padding:0}
 body{background:#fff;color:#000;font-size:11pt}
 pre{background:#f4f4f4;color:#000;white-space:pre-wrap;border:1px solid #ddd}
 a{color:#000}
 h2{break-after:avoid}
 .codebox,.table-wrap,tr{break-inside:avoid}
}
"""

JS = """
document.querySelectorAll('main pre').forEach(pre=>{
  const box=document.createElement('div');box.className='codebox';pre.parentNode.insertBefore(box,pre);box.appendChild(pre);
  const b=document.createElement('button');b.className='copy';b.type='button';b.textContent='Copy';
  b.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(pre.innerText.replace(/\\n$/,''));b.textContent='Copied';}
    catch(e){b.textContent='Select + Ctrl+C';}setTimeout(()=>b.textContent='Copy',1600);});
  box.appendChild(b);
});
const links=[...document.querySelectorAll('nav.toc a[href^="#"]')];
const byId=Object.fromEntries(links.map(a=>[a.getAttribute('href').slice(1),a]));
const heads=[...document.querySelectorAll('main h2[id],main h3[id]')];
function spy(){let cur=heads[0];for(const h of heads){if(h.getBoundingClientRect().top<120)cur=h;else break;}
  links.forEach(a=>a.classList.remove('active'));const a=cur&&byId[cur.id];if(a){a.classList.add('active');
  const r=a.getBoundingClientRect(),n=a.closest('nav').getBoundingClientRect();if(r.top<n.top||r.bottom>n.bottom)a.scrollIntoView({block:'nearest'});}}
document.addEventListener('scroll',spy,{passive:true});spy();
document.querySelectorAll('details.mobile-toc a').forEach(a=>a.addEventListener('click',()=>a.closest('details').open=false));
const root=document.documentElement;
function setTheme(t){if(t)root.setAttribute('data-theme',t);else root.removeAttribute('data-theme');try{t?localStorage.setItem('guide-theme',t):localStorage.removeItem('guide-theme')}catch(e){}}
try{const t=localStorage.getItem('guide-theme');if(t)root.setAttribute('data-theme',t)}catch(e){}
document.getElementById('theme').addEventListener('click',()=>{const dark=root.getAttribute('data-theme')==='dark'||
  (!root.getAttribute('data-theme')&&matchMedia('(prefers-color-scheme: dark)').matches);setTheme(dark?'light':'dark');});
const pr=document.getElementById('print');if(pr)pr.addEventListener('click',()=>window.print());
"""


def slugger():
    used = set()

    def slug(text):
        base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "section"
        s, i = base, 2
        while s in used:
            s, i = f"{base}-{i}", i + 1
        used.add(s)
        return s
    return slug


def build(out=OUT, artifact=False):
    src = SRC.read_text(encoding="utf-8")
    src = re.sub(r"\n## Contents\n.*?\n---\n", "\n", src, count=1, flags=re.S)  # the sidebar replaces it

    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    tokens = md.parse(src)
    slug, toc, title = slugger(), [], "Guide"
    for i, t in enumerate(tokens):
        if t.type != "heading_open":
            continue
        plain = re.sub(r"[*`]", "", tokens[i + 1].content).strip()
        if t.tag == "h1":
            title = plain
            continue
        sid = slug(plain)
        t.attrSet("id", sid)
        if t.tag in ("h2", "h3"):
            toc.append((t.tag, sid, plain))

    body = md.renderer.render(tokens, md.options, {})
    body = re.sub(r"<h1>.*?</h1>\s*", "", body, count=1, flags=re.S)
    body = re.sub(r'(<h([23]) id="([^"]+)">)(.*?)(</h\2>)', r'\1\4<a class="anchor" href="#\3" aria-label="Link to this section">#</a>\5', body)
    body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    body = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener"', body)

    items = "\n".join(f'<li class="{tag}"><a href="#{sid}">{html.escape(text)}</a></li>' for tag, sid, text in toc)
    built = dt.date.today().strftime("%B %d, %Y").replace(" 0", " ")
    print_btn = "" if artifact else '<button id="print" type="button">Print / PDF</button>'
    content = f"""<div class="layout">
<nav class="toc" aria-label="Contents">
  <p class="brand">GEO Engine Guide</p>
  <p class="sub">Build and run instructions</p>
  <div class="tools"><button id="theme" type="button">Light / dark</button>{print_btn}</div>
  <ol>{items}</ol>
</nav>
<main>
<header class="top"><h1>{html.escape(title)}</h1>
<p class="meta">Updated {built} · source: GUIDE.md in <a href="https://github.com/igrant9679/geo-engine" target="_blank" rel="noopener">igrant9679/geo-engine</a></p></header>
<details class="mobile-toc"><summary>Contents</summary><ol>{items}</ol></details>
{body}
<footer>Generated from GUIDE.md by scripts/build_guide_html.py. Edit the Markdown, then re-run the script.</footer>
</main>
</div>
<script>{JS}</script>
"""
    head = """<title>GEO Engine Guide</title>
<meta name="claude:viewport-fit-sides" content="cover">
<meta name="description" content="Build and run guide for the one-person AI-visibility and SEO service engine.">"""
    if artifact:  # the artifact host adds doctype/html/head/body itself
        page = f"{head}\n<style>{CSS}</style>\n{content}"
    else:
        page = (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                f"{head}\n<style>{CSS}</style>\n</head>\n<body>\n{content}</body>\n</html>\n")
    pathlib.Path(out).write_text(page, encoding="utf-8")
    return len(toc)


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--artifact":
        print(f"Wrote {sys.argv[2]} ({build(sys.argv[2], artifact=True)} sections)")
    else:
        print(f"Wrote {OUT} ({build()} sections)")
