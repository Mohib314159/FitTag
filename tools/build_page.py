"""Assemble docs/index.html from web_src/app.html + docs/data/samples.json (data inlined,
so the page is a single static file plus images — no server, no fetch)."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
app = (ROOT / "web_src" / "app.html").read_text()
data = (ROOT / "docs" / "data" / "samples.json").read_text().replace("</", "<\\/")
body = app.replace("/*DATA*/", data)
(ROOT / "docs" / "fragment.html").write_text(body)          # used for the claude.ai preview
(ROOT / "docs" / "index.html").write_text(
    '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n' + body + "\n</html>\n")
(ROOT / "docs" / ".nojekyll").write_text("")
print("docs/index.html written")
