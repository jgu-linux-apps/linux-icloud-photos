import os
import sys
from pathlib import Path

# README w katalogu głównym repozytorium (strona projektu na GitHubie) musi być taki sam jak src/README.md
# (z niego budowana jest paczka i notatki do wydań) - między 0.17.5 a 1.0.3 rozjechały się niezauważone.
root = Path(os.environ["PROJECT_ROOT"])
sys.path.insert(0, str(root))
import version  # noqa: E402

a, b = root / "README.md", root.parent / "README.md"
print("readme_in_sync ->", (not b.exists()) or a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8"))
print("readme_version_matches ->", f"Current version: {version.VERSION} (" in a.read_text(encoding="utf-8"))
