"""Escreve o texto do Release (changelog PT + EN da versão) num arquivo. Usado pelo workflow .github/workflows/release.yml.

Uso:  PYTHONPATH=src python tools/release_notes.py 0.17.2 Alezin-web/KerbHUD release-notes.md
"""
from __future__ import annotations

import sys
from pathlib import Path

from kerbhud.core.changelog import release_notes

if __name__ == "__main__":
    version, repo, out = sys.argv[1], sys.argv[2], sys.argv[3]
    Path(out).write_text(release_notes(version, repo, Path(__file__).resolve().parents[1]), encoding="utf-8")
    print("notas do release em", out)
