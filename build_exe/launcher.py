"""Ponto de entrada do .exe (o PyInstaller precisa de um script com importação absoluta)."""
import sys

from kerbhud.cli import main

if __name__ == "__main__":
    # No .exe sem console, sys.stdout/sys.stderr são None: um print() solto não pode derrubar o programa.
    import io
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, io.StringIO())
    raise SystemExit(main())
