#!/usr/bin/env python3
"""Render standalone sub-projects natively inside portfolio pages.

The collage and the diorama were each built as self-contained HTML sites. Rather than
linking out to them (which makes the reader leave the portfolio), this inlines each one
into its portfolio page: the sub-project's CSS is scoped under a wrapper class so it
can't collide with the portfolio stylesheet, its own decorative footer is dropped in
favour of the portfolio footer, and relative media paths are rewritten.

Run from inside the site folder, AFTER copying a fresh build over:
    python3 apply_inline_pages.py
"""
import re
import pathlib

HERE = pathlib.Path(__file__).parent

PAGES = [
    {
        "dest": "who-am-i.html",
        "src": "collage-project/index.html",
        "root": "collage-root",
        "tag": "SPED 854 &middot; Module 1 artifact &mdash; &ldquo;Who Am I?&rdquo;",
        "tag_bg": "#e9dcc2", "tag_fg": "#6b6151", "tag_line": "#cbbb9b",
        "title": "M1 &middot; Who Am I",
    },
    {
        "dest": "diorama.html",
        "src": "diorama-project/index.html",
        "root": "diorama-root",
        "tag": "SPED 854 &middot; Module 2 artifact &mdash; Virtual Diorama",
        "tag_bg": "#eef3fc", "tag_fg": "#4a5568", "tag_line": "#d6e0f0",
        "title": "M2 &middot; Virtual Diorama",
    },
]


def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def scope(css, root):
    """Prefix every selector with `.root` so sub-project styles stay contained."""
    out = []
    i, n = 0, len(css)
    while i < n:
        brace = css.find("{", i)
        if brace == -1:
            break
        head = css[i:brace].strip()

        if head.startswith("@"):
            depth, j = 0, brace
            while j < n:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            inner = css[brace + 1:j]
            if head.startswith("@keyframes"):
                # namespace animation names so two sub-projects can't collide
                head = head.replace("@keyframes ", f"@keyframes {root}-")
                out.append(f"{head}{{{inner}}}")
            else:
                out.append(f"{head}{{{scope(inner, root)}}}")
            i = j + 1
            continue

        close = css.find("}", brace)
        body = css[brace + 1:close]
        parts = []
        for sel in head.split(","):
            sel = sel.strip()
            if not sel:
                continue
            if sel in (":root", "html", "body"):
                parts.append(f".{root}")
            elif sel == "*":
                parts.append(f".{root} *")
            else:
                parts.append(f".{root} {sel}")
        if parts:
            out.append(f"{', '.join(parts)}{{{body}}}")
        i = close + 1
    return "\n".join(out)


def build(cfg):
    src_path = HERE / cfg["src"]
    dest_path = HERE / cfg["dest"]
    src = src_path.read_text(errors="ignore")
    dest = dest_path.read_text(errors="ignore")

    style = re.search(r"<style>(.*?)</style>", src, re.S).group(1)
    body = re.search(r"<body>(.*?)</body>", src, re.S).group(1)
    fonts = "\n".join(re.findall(r"<link[^>]+fonts\.[^>]+>", src))

    # drop the sub-project's decorative footer; the portfolio footer carries contact info
    body = re.sub(r"<footer[^>]*>.*?</footer>", "", body, flags=re.S)

    # rewrite relative media paths so they resolve from the site root.
    # NOTE: must cover every attribute that can carry a path - `poster` was missed once and
    # silently broke the Harriet McBryde Johnson video (it rendered as an empty black box).
    sub_dir = str(pathlib.PurePosixPath(cfg["src"]).parent)
    path_attrs = "src|href|poster|data-src|data-poster|srcset"
    body = re.sub(rf'({path_attrs})="(?!https?:|data:|#|/)([^"]+)"',
                  lambda m: f'{m.group(1)}="{sub_dir}/{m.group(2)}"', body)

    root = cfg["root"]
    # the portfolio stylesheet targets bare elements (blockquote, a, h1-h4, p, li...), which would
    # otherwise bleed into the sub-project. Reset those first; the scoped rules below still win.
    reset = f""".{root} blockquote{{background:none;border:0;border-radius:0;font-style:normal;
color:inherit;padding:0;margin:0}}
.{root} a{{color:inherit;text-decoration:none}}
.{root} h1,.{root} h2,.{root} h3,.{root} h4{{margin:0;font-size:inherit;color:inherit;
line-height:inherit;font-weight:inherit}}
.{root} p,.{root} li{{font-size:inherit;line-height:inherit}}
.{root} ul,.{root} ol{{margin:0;padding:0}}
.{root} .note,.{root} .ref{{background:none;border:0;padding:0;color:inherit;font-size:inherit;
border-radius:0}}
.{root} .card{{background:none;border:0;border-radius:0;padding:0}}
.{root} .button{{background:none;color:inherit;padding:0;border-radius:0;font-weight:inherit;margin:0}}
"""
    scoped = reset + scope(strip_comments(style), root)
    # keep keyframe *references* in sync with the namespaced definitions
    for anim in re.findall(r"@keyframes\s+([A-Za-z0-9_-]+)", strip_comments(style)):
        scoped = re.sub(rf"(animation(?:-name)?\s*:[^;}}]*?)\b{re.escape(anim)}\b",
                        rf"\1{root}-{anim}", scoped)

    sidebar_inner = re.search(r'<aside class="sidebar">(.*?)</aside>', dest, re.S).group(1)
    footer = re.search(r"<footer>.*?</footer>", dest, re.S).group(0)

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{cfg['title']} &middot; Gabe Esquivel</title>
<link rel="stylesheet" href="style.css">
{fonts}
<style>
.inline-wrap{{flex:1;min-width:0}}
.artifact-tag{{font-size:.76rem;letter-spacing:.14em;text-transform:uppercase;font-weight:700;
color:{cfg['tag_fg']};background:{cfg['tag_bg']};border-bottom:1px solid {cfg['tag_line']};
padding:.72rem 1.4rem}}
.{root}{{display:block}}
{scoped}
</style>
</head><body><div class="layout">
<aside class="sidebar">{sidebar_inner}</aside>
<div class="main inline-wrap">
<div class="artifact-tag">{cfg['tag']}</div>
<div class="{root}">
{body}
</div>
{footer}
</div></div></body></html>"""

    dest_path.write_text(page, encoding="utf-8")
    print(f"{cfg['dest']:<18} rebuilt from {cfg['src']} ({len(page):,} chars)")


if __name__ == "__main__":
    for cfg in PAGES:
        build(cfg)
