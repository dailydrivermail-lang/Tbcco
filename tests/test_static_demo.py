import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_static_demo_builds_with_no_broken_links_or_live_forms():
    subprocess.run([sys.executable, str(ROOT / "deploy" / "build_static_demo.py")], check=True, capture_output=True)
    site = ROOT / "deploy" / "site"
    assert (site / "index.html").is_file() and (site / "_headers").is_file()
    for f in site.rglob("*.html"):
        html = f.read_text(encoding="utf-8")
        assert 'method="post"' not in html and "csrf_token" not in html, f
        assert "noindex" in html, f
        for url in re.findall(r'(?:href|action)="(/[^"?]*)', html):
            t = site / url.lstrip("/")
            assert t.is_file() or (t / "index.html").is_file(), f"{f}: broken {url}"
