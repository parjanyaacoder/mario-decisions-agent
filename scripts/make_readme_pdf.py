#!/usr/bin/env python3
"""Render README.md to a styled, self-contained PDF using headless Chrome.

    uv pip install -e ".[docs]"
    python scripts/make_readme_pdf.py                 # -> docs/mario-decisions-agent.pdf
    python scripts/make_readme_pdf.py --open          # and open it when done

Needs the ``markdown`` package and Google Chrome (or Chromium). Inline images
(GIFs, SVGs) resolve relative to the README's folder.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  color: #1f2328; margin: 0 auto; max-width: 880px; padding: 48px 44px 64px;
}
h1 { font-size: 2.1em; margin: 0 0 .2em; }
h2 { font-size: 1.5em; margin: 1.9em 0 .5em; padding-bottom: .25em; border-bottom: 1px solid #e5e7eb; }
h3 { font-size: 1.2em; margin: 1.4em 0 .4em; }
a { color: #0969da; text-decoration: none; }
code {
  font: .88em/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: #f3f4f6; padding: .15em .35em; border-radius: 4px;
}
pre { background: #f6f8fa; border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px 16px; overflow: auto; }
pre code { background: none; padding: 0; font-size: .82em; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #d7dbe0; padding: 7px 10px; text-align: left; }
th { background: #f6f8fa; }
blockquote { margin: 1em 0; padding: .6em 1em; border-left: 4px solid #d0d7de; background: #f6f8fa; color: #3d444d; }
img { max-width: 100%; height: auto; }
hr { border: none; border-top: 1px solid #e5e7eb; margin: 2.2em 0; }
.center { text-align: center; }
@media print {
  body { max-width: none; padding: 0 10mm; font-size: 14px; }
  h2, h3 { break-after: avoid; }
  table, pre, img, blockquote { break-inside: avoid; }
  a { color: #1f2328; }
}
"""

CHROME_PATHS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)


def find_chrome() -> str:
    for path in CHROME_PATHS + tuple(shutil.which(n) or "" for n in (
        "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    )):
        if path and os.path.exists(path):
            return path
    raise SystemExit("Google Chrome / Chromium not found; required to print the PDF.")


def build_html(readme_text: str, base_dir: str) -> str:
    import markdown

    # GitHub renders markdown inside bare <div>/<p> wrappers; python-markdown needs
    # the md_in_html extension and an explicit markdown="1" opt-in.
    text = readme_text.replace('<div align="center">', '<div class="center" markdown="1">')
    text = text.replace('<p align="center">', '<p class="center" markdown="1">')
    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list", "md_in_html", "toc"],
    )
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<title>mario-decisions-agent</title>"
        f'<base href="file://{base_dir}/">'
        f"<style>{CSS}</style></head><body>{body}</body></html>"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--readme", default="README.md")
    ap.add_argument("--out", default="docs/mario-decisions-agent.pdf")
    ap.add_argument("--html-out", default="", help="keep the intermediate HTML here")
    ap.add_argument("--open", action="store_true", dest="open_pdf",
                    help="open the PDF when finished")
    args = ap.parse_args()

    base_dir = os.path.dirname(os.path.abspath(args.readme))
    with open(args.readme, encoding="utf-8") as fh:
        html = build_html(fh.read(), base_dir)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    tmp_dir = tempfile.mkdtemp(prefix="mdapdf-")
    html_path = args.html_out or os.path.join(tmp_dir, "readme.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    out = os.path.abspath(args.out)
    cmd = [
        find_chrome(),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--allow-file-access-from-files",
        "--virtual-time-budget=15000",
        f"--print-to-pdf={out}",
        f"file://{html_path}",
    ]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode != 0 or not os.path.exists(out):
        raise SystemExit("Chrome failed to print the PDF")

    print(f"wrote {args.out} ({os.path.getsize(out) // 1024} KB)")
    if args.open_pdf:
        subprocess.run(["open", out], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
