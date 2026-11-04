#!/usr/bin/env python3
"""Fail if any relative Markdown link points at a file that does not exist."""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
LINK = re.compile(r"\[[^\]]+\]\(([^)#]+?)(?:#[^)]*)?\)")
# Text in a code fence or an inline code span is an example, not a link.
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.S)

bad = []
for md in sorted(ROOT.rglob("*.md")):
    if ".git/" in str(md):
        continue
    for m in LINK.finditer(CODE.sub("", md.read_text(encoding="utf-8"))):
        link = m.group(1).strip()
        if link.startswith(("http://", "https://", "mailto:")):
            continue
        if not (md.parent / link).resolve().exists():
            bad.append(f"{md.relative_to(ROOT)}  ->  {link}")

if bad:
    print("Broken relative links:\n  " + "\n  ".join(bad))
    sys.exit(1)
print("All relative links resolve.")
