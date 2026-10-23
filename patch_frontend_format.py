"""Small safe patch: show 'Not recorded' when requests have no stored date.
Run from the project root after copying this file there, or adjust TARGET below.
"""
from pathlib import Path

TARGET = Path("Frontend/js/app.js")
OLD = "const fmt = d => new Date(d + 'T00:00:00').toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });"
NEW = "const fmt = d => !d ? 'Not recorded' : new Date(d + 'T00:00:00').toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });"

if not TARGET.is_file():
    raise SystemExit(f"Could not find {TARGET}. Run this script from your project root.")
text = TARGET.read_text(encoding="utf-8")
if NEW in text:
    print("Date display patch is already applied; no changes made.")
elif OLD in text:
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("Patched app.js: requests without a stored date now display 'Not recorded'.")
else:
    raise SystemExit("Expected date-format line was not found. No file was changed.")
