"""Create the manual-install integration ZIP from source, with no runtime files."""

import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
component = root / "custom_components/fish_live3"
destination = root / "dist"
destination.mkdir(exist_ok=True)
with zipfile.ZipFile(destination / "fish_live3.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(component.rglob("*")):
        if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc":
            archive.write(file, file.relative_to(component.parent))
print("Built dist/fish_live3.zip")
