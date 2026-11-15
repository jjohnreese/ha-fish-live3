"""Collect license texts for the exact packages installed by npm ci."""

import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
packages = root / "frontend/node_modules"
sections = []
for package_json in sorted(packages.rglob("package.json")):
    if "node_modules" not in package_json.parts:
        continue
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        continue
    if not data.get("name") or not data.get("version"):
        continue
    heading = f"{data['name']} {data['version']} — {data.get('license', 'See package license')}"
    texts = []
    for file in sorted(package_json.parent.iterdir()):
        if file.is_file() and file.name.lower().startswith(
            ("license", "licence", "copying", "notice")
        ):
            texts.append(file.read_text(encoding="utf-8", errors="replace"))
    sections.append(
        heading
        + "\n"
        + "=" * len(heading)
        + "\n"
        + ("\n\n".join(texts) or "See the package source for its license.")
    )
target = root / "third_party/npm-licenses.txt"
target.parent.mkdir(exist_ok=True)
target.write_text(
    "Frontend dependency licenses\n\n" + "\n\n".join(sections) + "\n", encoding="utf-8"
)
print(f"Collected {len(sections)} package license notices")
