"""Bundle the static portal demo into ONE self-contained HTML file (fictional data only).

    python deploy/build_static_demo.py      # builds deploy/site/
    python deploy/build_single_file.py      # writes deploy/portal-demo.html

Open the file in any browser, or email it. Everything is inlined: styles, font, scripts and every page.
Links switch pages inside the file. PDF downloads are not included.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "deploy" / "site"
OUT = ROOT / "deploy" / "portal-demo.html"

ROUTER = r"""
(function () {
  var PAGES = JSON.parse(document.getElementById("pages").textContent);
  function norm(p) { p = (p || "/").split("?")[0].split("#")[0]; if (p.slice(-1) !== "/" && !/\.[a-z0-9]+$/i.test(p)) p += "/"; return p; }
  function show(path) {
    path = norm(path);
    var page = PAGES[path];
    if (!page) {
      page = PAGES["/demo-not-saved/"];
      if (/\.pdf$/i.test(path)) page = { title: "Not included", body: page.body.replace(/<h2>[\s\S]*?<\/div>\s*$/, "") + '<h2>PDF not included</h2><p class="muted">Downloads are left out of the single-file demo. The live demo site has them.</p><div class="choice-cards"><a class="btn btn-primary btn-lg" href="/">Back to the demo</a></div></div></section></div>' };
    }
    document.title = page.title;
    document.body.innerHTML = page.body;
    window.scrollTo(0, 0);
    if (document.getElementById("assess-data")) window.__runWizard();
    window.__runApp();
  }
  function go(path) { location.hash = "#" + norm(path); }
  document.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("a[href]") : null;
    if (!a) return;
    var h = a.getAttribute("href");
    if (h.charAt(0) === "/") { e.preventDefault(); go(h); }
  });
  document.addEventListener("submit", function (e) { e.preventDefault(); go(e.target.getAttribute("action") || "/demo-not-saved/"); });
  HTMLFormElement.prototype.submit = function () { go(this.getAttribute("action") || "/demo-not-saved/"); };
  window.addEventListener("hashchange", function () { show(location.hash.slice(1)); });
  show(location.hash.slice(1) || "/");
})();
"""


def main():
    css = (SITE / "static" / "portal.css").read_text(encoding="utf-8")
    font = base64.b64encode((SITE / "static" / "fonts" / "inter-latin-wght-normal.woff2").read_bytes()).decode()
    css = css.replace('url("fonts/inter-latin-wght-normal.woff2")', f'url("data:font/woff2;base64,{font}")')
    js = {n: (SITE / "static" / "js" / n).read_text(encoding="utf-8") for n in ("assessment-engine.js", "wizard.js", "app.js")}
    pages = {}
    for f in sorted(SITE.rglob("index.html")):
        html = f.read_text(encoding="utf-8")
        body = re.search(r"<body[^>]*>(.*)</body>", html, re.S).group(1)
        body = re.sub(r'<script[^>]*\bsrc="[^"]*"[^>]*>\s*</script>', "", body)
        title = re.search(r"<title>(.*?)</title>", html, re.S).group(1).strip()
        path = "/" + f.parent.relative_to(SITE).as_posix() + "/"
        pages["/" if path == "/./" else path] = {"title": title, "body": body}
    data = json.dumps(pages).replace("</", "<\\/")
    out = f"""<!doctype html>
<html lang="en-AU"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>Compliance Portal demo</title>
<style>{css}</style></head>
<body><noscript>This demo needs JavaScript.</noscript></body>
<script type="application/json" id="pages">{data}</script>
<script>{js["assessment-engine.js"]}</script>
<script>window.__runWizard = function () {{ {js["wizard.js"]} }}; window.__runApp = function () {{ {js["app.js"]} }};</script>
<script>{ROUTER}</script>
</html>"""
    OUT.write_text(out, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(pages)} pages, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
