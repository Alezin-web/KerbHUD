"""Teste de fumaça da interface com PySide6 REAL, sem abrir janelas na tela.

    set PYTHONPATH=src
    python tools/ui_smoke.py

Usa a plataforma Qt "offscreen", sobe o motor em modo DEMO, aplica cada layout
e salva uma imagem de cada módulo em ./ui_smoke_out/. Serve para validar a
renderização e para conferir o visual sem o simulador.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KERBHUD_HOME", tempfile.mkdtemp(prefix="kerbhud_smoke_"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from kerbhud.core.engine import Engine, load_settings  # noqa: E402
from kerbhud.core.history import TelemetryHistory  # noqa: E402
from kerbhud.core.layout import LayoutStore  # noqa: E402
from kerbhud.core.paths import layouts_dir  # noqa: E402
from kerbhud.ui.context import ModuleContext  # noqa: E402
from kerbhud.ui.overlay_manager import OverlayManager  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    cfg = load_settings()
    cfg["simulator"] = "demo"
    engine = Engine(cfg)
    history = TelemetryHistory()
    engine.subscribe(history.on_snapshot)
    engine.start()
    store = LayoutStore(layouts_dir())
    store.ensure_defaults()
    mgr = OverlayManager(engine, store, cfg, ModuleContext(settings=cfg, history=history))
    out = Path("ui_smoke_out")
    out.mkdir(exist_ok=True)
    t0 = time.time()
    while time.time() - t0 < 3.0:  # deixa acumular histórico do DEMO
        app.processEvents()
        time.sleep(0.02)
    for name in store.list_names():
        mgr.switch_layout(name)
        for edit in (False, True):
            mgr.set_edit_mode(edit)
            app.processEvents()
            for mid, w in mgr.windows.items():
                if w.isVisible():
                    path = out / f"{name}_{mid}_{'edit' if edit else 'run'}.png"
                    w.grab().save(str(path))
    mgr.shutdown()
    engine.stop()
    print(f"OK: imagens em {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
