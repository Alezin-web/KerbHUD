"""Testa a camada Qt (janelas, gerenciador) usando um PySide6 SIMULADO.

Objetivo: pegar erros de lógica/nomes/fluxo no código de UI sem precisar de Qt.
NÃO valida aparência nem comportamento real do Windows; isso exige rodar o app
(`python -m kerbhud run --sim demo`). Se o PySide6 real estiver instalado,
estes testes são pulados.
"""
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

HAVE_QT = importlib.util.find_spec("PySide6") is not None


def _install_stub():
    class Signal:
        def __init__(self, *a): pass
        def __set_name__(self, owner, name): self.name = "_sig_" + name
        def __get__(self, inst, owner=None):
            if inst is None:
                return self
            if self.name not in inst.__dict__:
                inst.__dict__[self.name] = _Sig()
            return inst.__dict__[self.name]

    class _Sig:
        def __init__(self): self.cbs, self.emitted = [], []
        def connect(self, f): self.cbs.append(f)
        def emit(self, *a):
            self.emitted.append(a)
            for f in self.cbs: f(*a)

    class _Rect:
        def __init__(self, x, y, w, h): self._v = (x, y, w, h)
        def x(self): return self._v[0]
        def y(self): return self._v[1]
        def width(self): return self._v[2]
        def height(self): return self._v[3]

    class QWidget:
        def __init__(self, parent=None, flags=None): self._g, self._vis = [0, 0, 100, 100], False
        def setGeometry(self, x, y, w, h): self._g = [x, y, w, h]
        def geometry(self): return _Rect(*self._g)
        def width(self): return self._g[2]
        def height(self): return self._g[3]
        def resize(self, w, h): self._g[2:] = [w, h]
        def show(self): self._vis = True
        def hide(self): self._vis = False
        def isVisible(self): return self._vis
        def winId(self): return 1234
        def __getattr__(self, n): return MagicMock()

    class QObject:
        def __init__(self, *a): pass

    class QTimer(QObject):
        timeout = Signal()
        def start(self, *a): self.running = True
        def stop(self): self.running = False
        def setSingleShot(self, v): pass
        def setInterval(self, v): pass

    class QAbstractNativeEventFilter:
        def __init__(self): pass

    class _Qt:
        LeftButton = 1
        AltModifier = 0x08000000
        ControlModifier = 0x04000000
        def __getattr__(self, n): return MagicMock()

    class QRectF:
        def __init__(self, x=0.0, y=0.0, w=0.0, h=0.0): self._v = (x, y, w, h)
        def left(self): return self._v[0]
        def top(self): return self._v[1]
        def width(self): return self._v[2]
        def height(self): return self._v[3]
        def right(self): return self._v[0] + self._v[2]
        def bottom(self): return self._v[1] + self._v[3]
        def toRect(self): return self

    class QPointF:
        def __init__(self, x=0.0, y=0.0): self._x, self._y = x, y
        def x(self): return self._x
        def y(self): return self._y

    core = types.ModuleType("PySide6.QtCore")
    core.Qt, core.Signal, core.QObject, core.QTimer = _Qt(), Signal, QObject, QTimer
    core.QUrl = MagicMock()
    core.QAbstractNativeEventFilter = QAbstractNativeEventFilter
    core.QPointF, core.QRectF = QPointF, QRectF
    class QPainter:
        Antialiasing, TextAntialiasing, SmoothPixmapTransform = 1, 2, 4
        def __init__(self, *a): pass
        def fontMetrics(self):
            fm = MagicMock()
            fm.horizontalAdvance.return_value = 80  # Qt real devolve int
            return fm
        def __getattr__(self, n): return MagicMock()

    gui = types.ModuleType("PySide6.QtGui")
    gui.QPainter = QPainter
    for n in ("QColor", "QFont", "QPen", "QPainterPath", "QBrush", "QLinearGradient", "QRadialGradient", "QGuiApplication", "QAction", "QActionGroup", "QIcon", "QPixmap", "QKeySequence", "QFontDatabase", "QDesktopServices"):
        setattr(gui, n, MagicMock())
    wid = types.ModuleType("PySide6.QtWidgets")
    wid.QWidget = QWidget
    wid.QDialog = type('QDialog', (QWidget,), {})
    def _mw(self): return MagicMock()
    wid.QMainWindow = type('QMainWindow', (QWidget,), {'menuBar': _mw, 'statusBar': _mw, 'setCentralWidget': lambda self, w: None,
                                                       'setWindowTitle': lambda self, t: None, 'hide': lambda self: setattr(self, '_vis', False)})
    for n in ("QApplication", "QInputDialog", "QMenu", "QMessageBox", "QSystemTrayIcon", "QFileDialog", "QCheckBox", "QComboBox", "QDialogButtonBox", "QFormLayout", "QHBoxLayout", "QKeySequenceEdit", "QLabel", "QLineEdit", "QListWidget", "QPushButton", "QPlainTextEdit", "QSpinBox", "QTabWidget", "QToolButton", "QVBoxLayout", "QScrollArea", "QSystemTrayIcon", "QTextBrowser"):
        setattr(wid, n, MagicMock())
    wid.QComboBox = lambda *a, **k: MagicMock(findData=MagicMock(return_value=0))  # findData precisa devolver int
    pkg = types.ModuleType("PySide6")
    pkg.QtCore, pkg.QtGui, pkg.QtWidgets = core, gui, wid
    sys.modules.update({"PySide6": pkg, "PySide6.QtCore": core, "PySide6.QtGui": gui, "PySide6.QtWidgets": wid})


class _Pt:
    def __init__(self, x, y): self._x, self._y = x, y
    def x(self): return self._x
    def y(self): return self._y
    def toPoint(self): return self
    def __sub__(self, o): return _Pt(self._x - o._x, self._y - o._y)


class _Ev:
    def __init__(self, x=0, y=0, gx=0, gy=0, mods=0, delta=0, button=1):
        self._l, self._g, self._m, self._d, self._b = _Pt(x, y), _Pt(gx, gy), mods, delta, button
    def position(self): return self._l
    def globalPosition(self): return self._g
    def modifiers(self): return self._m
    def button(self): return self._b
    def angleDelta(self): return _Pt(0, self._d)


@unittest.skipIf(HAVE_QT, "PySide6 real instalado: teste com stub dispensado")
class TestUiWithStub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _install_stub()
        from kerbhud.core.layout import MODULES, LayoutStore, ScreenInfo
        from kerbhud.providers.demo import DemoProvider
        from kerbhud.ui import modules, overlay_manager
        cls.MODULES, cls.LayoutStore, cls.ScreenInfo = MODULES, LayoutStore, ScreenInfo
        cls.modules, cls.om = modules, overlay_manager
        cls.snap = DemoProvider("corrida").poll()

    def test_all_modules_paint_without_errors(self):
        from kerbhud.core.model import Snapshot
        for mid in self.MODULES:
            win = self.modules.create_module(mid)
            for snap in (None, Snapshot(), self.snap):
                win.snapshot = snap
                win.paint_content(MagicMock(), win.spec.design_w, win.spec.design_h)
            win.paintEvent(None)  # caminho completo, incluindo moldura de edição
            win.set_edit_mode(True)
            win.paintEvent(None)

    def test_stage5_modules_draw_from_the_demo(self):
        import time
        from kerbhud.providers.demo import DemoProvider
        d = DemoProvider("box")
        track = self.modules.create_module("trackmap")
        fuel = self.modules.create_module("fuel")
        dmg = self.modules.create_module("damage")
        for t in [x * 0.05 for x in range(0, 700)]:
            d._t0 = time.monotonic() - t
            snap = d.poll()
            for win in (fuel, dmg):
                win.update_snapshot(snap)
            if int(t * 20) % 40 == 0:
                for win in (fuel, dmg):
                    p = MagicMock()
                    win.paint_content(p, win.spec.design_w, win.spec.design_h)
        race = DemoProvider("corrida")  # o mapa grava numa volta do piloto (amostras densas, como no uso real)
        for i in range(1500):
            race._t0 = time.monotonic() - i * 0.02
            track.update_snapshot(race.poll())
        # depois de uma volta o mapa desenha o traçado (círculos = carros) e o combustível mostra o abastecer
        p = MagicMock(); track.paint_content(p, 360, 300)
        self.assertGreaterEqual(p.drawEllipse.call_count, 8)
        p = MagicMock(); fuel.paint_content(p, 260, 250)
        self.assertTrue(any("ABAST." in str(c) for c in p.drawText.call_args_list))
        track.regravar()  # não quebra mesmo sem pasta de traçados

    def test_stage6_modules_draw_from_the_demo(self):
        import time
        from kerbhud.providers.demo import DemoProvider
        d = DemoProvider("corrida")

        def at(t):
            d._t0 = time.monotonic() - t
            return d.poll()

        tires = self.modules.create_module("tires")
        spotter = self.modules.create_module("spotter")
        radar = self.modules.create_module("radar")
        flag = self.modules.create_module("digflag")
        for t in [x * 0.05 for x in range(0, 400)]:  # percorre 20 s (o tempo de espera do spotter conta em tempo real)
            snap = at(t)
            for win in (spotter, flag):
                win.update_snapshot(snap)
        for win in (tires, radar):
            win.update_snapshot(at(17))
        spotter.update_snapshot(at(17))
        flag.update_snapshot(at(14))
        p = MagicMock(); tires.paint_content(p, 260, 240)
        t = self._texts(p)
        self.assertIn("VOLTA", t)  # a volta atual no centro do carro
        self.assertTrue(any(x.endswith("°") for x in t))
        self.assertTrue(any(x.endswith("°C") for x in t))  # temperatura média em destaque, em cada pneu
        self.assertIn("TEMP.", t)
        self.assertIn("DESG.", t)  # o desgaste continua, mas secundário
        p = MagicMock(); flag.paint_content(p, 280, 140)
        self.assertGreater(p.drawEllipse.call_count, 120)  # painel de LEDs: moldura + grade + sigla
        flag.update_snapshot(at(10))  # sem bandeira: some com fade (não de seco)
        self.assertTrue(flag.is_animating)
        p = MagicMock(); flag.paint_content(p, 280, 140)
        self.assertGreater(p.drawEllipse.call_count, 0)
        flag._t -= 1.0  # passou o tempo do fade
        p = MagicMock(); flag.paint_content(p, 280, 140)
        self.assertEqual(p.drawEllipse.call_count, 0)
        self.assertFalse(flag.is_animating)
        flag.update_snapshot(at(14))  # a bandeira volta: aparece com fade
        flag._t -= 0.05
        p = MagicMock(); flag.paint_content(p, 280, 140)
        self.assertTrue(0.0 < flag._alpha < 1.0)
        p = MagicMock(); radar.paint_content(p, 240, 240)
        self.assertIn("lado estimado", self._texts(p))  # iRacing: lateral estimada
        self.assertGreaterEqual(p.drawRoundedRect.call_count, 2)
        p = MagicMock(); spotter.paint_content(p, 420, 110)
        self.assertGreaterEqual(p.drawRoundedRect.call_count, 3)

    def test_radar_side_glow_and_approach_strip(self):
        import time
        from kerbhud.providers.demo import DemoProvider
        d = DemoProvider("lmu")
        radar = self.modules.create_module("radar")
        glow = strip = False
        for i in range(0, 700):  # 35 s da etapa LMU
            d._t0 = time.monotonic() - i * 0.05
            radar.update_snapshot(d.poll())
            p = MagicMock(); radar.paint_content(p, 240, 240)
            glow = glow or p.setClipRect.call_count > 0
            strip = strip or p.drawPath.call_count > 0
        self.assertTrue(glow)   # meia-lua do carro ao lado
        self.assertTrue(strip)  # faixa do carro vindo de trás

    def test_radar_only_shows_when_a_car_is_near_with_fade(self):
        import time
        from kerbhud.providers.demo import DemoProvider
        d = DemoProvider("lmu")
        radar = self.modules.create_module("radar")

        def draw(t_stage):
            d._t0 = time.monotonic() - t_stage
            radar.update_snapshot(d.poll())
            p = MagicMock(); radar.paint_content(p, 240, 240)
            return p.drawEllipse.call_count

        radar._near_t = -1e9
        radar._alpha = 0.0
        self.assertEqual(draw(2), 0)  # ninguém perto: não desenha nada
        self.assertFalse(radar.is_animating)
        draw(14)  # carro emparelha: começa o fade-in
        self.assertGreater(radar._alpha, 0.0)
        self.assertLess(radar._alpha, 1.0)
        radar._alpha = 1.0
        radar._near_t = time.monotonic() - 10.0  # faz tempo que ninguém passa perto
        radar._t -= 0.1
        draw_after = draw(2)
        self.assertGreater(draw_after, 0)  # ainda desenha durante o fade-out
        self.assertLess(radar._alpha, 1.0)
        radar.options["auto_hide"] = False  # opção "sempre visível"
        radar._near_t = -1e9
        radar._alpha = 0.0
        radar._t -= 1.0
        self.assertGreater(draw(2), 0)

    def test_spotter_animates_while_a_car_is_alongside(self):
        import time
        from kerbhud.providers.demo import DemoProvider
        d = DemoProvider("lmu")
        sp = self.modules.create_module("spotter")
        d._t0 = time.monotonic() - 5.0
        sp.update_snapshot(d.poll())
        self.assertFalse(sp.is_animating)  # livre: nada aceso, nada animando
        for i in range(0, 400):  # percorre a etapa até um carro emparelhar
            d._t0 = time.monotonic() - 12.0 - i * 0.02
            sp.update_snapshot(d.poll())
            if sp._sides and any(sp._sides):
                break
        self.assertTrue(any(sp._sides))
        sp._alpha = [1.0, 1.0]
        p = MagicMock(); sp.paint_content(p, 520, 190)
        self.assertTrue(sp.is_animating)  # brilho/pulso contínuos
        self.assertGreater(p.setClipPath.call_count, 0)  # o brilho sobe pela barra

    def test_drag_move_resize_and_commit(self):
        win = self.modules.create_module("inputs")
        win.setGeometry(100, 100, 300, 120)
        win.mousePressEvent(_Ev(150, 60, 250, 160))
        win.mouseMoveEvent(_Ev(150, 60, 277, 173))
        self.assertEqual(win._geom(), (100, 100, 300, 120))  # fora do modo de edição: ignorado
        win.set_edit_mode(True)
        win.mousePressEvent(_Ev(150, 60, 250, 160))
        win.mouseMoveEvent(_Ev(150, 60, 277, 173))  # +27, +13 -> snap 8px
        self.assertEqual(win._geom(), (128, 112, 300, 120))
        win.mouseReleaseEvent(_Ev())
        self.assertEqual(win.geometry_committed.emitted, [("inputs",)])
        # Inputs tem escala fixa: arrastar a borda muda a ESCALA (proporção mantida), não a área visível
        g = win.geometry()
        win.mousePressEvent(_Ev(g.width() - 2, 60, 500, 500))
        win.mouseMoveEvent(_Ev(0, 0, 530, 520, mods=0x08000000))
        x, y, w, h = win._geom()
        self.assertEqual((w, h), (330, 132))  # +10% de largura = +10% de altura

    def test_wheel_scale_and_opacity(self):
        win = self.modules.create_module("trackmap")
        win.setGeometry(0, 0, 400, 300)
        win.set_edit_mode(True)
        win.wheelEvent(_Ev(delta=120))
        self.assertEqual(win._geom(), (0, 0, 400, 300))  # a roda sozinha NÃO muda mais a escala
        win.wheelEvent(_Ev(delta=-120, mods=0x04000000))
        self.assertAlmostEqual(win.opacity, 0.95)  # Ctrl + roda continua sendo a transparência
        # módulo sem escala fixa: arrastar o canto escala a janela inteira (proporção livre, como sempre)
        win.mousePressEvent(_Ev(395, 295, 500, 400))
        win.mouseMoveEvent(_Ev(395, 295, 600, 400, mods=0x08000000))
        self.assertEqual(win._geom()[2:], (500, 300))

    def test_manager_end_to_end(self):
        om = self.om
        screens = [self.ScreenInfo("S1", 0, 0, 1920, 1080)]
        om.current_screens = lambda: (screens, "S1")
        engine = MagicMock()
        engine.latest.return_value = self.snap
        with tempfile.TemporaryDirectory() as d:
            store = self.LayoutStore(Path(d) / "layouts")
            store.ensure_defaults()
            mgr = om.OverlayManager(engine, store, {"ui_hz": 30})
            mgr.load_active()
            vis = {mid: w.isVisible() for mid, w in mgr.windows.items()}
            self.assertEqual(vis, {"standings": True, "relative": True, "inputs": True,
                                   "telemetry": False, "trackmap": True, "fuel": True, "damage": True, "tires": True,
                                   "spotter": True, "radar": True, "digflag": True, "status": True})
            self.assertEqual(store.get_active(), "Corrida")
            # dados chegam às janelas visíveis
            mgr._on_tick()
            self.assertIs(mgr.windows["inputs"].snapshot, self.snap)
            # troca por atalho (índice) e visibilidade muda
            mgr.switch_layout_by_index(3)
            self.assertEqual(mgr.layout.name, "Broadcast")
            self.assertTrue(mgr.windows["inputs"].fading_out)  # some com fade-out, não de repente
            mgr.windows["inputs"]._vf = 0.0  # fade terminou
            mgr._on_tick()
            self.assertFalse(mgr.windows["inputs"].isVisible())
            self.assertTrue(mgr.windows["standings"].isVisible())
            # edição: mover módulo e persistir
            mgr.set_edit_mode(True)
            w = mgr.windows["trackmap"]
            w.mousePressEvent(_Ev(50, 50, 1000, 100))
            w.mouseMoveEvent(_Ev(50, 50, 1096, 196))
            w.mouseReleaseEvent(_Ev())
            mgr.set_edit_mode(False)  # força o salvamento
            again = store.load("Broadcast")
            self.assertNotEqual(again.modules["trackmap"].rect, self.om.preset_corrida().modules["trackmap"].rect)
            self.assertEqual(again.modules["trackmap"].screen, "S1")
            # salvar como novo layout e excluir
            mgr.save_as("Meu Layout")
            self.assertIn("Meu Layout", store.list_names())
            mgr.delete_layout("Meu Layout")
            self.assertNotIn("Meu Layout", store.list_names())
            # ocultar módulo individualmente e esconder tudo
            def finish_fades():  # o fade-out de 0,3 s termina e a janela é escondida de verdade
                for w in mgr.windows.values():
                    if w.fading_out:
                        w._vf = 0.0
                mgr._on_tick()
            mgr.set_module_visible("standings", False)
            finish_fades()
            self.assertFalse(mgr.windows["standings"].isVisible())
            mgr.toggle_overlay()
            finish_fades()
            self.assertFalse(any(w.isVisible() for w in mgr.windows.values()))
            mgr.set_edit_mode(True)  # edição reexibe o overlay
            self.assertTrue(mgr.windows["status"].isVisible())


    # ---- Etapa 3: módulos Inputs e Telemetria -------------------------- #
    @staticmethod
    def _texts(painter):
        out = []
        for c in painter.drawText.call_args_list:
            out.extend(a for a in c.args if isinstance(a, str))
        return out

    def _live_snapshot(self, gear=4, speed_ms=50.0):
        from kerbhud.core.model import Inputs, Sim, Snapshot
        return Snapshot(sim=Sim.LMU, connected=True, inputs=Inputs(
            throttle=0.8, brake=0.1, clutch=0.0, steering=0.25, steering_deg=135.0, gear=gear,
            rpm=7000.0, rpm_max=8000.0, speed_ms=speed_ms, shift_pct=0.9, shift_source="derived"))

    def test_inputs_module_shows_real_values_and_units(self):
        from kerbhud.ui.context import ModuleContext
        ctx = ModuleContext(settings={"units": "kmh"})
        win = self.modules.create_module("inputs", ctx)
        win.snapshot = self._live_snapshot()
        p = MagicMock()
        win.paint_content(p, 620, 112)
        t = self._texts(p)
        for expected in ("4", "180", "km/h", "R 135°", "7 000 rpm", "80%", "10%", "0%"):
            self.assertIn(expected, t)
        ctx.settings["units"] = "mph"
        p = MagicMock()
        win.paint_content(p, 620, 112)
        t = self._texts(p)
        self.assertIn("112", t)
        self.assertIn("mph", t)
        for gear, label in ((-1, "R"), (0, "N")):  # ré e neutro
            win.snapshot = self._live_snapshot(gear=gear)
            p = MagicMock()
            win.paint_content(p, 620, 112)
            self.assertIn(label, self._texts(p))

    def test_inputs_module_without_data_does_not_invent_values(self):
        win = self.modules.create_module("inputs")
        win.snapshot = None
        p = MagicMock()
        win.paint_content(p, 620, 112)
        t = self._texts(p)
        self.assertIn("SEM DADOS", t)
        self.assertIn("--", t)
        self.assertNotIn("0%", t)  # sem dados, nada de porcentagens inventadas
        self.assertEqual(p.drawPath.call_count, 0)  # sem histórico, sem curvas

    def test_inputs_shift_lights_span_full_width_at_top(self):
        win = self.modules.create_module("inputs")
        win.snapshot = self._live_snapshot()
        p = MagicMock(); win.paint_content(p, 620, 112)
        rects = [c.args[0] for c in p.drawRect.call_args_list]
        self.assertEqual(len(rects), 12)  # 12 segmentos
        self.assertEqual(p.setClipPath.call_count, 1)  # recortados pelo contorno do módulo

    def test_inputs_percent_labels_follow_visible_pedals(self):
        win = self.modules.create_module("inputs")
        win.snapshot = self._live_snapshot()
        p = MagicMock(); win.paint_content(p, 620, 112)
        pct = [t for t in self._texts(p) if t.endswith("%")]
        self.assertEqual(pct, ["0%", "10%", "80%"])  # embreagem, freio, acelerador
        win.options = {"show_clutch": False}
        p = MagicMock(); win.paint_content(p, 620, 112)
        self.assertEqual([t for t in self._texts(p) if t.endswith("%")], ["10%", "80%"])

    def test_inputs_layout_has_tight_vertical_margins_and_fits(self):
        from kerbhud.ui import inputs_module as im
        spec = self.MODULES["inputs"]
        self.assertEqual((spec.design_w, spec.design_h), (620, 112))
        self.assertLessEqual(im.TOP - im.LED_H, 4.0)  # respiro entre LEDs e conteúdo
        self.assertLessEqual(spec.design_h - im.BOTTOM, 3.0)  # margem inferior fina
        # rótulo de % cabe abaixo da barra e dentro da área útil
        self.assertLessEqual(im.LABEL_Y + im.LABEL_H, im.BOTTOM)
        # volante (aro + espessura) cabe na altura útil e na largura do módulo
        reach = im.WHEEL_R + im.RIM / 2
        self.assertGreaterEqual(im.WHEEL_C[1] - reach, im.TOP)
        self.assertLessEqual(im.WHEEL_C[1] + reach, im.LABEL_Y)  # sobra espaço p/ o ângulo
        self.assertLessEqual(im.WHEEL_C[0] + reach, spec.design_w)
        self.assertGreater(im.WHEEL_R, 26.0)  # maior que o volante anterior
        self.assertGreater(im.RIM, 5.0)  # aro mais grosso que o anterior
        # blocos horizontais não se sobrepõem
        self.assertLessEqual(im.TRACE[0] + im.TRACE[2], im.BAR_X0)
        self.assertLessEqual(im.BAR_X0 + 3 * im.BAR_W + 2 * im.BAR_GAP, im.GEAR[0])
        self.assertLessEqual(im.GEAR[0] + im.GEAR[2], im.SPEED_X)
        self.assertLessEqual(im.SPEED_X + im.SPEED_W, im.WHEEL_C[0] - reach)

    def test_panel_background_covers_only_the_used_area_anchored_top_left(self):
        """Janela maior que o conteúdo: o painel cobre só a área usada, no canto superior esquerdo."""
        from kerbhud.ui import module_base as mb

        class R:  # QRectF que guarda os valores
            def __init__(self, x, y, w, h): self.v = (x, y, w, h)

        win = self.modules.create_module("inputs")
        win.setGeometry(0, 0, 620, 300)  # bem mais alta que o conteúdo (112)
        painter = MagicMock()
        orig_p, orig_r = mb.QPainter, mb.QRectF
        mb.QPainter, mb.QRectF = MagicMock(return_value=painter), R
        try:
            win.paintEvent(None)
        finally:
            mb.QPainter, mb.QRectF = orig_p, orig_r
        x, y, w, h = painter.drawRoundedRect.call_args_list[0].args[0].v  # fundo do painel
        self.assertAlmostEqual(h, 111.0, delta=1.0)  # altura do conteúdo, não 300
        self.assertAlmostEqual(w, 619.0, delta=1.0)
        self.assertAlmostEqual(y, 0.5, delta=1.0)  # colado no topo (não centralizado)

    def test_inputs_pedal_bars_option(self):
        win = self.modules.create_module("inputs")
        self.assertEqual(win.visible_pedals(), ["clutch", "brake", "throttle"])
        win.options = {"show_clutch": False}
        self.assertEqual(win.visible_pedals(), ["brake", "throttle"])

    def test_inputs_embedded_trace(self):
        from kerbhud.core.history import TelemetryHistory
        from kerbhud.ui.context import ModuleContext
        hist = TelemetryHistory()
        snap = self._live_snapshot()
        for k in range(120):
            hist.on_snapshot(snap, now=50.0 + k / 60)
        win = self.modules.create_module("inputs", ModuleContext(history=hist))
        win.snapshot = snap
        p = MagicMock(); win.paint_content(p, 620, 112)
        self.assertEqual(p.drawPath.call_count, 3)  # embreagem, freio, acelerador
        win.options = {"show_clutch": False}
        p = MagicMock(); win.paint_content(p, 620, 112)
        self.assertEqual(p.drawPath.call_count, 2)
        win.options = {"trace_steering": True}
        p = MagicMock(); win.paint_content(p, 620, 112)
        self.assertEqual(p.drawPath.call_count, 4)
        # histórico mais curto que 2 amostras: não desenha nada
        win.ctx.history.clear()
        p = MagicMock(); win.paint_content(p, 620, 112)
        self.assertEqual(p.drawPath.call_count, 0)

    def test_inputs_abs_tc_gold_lockup_dot_and_wheel_styles(self):
        from kerbhud.core.history import TelemetryHistory
        from kerbhud.core.model import Inputs, Sim, Snapshot
        from kerbhud.ui import theme
        from kerbhud.ui.context import ModuleContext
        hist = TelemetryHistory()
        calm = self._live_snapshot()
        busy = Snapshot(sim=Sim.LMU, connected=True, inputs=Inputs(
            throttle=0.2, brake=0.9, steering_deg=10.0, gear=3, rpm=6000.0, rpm_max=8000.0, speed_ms=40.0,
            abs_active=True, tc_active=False, lockup=True))
        for k in range(120):
            hist.on_snapshot(busy if 40 <= k < 80 else calm, now=50.0 + k / 60)
        win = self.modules.create_module("inputs", ModuleContext(history=hist))
        win.snapshot = busy
        p = MagicMock(); win.paint_content(p, 620, 112)
        self.assertTrue(win.is_animating)  # o aviso pulsa
        brushes = [str(c.args[0]) for c in p.setBrush.call_args_list if c.args]
        self.assertTrue(any(theme.GOLD in b for b in brushes) or p.setPen.called)
        self.assertGreater(p.drawPath.call_count, 3)  # trecho dourado do freio por cima da linha
        # desligado em Config: nada de dourado nem de pulsar
        win.options = {"abs_tc_alert": False, "lock_alert": False, "downshift_marks": False}
        p = MagicMock(); win.paint_content(p, 620, 112)
        self.assertFalse(win.is_animating)
        self.assertEqual(p.drawPath.call_count, 3)
        # sem a informação do simulador (iRacing não dá TC; ABS ausente): nada aparece
        win.options = {}
        win.snapshot = calm
        p = MagicMock(); win.paint_content(p, 620, 112)
        self.assertFalse(win.is_animating)
        # todos os estilos de volante desenham sem erro; "sem volante" não desenha o aro
        for style in ("classic", "gt", "formula", "custom", "hidden"):
            win.options = {"wheel_style": style, "wheel_image": "/nao/existe.png"}
            p = MagicMock(); win.paint_content(p, 620, 112)
            self.assertIn("R 135°", self._texts(p), style)

    def test_telemetry_draws_one_curve_per_enabled_channel(self):
        from kerbhud.core.history import TelemetryHistory
        from kerbhud.ui.context import ModuleContext
        hist = TelemetryHistory()
        snap = self._live_snapshot()
        for k in range(120):
            hist.on_snapshot(snap, now=100.0 + k / 60)
        ctx = ModuleContext(settings={"units": "kmh"}, history=hist)
        win = self.modules.create_module("telemetry", ctx)
        win.snapshot = snap
        p = MagicMock(); win.paint_content(p, 640, 200)
        self.assertEqual(p.drawPath.call_count, 6)
        win.options = {"channels": {"speed": False, "rpm": False, "clutch": False}}
        p = MagicMock(); win.paint_content(p, 640, 200)
        self.assertEqual(p.drawPath.call_count, 3)
        win.options = {"channels": {c: False for c in ("throttle", "brake", "clutch", "speed", "rpm", "steering")}}
        p = MagicMock(); win.paint_content(p, 640, 200)
        self.assertEqual(p.drawPath.call_count, 0)
        self.assertIn("NENHUM CANAL ATIVO", self._texts(p))

    def test_telemetry_without_history_waits(self):
        win = self.modules.create_module("telemetry")
        win.snapshot = self._live_snapshot()
        p = MagicMock(); win.paint_content(p, 640, 200)
        self.assertEqual(p.drawPath.call_count, 0)
        self.assertIn("AGUARDANDO TELEMETRIA", self._texts(p))

    def test_manager_options_persist_and_units_saved(self):
        om = self.om
        om.current_screens = lambda: ([self.ScreenInfo("S1", 0, 0, 1920, 1080)], "S1")
        from kerbhud.ui.context import ModuleContext
        saved = {}
        engine = MagicMock(); engine.latest.return_value = self.snap
        with tempfile.TemporaryDirectory() as d:
            store = self.LayoutStore(Path(d) / "layouts"); store.ensure_defaults()
            settings = {"ui_hz": 30, "units": "kmh"}
            ctx = ModuleContext(settings=settings, save_setting=lambda k, v: saved.update({k: v}))
            mgr = om.OverlayManager(engine, store, settings, ctx)
            mgr.load_active()
            mgr.set_channel("brake", False)
            mgr.set_option("telemetry", "history_s", 30.0)
            mgr.set_units("mph")
            self.assertEqual(saved, {"units": "mph"})
            self.assertEqual(settings["units"], "mph")
            mgr._flush_save()
            reloaded = store.load(mgr.layout.name).modules["telemetry"].options
            self.assertEqual(reloaded["channels"]["brake"], False)
            self.assertEqual(reloaded["history_s"], 30.0)
            # a janela vê as mesmas opções após trocar de layout e voltar
            mgr.switch_layout("Treino"); mgr.switch_layout("Corrida")
            self.assertEqual(mgr.windows["telemetry"].options["history_s"], 30.0)

    def test_tray_menu_builds(self):
        from kerbhud.ui import app as appmod
        om = self.om
        om.current_screens = lambda: ([self.ScreenInfo("S1", 0, 0, 1920, 1080)], "S1")
        engine = MagicMock(); engine.latest.return_value = self.snap; engine.settings = {"simulator": "auto"}
        with tempfile.TemporaryDirectory() as d:
            store = self.LayoutStore(Path(d) / "layouts"); store.ensure_defaults()
            mgr = om.OverlayManager(engine, store, {"ui_hz": 30})
            mgr.load_active()
            appmod.Tray(MagicMock(), mgr, engine, [])  # constrói e executa rebuild()

    def test_stage7_manager_layout_management_and_dialog_module(self):
        om = self.om
        om.current_screens = lambda: ([self.ScreenInfo("S1", 0, 0, 1920, 1080)], "S1")
        engine = MagicMock(); engine.latest.return_value = self.snap
        with tempfile.TemporaryDirectory() as d:
            store = self.LayoutStore(Path(d) / "layouts"); store.ensure_defaults()
            mgr = om.OverlayManager(engine, store, {"ui_hz": 30})
            mgr.load_active()
            names = store.list_names()
            first = mgr.layout.name
            mgr.next_layout(1)
            self.assertEqual(mgr.layout.name, names[(names.index(first) + 1) % len(names)])
            mgr.next_layout(-1)
            self.assertEqual(mgr.layout.name, first)  # volta e dá a volta na lista
            copy = mgr.duplicate_layout(first)
            self.assertIn(copy, store.list_names())
            mgr.rename_layout(copy, "Minha cópia")
            out = Path(d) / "x.json"
            mgr.export_layout("Minha cópia", out)
            self.assertEqual(mgr.import_layout(out), "Minha cópia (2)")
            mgr.rename_layout(first, "Renomeado")  # renomear o ativo mantém o ativo
            self.assertEqual((mgr.layout.name, store.get_active()), ("Renomeado", "Renomeado"))
            mgr.set_ui_hz(60)
            self.assertEqual(mgr.settings["ui_hz"], 60)
            import kerbhud.ui.settings_dialog as sd  # só precisa importar com o stub
            self.assertTrue(hasattr(sd, "SettingsDialog") and hasattr(sd, "ModuleConfigDialog"))
            import kerbhud.ui.update_ui as uu
            self.assertTrue(hasattr(uu, "UpdateController"))
            self._check_suggestion_dialog()
            dlg = sd.ModuleConfigDialog(mgr, "radar")  # monta a partir de core/module_options
            mgr.set_option("radar", "range_m", 40.0)
            self.assertEqual(mgr.layout.modules["radar"].options["range_m"], 40.0)

    def test_overlay_steps_off_the_top_while_the_taskbar_or_tray_is_in_use(self):
        from unittest import mock
        om = self.om
        om.current_screens = lambda: ([self.ScreenInfo("S1", 0, 0, 1920, 1080)], "S1")
        engine = MagicMock(); engine.latest.return_value = self.snap
        with tempfile.TemporaryDirectory() as d:
            store = self.LayoutStore(Path(d) / "layouts"); store.ensure_defaults()
            mgr = om.OverlayManager(engine, store, {"ui_hz": 30})
            for w in mgr.windows.values():
                w.lower_below_shell, w.reassert_topmost = MagicMock(), MagicMock()
            first = next(iter(mgr.windows.values()))
            with mock.patch.object(om.winapi, "shell_has_focus", return_value=True):
                mgr._reassert_topmost(); mgr._reassert_topmost()
            self.assertEqual(first.lower_below_shell.call_count, 1)  # abaixa uma vez só
            first.reassert_topmost.assert_not_called()  # e não reafirma o topo enquanto a barra está em uso
            with mock.patch.object(om.winapi, "shell_has_focus", return_value=False):
                mgr._reassert_topmost()
            first.reassert_topmost.assert_called_once()  # o foco voltou: volta ao topo na hora
            mgr.external_menu_open = lambda: True  # menu da bandeja aberto também conta
            mgr._reassert_topmost()
            self.assertEqual(first.lower_below_shell.call_count, 2)

    def test_main_window_builds_and_hides_to_tray_on_close(self):
        from kerbhud.ui import main_window as mw
        om = self.om
        om.current_screens = lambda: ([self.ScreenInfo("S1", 0, 0, 1920, 1080)], "S1")
        engine = MagicMock(); engine.latest.return_value = self.snap; engine.settings = {"simulator": "auto"}
        saved, quit_calls = {}, []
        with tempfile.TemporaryDirectory() as d:
            store = self.LayoutStore(Path(d) / "layouts"); store.ensure_defaults()
            settings = {"ui_hz": 30, "close_to_tray": True, "remember_window": True, "window_geometry": [10, 20, 500, 600]}
            mgr = om.OverlayManager(engine, store, settings)
            mgr.load_active()
            tray = MagicMock()
            win = mw.MainWindow(tray, mgr, engine, settings, lambda k, v: saved.__setitem__(k, v),
                                lambda: quit_calls.append(1))
            self.assertEqual(win.modules_panel.rows.keys(), mw.MODULES.keys())
            ctl = MagicMock(); ctl.state, ctl.message, ctl.available, ctl.listeners = "idle", "", None, []
            win.set_updates(ctl)  # barra de atualização ligada ao controlador
            self.assertEqual(len(ctl.listeners), 2)  # barra de versão + faixa de "nova versão"
            ctl.state, ctl.available = "available", MagicMock(version="9.9.9")
            for cb in ctl.listeners:
                cb()  # aviso de versão nova atualiza a barra e a faixa sem erro
            import kerbhud.ui.changelog_dialog as cd
            self.assertTrue(hasattr(cd, "ChangelogDialog"))
            ev = MagicMock()
            win.closeEvent(ev)  # fechar = esconder, não encerrar
            ev.ignore.assert_called_once()
            self.assertEqual(quit_calls, [])
            self.assertEqual(saved["window_geometry"][2:], [500, 600])
            settings["close_to_tray"] = False
            ev2 = MagicMock()
            win.closeEvent(ev2)  # sem bandeja: fechar encerra
            ev2.accept.assert_called_once()
            self.assertEqual(quit_calls, [1])
            win2 = mw.MainWindow(tray, mgr, engine, settings, lambda k, v: None, lambda: quit_calls.append(2))
            win2.quit()
            self.assertEqual(quit_calls, [1, 2])

    # ---- Etapa 4: Standings e Relative ---------------------------------- #
    def _rel_helpers(self):
        try:
            import test_standings_relative as T4
        except ImportError:
            from tests import test_standings_relative as T4
        return T4

    def setUp(self):
        from kerbhud.ui import module_base as mb
        mb.clear_font_caches()  # cada teste começa sem fontes/ajustes guardados por outro teste
        self.addCleanup(mb.clear_font_caches)

    class FakeLogos:
        """Faz o papel do LogoCache: registra quais logos reais foram desenhadas."""
        def __init__(self, available=None):
            self.keys, self.available = [], available
        def draw(self, p, brand, cx, cy, size=22.0):
            ok = self.available is None or brand.key in self.available
            if ok:
                self.keys.append(brand.key)
            return ok
        def clear(self):
            pass
        unrecognized = None

        def note_unrecognized(self, team, raw, cls=None):
            if self.unrecognized is None:
                self.unrecognized = []
            self.unrecognized.append((team, raw))

    def test_standings_top_bar_groups_rows_and_footer(self):
        import re
        from kerbhud.ui import icons
        from kerbhud.ui.context import ModuleContext
        logos = self.FakeLogos()
        win = self.modules.create_module("standings", ModuleContext(logos=logos))
        win.snapshot = self.snap  # DEMO: corrida por tempo, 3 classes
        helmets = []
        orig = icons.helmet
        icons.helmet = lambda *a, **k: helmets.append(a)
        try:
            p = MagicMock(); win.paint_content(p, *win.design_size())
        finally:
            icons.helmet = orig
        t = self._texts(p)
        # barra superior: relógio, incidentes, volta atual/estimada, quantidade de pilotos
        self.assertTrue(any(re.fullmatch(r"\d\d:\d\d:\d\d / 02:00:00", x) for x in t), t[:8])
        self.assertIn("R", t)  # inicial da sessão
        self.assertIn("6/25", t)
        self.assertIn("Lap", t)
        me = self.snap.player()
        self.assertTrue(any(x.startswith(f"{me.laps_completed + 1}/~") for x in t))
        self.assertIn(str(len(self.snap.cars)), t)
        for title in ("Tire", "Int", "Gap", "Fastest", "Last", "NRG"):
            self.assertIn(title, t)
        # cabeçalhos de classe: capacete + quantidade de pilotos da classe + nome
        for label, count in (("HYPER", 5), ("LMP2", 4), ("GT3", 7)):
            self.assertIn(label, t)
            self.assertIn(str(count), t)
        n_classes = len({c.class_name for c in self.snap.cars})
        self.assertEqual(len(helmets), n_classes + 1)  # 1 cabeçalho por classe + 1 na barra superior
        # rodapé com o meu perfil
        self.assertIn("LIC", t)
        self.assertIn("iR", t)
        self.assertTrue(any(x.endswith("%") for x in t))  # energia (NRG)
        self.assertTrue({"S", "M", "H"} & set(t))  # pneus
        # marcas: logos REAIS pedidas ao cache (nunca texto com sigla)
        self.assertTrue({"toyota", "ferrari", "porsche", "cadillac", "peugeot", "oreca"} & set(logos.keys))
        self.assertFalse({"TOY", "FER", "POR", "CAD", "PEU", "ORE"} & set(t))

    def test_no_abbreviation_badge_when_logo_files_are_missing(self):
        from kerbhud.ui.context import ModuleContext
        for logos in (None, self.FakeLogos(available=set())):  # sem cache / cache sem nenhum arquivo
            win = self.modules.create_module("standings", ModuleContext(logos=logos))
            win.snapshot = self.snap
            p = MagicMock(); win.paint_content(p, *win.design_size())
            t = self._texts(p)
            self.assertFalse({"TOY", "FER", "POR", "CAD", "PEU", "ORE", "BMW", "AM", "MB"} & set(t))

    def test_standings_rows_columns_scope_and_profile_options(self):
        names = [c.driver_name for c in self.snap.cars]
        win = self.modules.create_module("standings")
        win.snapshot = self.snap

        def drawn(opts):
            win.options = opts
            p = MagicMock(); win.paint_content(p, *win.design_size())
            return self._texts(p)

        small = drawn({"top_rows": 1, "around_rows": 3})
        big = drawn({"top_rows": 10, "around_rows": 20, "other_top": 5, "other_around": 5})
        n_small, n_big = sum(n in small for n in names), sum(n in big for n in names)
        self.assertLess(n_small, n_big)
        self.assertEqual(n_big, len(names))  # com contagens grandes todos aparecem
        no_cols = drawn({"columns": {"tire": False, "nrg": False, "license": False}})
        for gone in ("Tire", "NRG"):
            self.assertNotIn(gone, no_cols)
        me = self.snap.player()
        only = drawn({"scope": "class", "top_rows": 10, "around_rows": 20})
        for c in self.snap.cars:
            self.assertEqual(c.driver_name in only, c.class_name == me.class_name, c.driver_name)
        self.assertFalse(any(x.endswith(("HYPER", "LMP2")) and x[0].isdigit() for x in only))  # sem cabeçalhos
        self.assertIn("LIC", drawn({}))
        self.assertNotIn("LIC", drawn({"show_profile": False}))

    def test_standings_row_details_tire_energy_brand_rating(self):
        T4 = self._rel_helpers()
        cars = [T4.car(1, 1, "GT3", driver_name="Pole Sitter", car_model="BMW M4 GT3", irating=1800,
                       license_class="A", license_sr=3.4, tire="S", energy_pct=80.0, best_lap=100.0,
                       last_lap=101.0, laps_completed=12),
                T4.car(2, 2, "GT3", driver_name="Segundo", irating=1500, license_class="B", license_sr=2.2)]
        from kerbhud.ui.context import ModuleContext
        logos = self.FakeLogos()
        win = self.modules.create_module("standings", ModuleContext(logos=logos))
        win.snapshot = T4.snap(cars, me=1)  # meu carro tem NRG: a coluna existe
        p = MagicMock(); win.paint_content(p, *win.design_size())
        t = self._texts(p)
        for expected in ("Pole Sitter", "1.8k", "A", "S", "80%", "1:40.000", "1:41.000", "12", "1.5k"):
            self.assertIn(expected, t)
        self.assertEqual(logos.keys, ["bmw"])  # a logo real da BMW foi pedida, uma vez
        self.assertNotIn("BMW", t)

    def test_standings_empty_states_and_anchor(self):
        from kerbhud.core.model import SessionState, Sim, Snapshot
        win = self.modules.create_module("standings")
        win.snapshot = None
        p = MagicMock(); win.paint_content(p, *win.design_size())
        self.assertIn("SEM DADOS", self._texts(p))
        race_empty = Snapshot(sim=Sim.LMU, connected=True, session=SessionState(active=True, session_type="Race"))
        win.snapshot = race_empty  # corrida sem ninguém na lista ainda
        p = MagicMock(); win.paint_content(p, *win.design_size())
        self.assertIn("AGUARDANDO CLASSIFICAÇÃO", self._texts(p))
        # ancorado no canto superior esquerdo: janela mais alta não centraliza o painel
        from kerbhud.ui import module_base as mb

        class R:
            def __init__(self, x, y, w, h): self.v = (x, y, w, h)
        win.setGeometry(0, 0, 900, 900)
        painter = MagicMock()
        o1, o2 = mb.QPainter, mb.QRectF
        mb.QPainter, mb.QRectF = MagicMock(return_value=painter), R
        try:
            win.paintEvent(None)
        finally:
            mb.QPainter, mb.QRectF = o1, o2
        x, y, w, h = painter.drawRoundedRect.call_args_list[0].args[0].v
        self.assertAlmostEqual(x, 0.5, delta=1.0)
        self.assertAlmostEqual(y, 0.5, delta=1.0)

    def test_standings_practice_mode_shows_best_lap_gaps(self):
        T4 = self._rel_helpers()
        cars = [T4.car(1, 1, best_lap=100.0, last_lap=101.2), T4.car(2, 2, best_lap=100.8),
                T4.car(3, 3, best_lap=None)]
        win = self.modules.create_module("standings")
        win.snapshot = T4.snap(cars, session_type="Practice", me=2)
        p = MagicMock(); win.paint_content(p, *win.design_size())
        t = self._texts(p)
        for expected in ("+0.800", "1:40.000", "1:41.200", "P"):
            self.assertIn(expected, t)  # "P" = inicial de Practice
        self.assertIn("—", t)  # carro sem volta cronometrada

    def test_relative_demo_top_bar_footer_and_pills(self):
        import re
        win = self.modules.create_module("relative")
        win.snapshot = self.snap
        p = MagicMock(); win.paint_content(p, *win.design_size())
        t = self._texts(p)
        self.assertIn("SOF", t)  # força do grid
        self.assertTrue(any(re.fullmatch(r"\d\.\dk", x) for x in t))
        self.assertIn("6/25", t)  # incidentes / limite
        self.assertIn("RACE", t)  # rodapé: sessão
        self.assertTrue(any(re.fullmatch(r"\d\d:\d\d:\d\d / 02:00:00", x) for x in t))
        self.assertIn("Lap", t)
        self.assertIn("0.0", t)  # minha linha
        self.assertNotIn("RELATIVE", t)  # sem o título antigo
        self.assertTrue(any(x.startswith(("-", "+")) for x in t))

    def test_relative_draws_neighbours_gaps_license_and_rating(self):
        from kerbhud.core.relative import RelativeTracker, get_relative_options
        from kerbhud.core.standings import ir_deltas
        T4 = self._rel_helpers()
        s = T4.rel_snap(irating=2200, license_class="A", license_sr=3.4, others=[
            {"idx": 1, "pct": 0.52, "driver_name": "Ana Silva", "irating": 2500, "license_class": "B", "license_sr": 4.6},
            {"idx": 2, "pct": 0.47, "driver_name": "Bob Costa", "irating": 1800, "license_class": "C", "license_sr": 2.1}])
        win = self.modules.create_module("relative")
        win.snapshot = s
        p = MagicMock(); win.paint_content(p, *win.design_size())
        t = self._texts(p)
        for expected in ("Ana Silva", "Bob Costa", "Eu", "-2.00", "+3.00", "2.5k", "1.8k", "2.2k",
                         "B", "C", "A", "4.6", "2.1", "3.4"):
            self.assertIn(expected, t)
        self.assertLess(t.index("Ana Silva"), t.index("Eu"))  # à frente acima do piloto
        self.assertLess(t.index("Eu"), t.index("Bob Costa"))  # atrás abaixo
        for idx, delta in ir_deltas(s.cars).items():  # variação projetada de iRating em cada pílula
            self.assertIn(str(abs(delta)), t)

    def test_unrecognized_cars_are_noted_for_the_missing_logos_list(self):
        from kerbhud.ui.context import ModuleContext
        logos = self.FakeLogos()
        win = self.modules.create_module("standings", ModuleContext(logos=logos))
        T4 = self._rel_helpers()
        cars = [T4.car(1, 1, "GT3", driver_name="Ana", laps_completed=3, vehicle_raw="Porsche 911 GT3 R"),
                T4.car(2, 2, "GT3", driver_name="Eu", laps_completed=3, vehicle_raw="Carro Misterioso 9000")]
        win.snapshot = T4.snap(cars, me=2)
        p = MagicMock(); win.paint_content(p, *win.design_size())
        self.assertIn("porsche", logos.keys)
        self.assertEqual(logos.unrecognized, [(None, "Carro Misterioso 9000")])  # (equipe, veículo)

    def test_relative_lmu_shows_my_ranks_not_license(self):
        from kerbhud.core.model import DriverProfile, ProfileSource
        T4 = self._rel_helpers()
        s = T4.rel_snap(others=[{"idx": 1, "pct": 0.52}])
        s.profile = DriverProfile(driver_rank="Gold", safety_rank="Silver", source=ProfileSource.MANUAL)
        win = self.modules.create_module("relative")
        win.snapshot = s
        p = MagicMock(); win.paint_content(p, *win.design_size())
        t = self._texts(p)
        for expected in ("DR", "Gold", "SR", "Silver"):  # sem ícone conhecido: o texto do rank
            self.assertIn(expected, t)

    def test_ranks_are_text_and_the_safety_badge_takes_the_flag_slot(self):
        import time
        from kerbhud.core.model import ProfileSource
        from kerbhud.providers.demo import DemoProvider
        from kerbhud.ui import icons
        d = DemoProvider("lmu"); d._t0 = time.monotonic() - 12
        s = d.poll()
        calls = []
        orig = icons.contact_badge
        icons.contact_badge = lambda p, cx, cy, key, cache, size=30.0: (calls.append(key), True)[1]
        try:
            win = self.modules.create_module("standings")
            win.snapshot = s
            p = MagicMock(); win.paint_content(p, *win.design_size())
            texts = self._texts(p)
            for expected in (s.profile.driver_rank, "S3", "DR", "SR", "BADGE"):  # chips de DR e SR (também na linha) e o rótulo BADGE
                self.assertIn(expected, texts)
            self.assertEqual(calls, [s.profile.contact_badge.lower()] * 2)  # o ícone: na coluna da bandeira e no rodapé (no lugar do texto)
        finally:
            icons.contact_badge = orig

    def test_relative_puts_the_badge_icon_where_the_flag_would_be(self):
        import time
        from kerbhud.providers.demo import DemoProvider
        from kerbhud.ui import icons
        d = DemoProvider("lmu"); d._t0 = time.monotonic() - 12
        s = d.poll()
        calls = []
        orig = icons.contact_badge
        icons.contact_badge = lambda p, cx, cy, key, cache, size=30.0: (calls.append(key), True)[1]
        try:
            win = self.modules.create_module("relative")
            win.snapshot = s
            p = MagicMock(); win.paint_content(p, *win.design_size())
        finally:
            icons.contact_badge = orig
        self.assertEqual(calls, [s.profile.contact_badge.lower()])
        t = self._texts(p)
        self.assertIn(s.profile.driver_rank, t); self.assertIn("S3", t)

    def test_relative_counts_hits_and_off_tracks_for_lmu(self):
        import time
        from kerbhud.providers.demo import DemoProvider
        d = DemoProvider("lmu")
        win = self.modules.create_module("relative")
        for i in range(0, 700):
            d._t0 = time.monotonic() - i * 0.05
            win.update_snapshot(d.poll())
        self.assertEqual((win._incidents.hits, win._incidents.offs), (2, 2))
        p = MagicMock(); win.paint_content(p, *win.design_size())
        t = self._texts(p)
        self.assertIn("BAT", t)
        self.assertIn("FORA", t)

    def test_relative_empty_states_and_design(self):
        win = self.modules.create_module("relative")
        win.snapshot = None
        p = MagicMock(); win.paint_content(p, *win.design_size())
        self.assertIn("Aguardando dados", self._texts(p))
        from kerbhud.core import relative as rc
        self.assertEqual(win.design_size(), (rc.DESIGN_W, rc.HEADER_H + 7 * rc.ROW_H + rc.FOOTER_H))
        win.options = {"ahead": 5, "behind": 2}
        self.assertEqual(win.design_size()[1], rc.HEADER_H + 8 * rc.ROW_H + rc.FOOTER_H)

    def test_relative_lap_tags_pit_and_fight_outline(self):
        T4 = self._rel_helpers()
        from kerbhud.core.model import CarStatus
        s = T4.rel_snap(others=[{"idx": 1, "pct": 0.508, "driver_name": "Duelo"},
                                {"idx": 2, "pct": 0.53, "laps": 6, "driver_name": "UmaVoltaAFrente"},
                                {"idx": 3, "pct": 0.46, "status": CarStatus.PITS, "driver_name": "NoBox"}])
        win = self.modules.create_module("relative")
        win.snapshot = s
        p = MagicMock(); win.paint_content(p, *win.design_size())
        t = self._texts(p)
        self.assertIn("+1L", t)  # carro uma volta à frente
        self.assertIn("PIT", t)
        self.assertGreater(p.drawRect.call_count, 8)  # contorno extra da disputa direta

    def _fake_clock(self):
        class Clock:
            t = 0.0
            def __call__(self): return self.t
        return Clock()

    def test_standings_overtake_animation(self):
        T4 = self._rel_helpers()
        def order(first, second):
            return [T4.car(first, 1, laps_completed=5), T4.car(second, 2, laps_completed=5),
                    T4.car(3, 3, laps_completed=5)]
        win = self.modules.create_module("standings")
        clock = self._fake_clock(); win._clock = clock
        win.snapshot = T4.snap(order(1, 2), me=3)
        p = MagicMock(); win.paint_content(p, *win.design_size())
        self.assertFalse(win.is_animating)  # primeira vez: sem animação
        clock.t = 1.0
        win.snapshot = T4.snap(order(2, 1), me=3)  # carro 2 passou o carro 1
        p = MagicMock(); win.paint_content(p, *win.design_size())
        self.assertTrue(win.is_animating)
        self.assertGreater(win._anim.sample(2, clock.t).flash, 0)  # quem passou: verde
        self.assertLess(win._anim.sample(1, clock.t).flash, 0)  # quem foi passado: vermelho
        self.assertTrue(win._anim.sample(2, clock.t + 0.1).moving)
        self.assertEqual(win._anim.sample(3, clock.t).flash, 0)  # quem não mudou, não pisca
        clock.t = 6.0
        p = MagicMock(); win.paint_content(p, *win.design_size())
        self.assertFalse(win.is_animating)  # terminou
        # desligado nas opções: nunca anima
        off = self.modules.create_module("standings")
        off._clock = clock; off.options = {"animations": False}
        clock.t = 10.0
        off.snapshot = T4.snap(order(1, 2), me=3)
        off.paint_content(MagicMock(), *off.design_size())
        clock.t = 11.0
        off.snapshot = T4.snap(order(2, 1), me=3)
        off.paint_content(MagicMock(), *off.design_size())
        self.assertFalse(off.is_animating)

    def test_relative_overtake_animation(self):
        T4 = self._rel_helpers()
        def run(first_pct, second_pct):
            win = self.modules.create_module("relative")
            clock = self._fake_clock(); win._clock = clock
            win.snapshot = T4.rel_snap(others=[{"idx": 1, "pct": first_pct}])
            win.paint_content(MagicMock(), *win.design_size())
            clock.t = 1.0
            win.snapshot = T4.rel_snap(others=[{"idx": 1, "pct": second_pct}])
            win.paint_content(MagicMock(), *win.design_size())
            return win, clock
        win, clock = run(0.52, 0.48)  # eu passei o carro 1 (ele estava à frente e ficou atrás)
        self.assertTrue(win.is_animating)
        self.assertGreater(win._anim.sample(1, clock.t).flash, 0)  # verde
        self.assertTrue(win._anim.sample(1, clock.t + 0.1).moving)  # desliza atravessando a minha linha
        self.assertEqual(win._anim.sample("me", clock.t).flash, 0)
        win, clock = run(0.48, 0.52)  # o carro 1 me passou
        self.assertLess(win._anim.sample(1, clock.t).flash, 0)  # vermelho
        clock.t = 5.0
        win.paint_content(MagicMock(), *win.design_size())
        self.assertFalse(win.is_animating)

    def test_manager_keeps_repainting_animating_windows(self):
        om = self.om
        om.current_screens = lambda: ([self.ScreenInfo("S1", 0, 0, 1920, 1080)], "S1")
        engine = MagicMock(); engine.latest.return_value = self.snap
        with tempfile.TemporaryDirectory() as d:
            store = self.LayoutStore(Path(d) / "layouts"); store.ensure_defaults()
            mgr = om.OverlayManager(engine, store, {"ui_hz": 30})
            mgr.load_active()
            mgr._on_tick()  # entrega o snapshot
            for w in mgr.windows.values():
                w._vf = 1.0  # fade-in de entrada já terminou
                w.update = MagicMock()
            mgr.windows["standings"].is_animating = True
            mgr._on_tick()  # mesmo snapshot (jogo pausado): só quem anima é redesenhado
            self.assertTrue(mgr.windows["standings"].update.called)
            self.assertFalse(mgr.windows["inputs"].update.called)

    @staticmethod
    def _painter8():
        p = MagicMock()
        p.fontMetrics.return_value.horizontalAdvance.side_effect = lambda t: len(t) * 8  # largura realista
        return p

    @staticmethod
    def _draw_calls(p):
        return [(c.args[0], c.args[-1]) for c in p.drawText.call_args_list if isinstance(c.args[-1], str)]

    def _find(self, calls, text):
        return next(rect for rect, t in calls if t == text)

    def test_spacing_standings_top_bar_lap_and_incidents(self):
        from kerbhud.ui import icons, standings_module as sm
        win = self.modules.create_module("standings")
        win.snapshot = self.snap
        x_icons = []
        orig_x = icons.x_icon
        icons.x_icon = lambda p, cx, cy, size, color: x_icons.append(cx)
        orig_color = sm.QColor
        sm.QColor = type("C", (), {"__init__": lambda self, n="": setattr(self, "name", n),
                                   "setAlphaF": lambda self, a: None})
        p = self._painter8()
        try:
            win.paint_content(p, *win.design_size())
        finally:
            icons.x_icon, sm.QColor = orig_x, orig_color
        calls = self._draw_calls(p)
        me = self.snap.player()
        lap_text = next(t for _r, t in calls if t.startswith(f"{me.laps_completed + 1}/~"))
        lap, val = self._find(calls, "Lap"), self._find(calls, lap_text)
        self.assertLessEqual(val.left() - (lap.left() + 8 * 3), 6)  # "Lap" colado ao valor
        inc = self._find(calls, "6/25")
        self.assertLessEqual(inc.left() - x_icons[0], 12)  # ícone de X colado ao número
        # número de incidentes em BRANCO
        pen = None
        for c in p.mock_calls:
            if c[0] == "setPen" and c[1]:
                pen = c[1][0]
            if c[0] == "drawText" and c[1] and c[1][-1] == "6/25":
                break
        self.assertEqual(getattr(pen, "name", None), "#f4f4f5")

    def test_spacing_relative_footer_and_incidents(self):
        from kerbhud.ui import icons, relative_module as rm
        T4 = self._rel_helpers()
        s = T4.rel_snap(me_laps=11, others=[{"idx": 1, "pct": 0.52}])
        s.session.elapsed_s, s.session.total_s, s.session.laps_total, s.session.incidents = 900.0, 2700.0, 25, 6
        win = self.modules.create_module("relative")
        win.snapshot = s
        x_icons = []
        orig_x = icons.x_icon
        icons.x_icon = lambda p, cx, cy, size, color: x_icons.append(cx)
        orig_color = rm.QColor
        rm.QColor = type("C", (), {"__init__": lambda self, n="": setattr(self, "name", n),
                                   "setAlphaF": lambda self, a: None})
        p = self._painter8()
        try:
            win.paint_content(p, *win.design_size())
        finally:
            icons.x_icon, rm.QColor = orig_x, orig_color
        calls = self._draw_calls(p)
        race, clock = self._find(calls, "RACE"), self._find(calls, "00:15:00 / 00:45:00")
        self.assertLessEqual(clock.left() - (race.left() + 8 * 4), 8)  # tempo logo depois de "RACE"
        lap, val = self._find(calls, "Lap"), self._find(calls, "12/25")
        gap = (val.left() + 2) - (lap.left() + lap.width() - 2)
        self.assertLessEqual(gap, 6)  # "Lap" colado ao valor
        inc = self._find(calls, "6")
        self.assertLessEqual((inc.left() + 2) - x_icons[0], 12)  # X colado ao número
        pen = None
        for c in p.mock_calls:
            if c[0] == "setPen" and c[1]:
                pen = c[1][0]
            if c[0] == "drawText" and c[1] and c[1][-1] == "6":
                break
        self.assertEqual(getattr(pen, "name", None), "#f4f4f5")  # incidentes em branco

    def test_helmet_icon_is_a_shell_plus_visible_visor(self):
        from kerbhud.ui import icons
        recorded = type("C", (), {"__init__": lambda self, n="": setattr(self, "name", n),
                                  "setAlphaF": lambda self, a: None})
        orig = icons.QColor
        icons.QColor = recorded
        try:
            p = MagicMock()
            icons.helmet(p, 10, 10, 20, "#111111", visor="#4cc9f0")
            shell_color = p.fillPath.call_args.args[1].name
            visor_color = p.setBrush.call_args.args[0].name
            self.assertEqual((shell_color, visor_color), ("#111111", "#4cc9f0"))  # casco escuro, viseira vazada
            self.assertEqual(p.fillPath.call_count, 1)
            self.assertEqual(p.drawRoundedRect.call_count, 1)
            p = MagicMock()
            icons.helmet(p, 0, 0, 20, "#8b8b95")  # sem viseira explícita: usa a cor do painel
            self.assertEqual(p.setBrush.call_args.args[0].name, "#121216")
        finally:
            icons.QColor = orig

    def test_class_header_helmet_and_text_contrast_with_each_class_color(self):
        from kerbhud.core.standings import HeaderLine
        from kerbhud.core.animation import NEUTRAL
        from kerbhud.ui import icons, standings_module as sm
        win = self.modules.create_module("standings")
        for label, color, expected_fg in (("LMP2", "#4cc9f0", "#111111"),  # azul claro: preto, com viseira azul
                                          ("HYPER", "#e10600", "#ffffff"),  # vermelho: branco
                                          ("GTP", "#f5c400", "#111111")):  # amarelo: preto
            calls = []
            orig = icons.helmet
            icons.helmet = lambda p, x, y, size, fg, visor=None: calls.append((fg, visor, size))
            try:
                win._group_header(MagicMock(), 900, 0, HeaderLine(label, color, 4), NEUTRAL)
            finally:
                icons.helmet = orig
            (fg, visor, size), = calls
            self.assertEqual(fg, expected_fg, label)
            self.assertEqual(visor, color, label)  # a viseira mostra a cor da classe: capacete legível
            self.assertGreaterEqual(size, 14)

    @staticmethod
    def _font_of_texts(p):
        """{texto: (tamanho, negrito, semibold)} do último setFont antes de cada drawText."""
        fonts, current = {}, None
        for c in p.mock_calls:
            if c[0] == "setFont" and c[1]:
                current = c[1][0]
            elif c[0] == "drawText" and c[1] and isinstance(c[1][-1], str) and current is not None:
                fonts[c[1][-1]] = current
        return fonts

    def test_text_sizes_follow_the_reference_style(self):
        from kerbhud.ui import standings_module as sm
        win = self.modules.create_module("standings")
        win.snapshot = self.snap
        used = []
        orig = sm.make_font
        sm.make_font = lambda px, bold=False, semibold=False: used.append((px, bold, semibold)) or (px, bold, semibold)
        try:
            win.paint_content(MagicMock(), *win.design_size())
        finally:
            sm.make_font = orig
        sizes = [u[0] for u in used]
        self.assertTrue(any(u[0] >= 18 and u[1] for u in used))  # nome do piloto, em negrito
        self.assertTrue(any(u[0] >= 20 and u[1] for u in used))  # posição
        self.assertGreaterEqual(min(sizes), 12)  # nada minúsculo (antes havia textos de 10-11 px)

    def test_standings_numeric_columns_are_bold_and_large(self):
        """Voltas, Int, Gap, melhor, última e NRG: negrito (ou semibold) e maiores que antes (17)."""
        from kerbhud.core.standings import NUM2_FONT_PX, NUM_FONT_PX
        from kerbhud.ui import standings_module as sm
        T4 = self._rel_helpers()
        cars = [T4.car(1, 1, driver_name="Lider", laps_completed=12, best_lap=100.0, last_lap=101.0,
                       gap_leader=0.0, energy_pct=80.0),
                T4.car(2, 2, driver_name="Segundo", laps_completed=12, best_lap=100.5, last_lap=102.3,
                       gap_leader=5.5, energy_pct=55.0)]
        from kerbhud.ui import module_base as mb
        win = self.modules.create_module("standings")
        win.snapshot = T4.snap(cars, me=2)
        p = MagicMock()
        orig_sm, orig_mb = sm.make_font, mb.make_font
        fake = lambda px, bold=False, semibold=False: type("F", (), {"px": px, "bold": bold, "semi": semibold})()  # noqa: E731
        sm.make_font = mb.make_font = fake
        try:
            win.paint_content(p, *win.design_size())
        finally:
            sm.make_font, mb.make_font = orig_sm, orig_mb
        fonts = self._font_of_texts(p)
        for text, floor in (("1:40.500", NUM_FONT_PX), ("1:42.300", NUM_FONT_PX),  # melhor e última: maiores
                            ("12", NUM2_FONT_PX), ("+5.500", NUM2_FONT_PX), ("80%", NUM2_FONT_PX), ("55%", NUM2_FONT_PX)):
            f = fonts[text]
            self.assertGreaterEqual(f.px, floor, text)
            self.assertTrue(f.bold or f.semi, text)
        self.assertGreater(NUM_FONT_PX, NUM2_FONT_PX)
        self.assertGreaterEqual(NUM2_FONT_PX, 20.0)  # e todas bem maiores que a versão anterior (19 e 17)

    def test_numeric_columns_shrink_to_fit_with_a_wide_font(self):
        """Com uma fonte larga (fallback do Windows), os números encolhem em vez de invadir a coluna vizinha."""
        import types
        from kerbhud.core.standings import NUM2_FONT_PX, WIDTHS
        from kerbhud.ui import module_base as mb, standings_module as sm
        NUM_FONT_PX = NUM2_FONT_PX  # gap e NRG usam o tamanho das colunas estreitas
        T4 = self._rel_helpers()
        cars = [T4.car(1, 1, driver_name="Lider", laps_completed=123, best_lap=100.0, last_lap=101.0,
                       gap_leader=0.0, energy_pct=100.0),
                T4.car(2, 2, driver_name="Segundo", laps_completed=122, best_lap=100.5, last_lap=102.3,
                       gap_leader=130.0, energy_pct=55.0)]  # gap longo: "+2:10.0" (7 caracteres)
        win = self.modules.create_module("standings")
        win.snapshot = T4.snap(cars, me=2)
        state = {"px": 0.0}
        fake = lambda px, bold=False, semibold=False: types.SimpleNamespace(px=px)  # noqa: E731
        orig_sm, orig_mb = sm.make_font, mb.make_font
        sm.make_font = mb.make_font = fake
        p = MagicMock()
        p.setFont.side_effect = lambda f: state.update(px=f.px)
        p.fontMetrics.return_value.horizontalAdvance.side_effect = lambda t: len(t) * 0.80 * state["px"]  # larga
        try:
            win.paint_content(p, *win.design_size())
        finally:
            sm.make_font, mb.make_font = orig_sm, orig_mb
        fonts = self._font_of_texts(p)
        self.assertIn("+2:10.0", self._texts(p))  # o texto continua inteiro
        for text, key in (("+2:10.0", "gap"), ("100%", "nrg")):
            f = fonts[text]
            avail = WIDTHS[key] - (48 if key == "nrg" else 8)
            self.assertLess(f.px, NUM_FONT_PX, text)  # encolheu
            self.assertGreaterEqual(f.px, 11.0)
            self.assertLessEqual(len(text) * 0.80 * f.px, avail + 1e-6, text)  # e agora cabe na coluna

    def test_full_names_are_never_abbreviated(self):
        import types
        from kerbhud.core.relative import NAME_FONT_PX as REL_PX
        from kerbhud.core.standings import NAME_FONT_PX as ST_PX
        from kerbhud.ui import module_base as mb, relative_module as rm, standings_module as sm
        T4 = self._rel_helpers()
        long_name = "Matthew Richard Beaumont"  # 24 letras: antes virava "M. Beaumont"
        huge = "Maximilian Alexander Konstantinopolous-Papadimitriou"  # 52 letras

        def run(module_id, name):
            state = {"px": 0.0}
            fake_font = lambda px, bold=False, semibold=False: types.SimpleNamespace(px=px)  # noqa: E731
            patched = [(sm, "make_font"), (rm, "make_font"), (mb, "make_font")]
            origs = [(m, n, getattr(m, n)) for m, n in patched]
            for m, n in patched:
                setattr(m, n, fake_font)
            p = MagicMock()
            p.setFont.side_effect = lambda f: state.update(px=f.px)
            p.fontMetrics.return_value.horizontalAdvance.side_effect = lambda t: len(t) * 0.55 * state["px"]
            try:
                win = self.modules.create_module(module_id)
                if module_id == "standings":
                    win.snapshot = T4.snap([T4.car(1, 1, driver_name=name), T4.car(2, 2)], me=2)
                else:
                    win.snapshot = T4.rel_snap(others=[{"idx": 1, "pct": 0.52, "driver_name": name}])
                win.paint_content(p, *win.design_size())
            finally:
                for m, n, o in origs:
                    setattr(m, n, o)
            fonts = self._font_of_texts(p)
            return fonts, self._texts(p)

        for module_id, base in (("standings", ST_PX), ("relative", REL_PX)):
            fonts, texts = run(module_id, long_name)
            self.assertIn(long_name, texts)  # nome inteiro, sem abreviar
            self.assertNotIn("M. Beaumont", texts)
            self.assertFalse(any("…" in t for t in texts))  # nem reticências
            self.assertEqual(fonts[long_name].px, base)  # e cabe sem encolher a fonte
            fonts, texts = run(module_id, huge)
            self.assertIn(huge, texts)  # nome enorme: continua inteiro...
            self.assertLess(fonts[huge].px, base)  # ...com a fonte menor para caber
            self.assertGreaterEqual(fonts[huge].px, 11.0)

    def test_brand_logo_size_is_large_and_scaled_with_aspect(self):
        from kerbhud.core.brands import brand_for
        from kerbhud.ui import icons, standings_module as sm
        self.assertGreaterEqual(sm.LOGO_SIZE, 28)
        # o módulo pede a logo com esse tamanho
        sizes = []
        orig = icons.brand_logo
        icons.brand_logo = lambda p, cx, cy, brand, logos, size=0: sizes.append(size) or True
        try:
            win = self.modules.create_module("standings")
            win.snapshot = self.snap
            win.paint_content(MagicMock(), *win.design_size())
        finally:
            icons.brand_logo = orig
        self.assertTrue(sizes and all(s == sm.LOGO_SIZE for s in sizes))
        # o cache desenha centralizado e mantendo a proporção da imagem (aqui 2:1)
        class Pm:
            def width(self): return 96
            def height(self): return 48
        cache = icons.LogoCache(None)
        cache._cache["bmw"] = Pm()
        cache.dir = Path(".")
        p = MagicMock()
        self.assertTrue(cache.draw(p, brand_for("BMW M4"), 100.0, 50.0, 30.0))
        target = p.drawPixmap.call_args.args[0]
        self.assertAlmostEqual(target.width(), 30.0)
        self.assertAlmostEqual(target.height(), 15.0)
        self.assertAlmostEqual(target.left(), 85.0)  # centrada em x = 100
        self.assertAlmostEqual(target.top(), 42.5)  # centrada em y = 50

    # ---- texto de tamanho fixo (Standings e Inputs) ------------------------ #
    def _fake_fonts(self):
        """Troca make_font por um que devolve o tamanho (px), para comparar o texto entre janelas."""
        import types
        from kerbhud.ui import inputs_module as im, module_base as mb, standings_module as sm
        mods = [sm, mb, im]
        orig = [(m, m.make_font) for m in mods]
        fake = lambda px, bold=False, semibold=False: types.SimpleNamespace(px=px, bold=bold)  # noqa: E731
        for m in mods:
            m.make_font = fake
        self.addCleanup(lambda: [setattr(m, "make_font", f) for m, f in orig])

    def _paint_events(self, win, sizes):
        """Executa paintEvent em janelas de vários tamanhos e devolve (escala do pintor, área disponível)."""
        from kerbhud.ui import module_base as mb
        out = []
        for w, h in sizes:
            win.setGeometry(0, 0, w, h)
            painter = MagicMock()
            orig = mb.QPainter
            mb.QPainter = MagicMock(return_value=painter)
            seen = []
            orig_content = win.paint_content
            win.paint_content = lambda p, aw, ah, _s=seen: _s.append((aw, ah))
            try:
                win.paintEvent(None)
            finally:
                mb.QPainter = orig
                win.paint_content = orig_content
            scale = painter.scale.call_args.args if painter.scale.called else None
            out.append((scale, seen[0] if seen else None))
        return out

    def test_paint_event_keeps_scale_constant_when_the_window_is_resized(self):
        """O ponto central do pedido: o tamanho do texto (escala do pintor) NÃO depende do tamanho da janela."""
        for module_id in ("standings", "inputs"):
            win = self.modules.create_module(module_id)
            win.options = {"scale": 0.0005}
            results = self._paint_events(win, [(1100, 640), (700, 300), (1600, 900), (300, 120)])
            scales = {r[0] for r in results}
            self.assertEqual(scales, {(0.96, 0.96)}, module_id)  # sempre 0,0005 x 1920
            for (w, h), (_s, avail) in zip([(1100, 640), (700, 300), (1600, 900), (300, 120)], results):
                self.assertAlmostEqual(avail[0], w / 0.96, places=6)  # a janela só define a ÁREA disponível
                self.assertAlmostEqual(avail[1], h / 0.96, places=6)
        # nos demais módulos o comportamento continua: o conteúdo acompanha a janela
        rel = self.modules.create_module("relative")
        results = self._paint_events(rel, [(650, 280), (325, 140)])
        self.assertNotEqual(results[0][0], results[1][0])
        self.assertAlmostEqual(results[0][0][0] / results[1][0][0], 2.0, places=6)

    def test_text_scale_follows_zoom_not_resize(self):
        win = self.modules.create_module("standings")
        win.options = {"scale": 0.0005}
        before = self._paint_events(win, [(900, 500)])[0][0]
        win.setGeometry(0, 0, 400, 200)  # só redimensionou
        self.assertEqual(self._paint_events(win, [(400, 200)])[0][0], before)
        win.zoom(1.25)  # zoom: este sim muda o texto
        after = self._paint_events(win, [(win.width(), win.height())])[0][0]
        self.assertAlmostEqual(after[0] / before[0], 1.25, places=6)

    def test_resizing_standings_changes_visible_area_never_the_text_size(self):
        self._fake_fonts()
        from kerbhud.core.standings import NAME_FONT_PX, NUM2_FONT_PX
        names = [c.driver_name for c in self.snap.cars]
        me = self.snap.player()
        win = self.modules.create_module("standings")
        win.snapshot = self.snap
        win.options = {"scale": 0.0005, "top_rows": 10, "around_rows": 20}  # o tamanho da janela é o teto das linhas
        full_w, full_h = win.design_size()
        results = {}
        for label, (aw, ah) in {"cheia": (full_w, 900), "estreita": (700, 900), "baixa": (full_w, 260)}.items():
            p = MagicMock()
            win.paint_content(p, aw, ah)
            t = self._texts(p)
            fonts = self._font_of_texts(p)
            results[label] = (sum(n in t for n in names), "NRG" in t, "Tire" in t, fonts, t)
            self.assertEqual(fonts[me.driver_name].px, NAME_FONT_PX, label)  # mesmo tamanho em qualquer janela
            self.assertTrue(fonts[me.driver_name].bold)
        shown = {k: v[0] for k, v in results.items()}
        self.assertGreater(shown["cheia"], shown["baixa"])  # janela baixa: menos linhas
        self.assertFalse(results["estreita"][1] or results["estreita"][2])  # janela estreita: sem NRG/Tire
        self.assertTrue(results["cheia"][1] and results["cheia"][2])  # janela cheia: tudo
        # os números também mantêm o tamanho (a fonte só encolhe se o texto não coubesse, o que não ocorre aqui)
        for label, (_n, _nrg, _tire, fonts, t) in results.items():
            for text in t:
                if text.startswith("+") and text in fonts:
                    self.assertEqual(fonts[text].px, NUM2_FONT_PX, label)

    def test_layout_size_is_the_used_area_inside_the_available_one(self):
        win = self.modules.create_module("standings")
        win.snapshot = self.snap
        win.options = {"scale": 0.0005}
        w, h = win.design_size()
        uw, uh = win.layout_size(w + 500, h + 500)
        self.assertAlmostEqual(uw, w)  # não estica as colunas para a janela maior
        self.assertLessEqual(uh, h)  # e só ocupa a altura das linhas mostradas
        uw, uh = win.layout_size(700, 300)
        self.assertLessEqual(uw, 700)
        self.assertLessEqual(uh, 300 + 1e-6)

    def test_text_scale_comes_from_options_and_reference_width(self):
        from kerbhud.ui import module_base as mb
        win = self.modules.create_module("standings")
        win.options = {"scale": 0.0005}
        self.assertAlmostEqual(win.fixed_scale_px(), 0.96)  # 0,0005 x 1920
        win.set_reference_width(3840)  # monitor 4K: mesmo tamanho RELATIVO, o dobro de pixels
        self.assertAlmostEqual(win.fixed_scale_px(), 1.92)
        win.set_reference_width(0)  # inválido: volta ao padrão
        self.assertAlmostEqual(win.fixed_scale_px(), 0.96)
        win.options = {"scale": 9.0}
        self.assertEqual(win.fixed_scale_px(), win.SCALE_PX_MAX)  # limites de segurança
        win.options = {"scale": 1e-9}
        self.assertEqual(win.fixed_scale_px(), win.SCALE_PX_MIN)
        # sem escala (módulo fora de um layout): ajusta o conteúdo à janela, como antes
        win.options = {}
        dw, dh = win.design_size()
        win.setGeometry(0, 0, int(dw / 2), int(dh * 3))
        self.assertAlmostEqual(win.fixed_scale_px(), win.width() / dw)

    def test_zoom_scales_text_and_window_together(self):
        win = self.modules.create_module("standings")
        win.options = {"scale": 0.0005}
        win.setGeometry(100, 50, 800, 500)
        win.zoom(1.10)
        self.assertAlmostEqual(win.options["scale"], 0.00055)
        x, y, w, h = win._geom()
        self.assertEqual((x, y, w, h), (100, 50, 880, 550))  # janela acompanha: o que aparece não muda
        win.zoom(1 / 1.10)
        self.assertAlmostEqual(win.options["scale"], 0.0005, places=8)
        win.zoom(100.0)  # exagero: respeita o limite e a janela cresce só o equivalente
        self.assertEqual(win.fixed_scale_px(), win.SCALE_PX_MAX)
        # módulo sem escala fixa: o zoom só escala a janela (comportamento antigo)
        rel = self.modules.create_module("relative")
        rel.setGeometry(0, 0, 400, 200)
        rel.zoom(1.5)
        self.assertEqual(rel._geom()[2:], (600, 300))
        self.assertNotIn("scale", rel.options)

    def test_wheel_in_edit_mode_zooms_text_for_fixed_modules_only(self):
        win = self.modules.create_module("inputs")
        win.options = {"scale": 0.0005}
        win.setGeometry(0, 0, 600, 120)
        win.set_edit_mode(True)
        before = dict(win.options)
        win.wheelEvent(_Ev(delta=120))
        self.assertEqual(win.options, before)  # a roda sozinha não muda o texto
        # canto inferior direito do quadrado vermelho: +20% de largura = texto e janela +20%, proporção mantida
        win.mousePressEvent(_Ev(595, 115, 600, 120))
        win.mouseMoveEvent(_Ev(595, 115, 720, 120, mods=0x08000000))
        win.mouseReleaseEvent(_Ev())
        self.assertAlmostEqual(win.options["scale"], 0.0006, places=8)
        self.assertEqual(win._geom(), (0, 0, 720, 144))
        self.assertEqual(win.geometry_committed.emitted[-1], ("inputs",))
        # canto superior esquerdo: o canto oposto (inferior direito) fica parado
        win.mousePressEvent(_Ev(2, 2, 0, 0))
        win.mouseMoveEvent(_Ev(2, 2, 144, 0, mods=0x08000000))  # puxa 144 px para dentro = menor
        x, y, w, h = win._geom()
        self.assertEqual((x + w, y + h), (720, 144))
        self.assertLess(w, 720)
        before = dict(win.options)
        win.wheelEvent(_Ev(delta=120, mods=0x04000000))  # Ctrl: transparência, não o texto
        self.assertEqual(win.options, before)
        rel = self.modules.create_module("relative")
        rel.setGeometry(0, 0, 400, 200)
        rel.set_edit_mode(True)
        rel.wheelEvent(_Ev(delta=120))
        self.assertEqual(rel._geom()[2:], (400, 200))
        self.assertNotIn("scale", rel.options)

    def test_big_header_with_small_drivers_never_reaches_the_column_titles(self):
        self._fake_fonts()
        win = self.modules.create_module("standings")
        win.snapshot = self.snap
        cur = {"px": 10}
        first_scale = {}
        for name, opts in (("normal", {}), ("L/XS", {"header_size": "L", "driver_size": "XS"})):
            win.options = {"scale": 0.0005, **opts}
            p = MagicMock()
            p.setFont.side_effect = lambda f: cur.update(px=f.px)
            p.fontMetrics.return_value.horizontalAdvance.side_effect = lambda t: len(t) * cur["px"] * 0.62
            win.paint_content(p, 3000, 3000)
            first_scale[name] = next(c[1][0] for c in p.mock_calls if c[0] == "scale")
        self.assertLessEqual(first_scale["normal"], 1.0)
        # cabeçalho L pediria 1.3x, mas com linhas XS os títulos sobem para a esquerda: a barra encolhe para caber
        self.assertLess(first_scale["L/XS"], 1.3)
        self.assertLess(first_scale["L/XS"], first_scale["normal"])
        self.assertGreaterEqual(first_scale["L/XS"], 0.6)

    def _check_suggestion_dialog(self):
        """Janela de sugestões: só envia com ideia suficiente + consentimento; mostra erro sem travar; limita 1 por minuto."""
        import threading
        import kerbhud.ui.suggestion_dialog as sg
        from kerbhud.core import feedback
        sg._COOLDOWN = feedback.Cooldown(60)
        sg.QTimer = MagicMock()  # o stub não tem singleShot; o teste chama _poll() à mão
        dlg = sg.SuggestionDialog({})
        text = {"idea": "Mostrar o clima da pista no overlay", "why": "", "simulator": "iRacing", "contact": ""}
        dlg._data = lambda: dict(text, version="0.17.13")
        sent = []
        orig = feedback.submit
        try:
            feedback.submit = lambda data, version="", **k: sent.append(data)
            dlg.consent.isChecked = lambda: False
            dlg._refresh()
            dlg.send.setEnabled.assert_called_with(False)  # sem consentimento, Enviar fica desligado
            dlg.consent.isChecked = lambda: True
            dlg._refresh()
            dlg.send.setEnabled.assert_called_with(True)
            dlg._send()
            for t in threading.enumerate():
                if t.name == "kerbhud-suggestion":
                    t.join(2)
            dlg._poll()
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0]["idea"], "Mostrar o clima da pista no overlay")
            self.assertEqual(sent[0]["version"], "0.17.13")
            dlg._send()  # segunda tentativa logo em seguida: bloqueada pelo intervalo de 1 minuto
            self.assertEqual(len(sent), 1)
            # falha de rede: mostra a mensagem, não envia e não derruba
            sg._COOLDOWN = feedback.Cooldown(60)
            def boom(data, version="", **k): raise feedback.FeedbackError("Sem conexão")
            feedback.submit = boom
            dlg._send()
            for t in threading.enumerate():
                if t.name == "kerbhud-suggestion":
                    t.join(2)
            dlg._poll()
            self.assertFalse(dlg._sending)
        finally:
            feedback.submit = orig

    def test_standings_header_and_driver_size(self):
        win = self.modules.create_module("standings")
        win.snapshot = self.snap
        win.options = {"scale": 0.0005}
        w0, h0 = win.layout_size(2000, 2000)
        win.options = {"scale": 0.0005, "driver_size": "L", "header_size": "L"}
        w1, h1 = win.layout_size(2000, 2000)
        self.assertGreater(w1, w0)  # linhas maiores alargam o painel
        self.assertGreater(h1, h0)
        p = MagicMock()
        win.paint_content(p, 2000, 2000)
        scales = [c[1] for c in p.mock_calls if c[0] == "scale"]
        self.assertIn((1.3, 1.3), scales)  # linhas e barra do topo ampliadas
        win.options = {"scale": 0.0005, "driver_size": "XS", "header_size": "XS"}
        self.assertLess(win.layout_size(2000, 2000)[1], h0)

    def test_dragging_an_edge_scales_text_and_window_together(self):
        win = self.modules.create_module("standings")
        win.options = {"scale": 0.0005}
        win.setGeometry(100, 100, 900, 500)
        win.set_edit_mode(True)
        win.mousePressEvent(_Ev(895, 250, 995, 350))  # borda direita
        win.mouseMoveEvent(_Ev(895, 250, 695, 350, mods=0x08000000))  # arrasta 300 px para a esquerda, sem snap
        win.mouseReleaseEvent(_Ev())
        self.assertEqual(win._geom()[2:], (600, 333))  # janela menor na mesma proporção...
        self.assertAlmostEqual(win.options["scale"], 0.0005 * 600 / 900, places=8)  # ...e o texto encolhe junto
        win.mousePressEvent(_Ev(300, 328, 0, 0))  # borda de baixo: segue a altura
        win.mouseMoveEvent(_Ev(300, 328, 0, 100, mods=0x08000000))
        self.assertEqual(win._geom()[2:], (780, 433))

    def test_inputs_graph_absorbs_width_other_elements_keep_size(self):
        from kerbhud.ui import inputs_module as im
        self._fake_fonts()
        win = self.modules.create_module("inputs")
        win.snapshot = self._live_snapshot()
        win.options = {"scale": 0.0005}
        self.assertEqual(win.layout_size(900, 500), (900, im.DESIGN_H))
        self.assertEqual(win.layout_size(300, 500), (im.MIN_W, im.DESIGN_H))  # mínimo: gráfico não some
        self.assertEqual(win.layout_size(620, 40), (620, im.DESIGN_H))

        class R:
            def __init__(self, x, y, w, h): self.v = (x, y, w, h)
        orig = im.QRectF
        im.QRectF = R
        self.addCleanup(lambda: setattr(im, "QRectF", orig))
        gear_px = {}
        for aw, expected_graph in ((620, 256.0), (900, 536.0), (470, 106.0), (200, 106.0)):
            p = MagicMock()
            win.paint_content(p, aw, 500)
            graph = next(c.args[0].v for c in p.drawRoundedRect.call_args_list)  # 1º retângulo arredondado: gráfico
            self.assertEqual(graph[2], expected_graph, aw)
            dx = max(aw, im.MIN_W) - im.DESIGN_W
            self.assertIn((dx, 0), [c.args for c in p.translate.call_args_list], aw)  # blocos da direita deslocados
            fonts = self._font_of_texts(p)
            gear_px[aw] = (fonts["4"].px, fonts["180"].px)  # marcha e velocidade
        self.assertEqual(len(set(gear_px.values())), 1)  # o tamanho dos elementos não muda com a janela

    def test_single_class_race_shows_the_class_header_with_driver_count(self):
        from kerbhud.ui import icons
        T4 = self._rel_helpers()
        cars = [T4.car(i, i, "GT3", driver_name=f"Piloto {i}") for i in range(1, 8)]
        win = self.modules.create_module("standings")
        win.snapshot = T4.snap(cars, me=3)
        helmets = []
        orig = icons.helmet
        icons.helmet = lambda *a, **k: helmets.append(a)
        try:
            p = MagicMock(); win.paint_content(p, *win.design_size())
        finally:
            icons.helmet = orig
        t = self._texts(p)
        self.assertIn("GT3", t)  # nome da classe no cabeçalho
        self.assertIn("7", t)  # quantidade de pilotos da classe
        self.assertEqual(len(helmets), 2)  # 1 cabeçalho de classe + 1 na barra superior

    def test_standings_flags_follow_column_option_and_resolver(self):
        from kerbhud.core.flags import FlagResolver
        from kerbhud.ui.context import ModuleContext

        class FakeFlags:
            def __init__(self): self.drawn = []
            def draw(self, p, code, x, y, w=26.0, h=18.0):
                self.drawn.append((code, w, h)); return True
            def clear(self): pass
        T4 = self._rel_helpers()
        cars = [T4.car(1, 1, driver_name="Ana", country="br"), T4.car(2, 2, driver_name="Eu"),
                T4.car(3, 3, driver_name="Zé")]
        flags = FakeFlags()
        ctx = ModuleContext(flags=flags, flag_resolver=FlagResolver({"my_country": "pt"}))
        win = self.modules.create_module("standings", ctx)
        win.snapshot = T4.snap(cars, me=2)
        win.paint_content(MagicMock(), *win.design_size())
        self.assertEqual(sorted(c for c, _w, _h in flags.drawn), ["br", "pt"])  # só quem tem país
        self.assertTrue(all(w >= 24 and h >= 16 for _c, w, h in flags.drawn))  # bandeira de bom tamanho
        flags.drawn.clear()
        win.options = {"columns": {"flag": False}}
        win.paint_content(MagicMock(), *win.design_size())
        self.assertEqual(flags.drawn, [])  # coluna desligada
        win2 = self.modules.create_module("standings", ModuleContext(flag_resolver=FlagResolver({"my_country": "pt"})))
        win2.snapshot = T4.snap(cars, me=2)
        win2.paint_content(MagicMock(), *win2.design_size())  # sem cache de imagens: não quebra nem desenha

    def test_flag_cache_draws_centered_with_aspect_and_skips_missing_files(self):
        from kerbhud.ui import icons

        class Pm:
            def width(self): return 96
            def height(self): return 64  # bandeira 3:2
        cache = icons.LogoCache(None)  # só para garantir que não depende do LogoCache
        flags = icons.FlagCache(Path("."))
        flags._cache["br"] = Pm()
        flags._cache["xx"] = None
        p = MagicMock()
        self.assertTrue(flags.draw(p, "br", 10.0, 20.0, 30.0, 30.0))
        target = p.drawPixmap.call_args.args[0]
        self.assertAlmostEqual(target.width(), 30.0)
        self.assertAlmostEqual(target.height(), 20.0)  # 3:2 dentro da caixa 30x30
        self.assertAlmostEqual(target.left(), 10.0)
        self.assertAlmostEqual(target.top(), 25.0)  # centralizada na vertical
        self.assertFalse(flags.draw(MagicMock(), "xx", 0, 0))  # arquivo ausente: nada
        self.assertFalse(icons.FlagCache(None).draw(MagicMock(), "br", 0, 0))
        self.assertIsNone(icons.FlagCache(Path(".")).get(""))

    def test_manager_sets_reference_width_and_persists_zoom(self):
        om = self.om
        screens = [self.ScreenInfo("S1", 0, 0, 1920, 1080), self.ScreenInfo("S2", 1920, 0, 2560, 1440)]
        om.current_screens = lambda: (screens, "S1")
        engine = MagicMock(); engine.latest.return_value = self.snap
        with tempfile.TemporaryDirectory() as d:
            store = self.LayoutStore(Path(d) / "layouts"); store.ensure_defaults()
            mgr = om.OverlayManager(engine, store, {"ui_hz": 30})
            mgr.load_active()
            st = mgr.layout.modules["standings"]
            self.assertIn("scale", st.options)
            self.assertEqual(mgr.windows["standings"]._ref_width, 1920)  # monitor onde o módulo está
            self.assertIs(mgr.windows["standings"].options, st.options)  # mesmo dict: zoom persiste
            st.screen = "S2"
            mgr.apply_layout(mgr.layout)
            self.assertEqual(mgr.windows["standings"]._ref_width, 2560)  # outro monitor, outra referência
            st.screen = "S1"
            mgr.apply_layout(mgr.layout)
            before = st.options["scale"]
            mgr.zoom_module("standings", 1.10)
            mgr._flush_save()
            self.assertAlmostEqual(store.load(mgr.layout.name).modules["standings"].options["scale"], before * 1.10)

    def test_top_info_bar_is_larger_and_never_reaches_the_column_titles(self):
        import types
        from kerbhud.core.standings import (INFO_FONT_PX, INFO_LABEL_PX, TITLE_ROW_Y, column_layout,
                                               get_standings_options)
        from kerbhud.ui import icons, module_base as mb, standings_module as sm
        self.assertGreaterEqual(INFO_FONT_PX, 20.0)  # antes 18
        self.assertGreaterEqual(INFO_LABEL_PX, 17.0)  # "Lap": antes 16
        win = self.modules.create_module("standings")
        win.snapshot = self.snap
        state = {"px": 0.0}
        fake = lambda px, bold=False, semibold=False: types.SimpleNamespace(px=px, bold=bold)  # noqa: E731
        orig = (sm.make_font, mb.make_font, icons.helmet, icons.x_icon, icons.session_badge)
        sizes = {}
        sm.make_font = mb.make_font = fake
        icons.helmet = lambda p, x, y, size, *a, **k: sizes.setdefault("helmet", (x, y, size))  # o 1º é o da barra superior
        icons.x_icon = lambda p, cx, cy, size, color: sizes.setdefault("x", (cx, cy, size))
        icons.session_badge = lambda p, cx, cy, r, letter: sizes.setdefault("badge", (cx, cy, r))
        p = MagicMock()
        p.setFont.side_effect = lambda f: state.update(px=f.px)
        p.fontMetrics.return_value.horizontalAdvance.side_effect = lambda t: len(t) * 0.52 * state["px"]  # tipo DIN
        try:
            win.paint_content(p, *win.design_size())
        finally:
            sm.make_font, mb.make_font, icons.helmet, icons.x_icon, icons.session_badge = orig
        fonts, current = {}, None  # fonte de cada texto SÓ da linha de cima da barra (top == 1)
        for c in p.mock_calls:
            if c[0] == "setFont" and c[1]:
                current = c[1][0]
            elif c[0] == "drawText" and c[1] and isinstance(c[1][-1], str) and c[1][0].top() == 1.0:
                fonts[c[1][-1]] = current
        calls = self._draw_calls(p)
        info = [(r, t) for r, t in calls if r.top() == 1.0]  # textos da linha de cima da barra
        texts = {t for _r, t in info}
        me = self.snap.player()
        lap_text = next(t for t in texts if t.startswith(f"{me.laps_completed + 1}/~"))
        time_text = next(t for t in texts if " / " in t)
        for t in (time_text, "6/25", lap_text, str(len(self.snap.cars))):
            self.assertEqual(fonts[t].px, INFO_FONT_PX, t)
            self.assertTrue(fonts[t].bold, t)
        self.assertEqual(fonts["Lap"].px, INFO_LABEL_PX)
        self.assertGreater(sizes["badge"][2], 11.5)  # ícone da sessão (antes r = 11)
        self.assertGreaterEqual(sizes["helmet"][2], 21)  # capacete (antes 19)
        self.assertGreaterEqual(sizes["x"][2], 11)  # ícone de X (antes 10)
        # cabe na faixa de cima: do topo até antes dos títulos das colunas
        for r, t in info:
            self.assertGreaterEqual(r.top(), 0.0)
            self.assertLessEqual(r.top() + r.height(), TITLE_ROW_Y + 2, t)
        # e termina antes da primeira coluna com título (com a janela cheia), sem invadir os títulos
        first_title_x = min(c.x for c in column_layout(get_standings_options({})) if c.key in ("tire", "laps", "int"))
        right_edge = max(r.left() + r.width() for r, t in info)
        self.assertLess(right_edge, first_title_x - 10)
        # e o ícone da sessão continua à esquerda de tudo
        self.assertLess(sizes["badge"][0] + sizes["badge"][2], min(r.left() for r, _t in info))

    def test_column_titles_are_large_and_fit_the_header_strip(self):
        """Títulos (Tire, Laps, Int, Gap, Fastest, Last, NRG) maiores que antes (13) e dentro da barra superior."""
        import types
        from kerbhud.core.standings import (TITLE_FONT_PX, TITLE_ROW_H, TITLE_ROW_Y, TOP_H, WIDTHS, column_layout,
                                               get_standings_options, standings_design_size)
        from kerbhud.ui import module_base as mb, standings_module as sm
        self.assertGreaterEqual(TITLE_FONT_PX, 16.0)
        self.assertLessEqual(TITLE_ROW_Y + TITLE_ROW_H, TOP_H)  # a faixa cabe na barra superior
        # a altura do módulo não mudou: layouts salvos continuam mostrando o mesmo número de linhas
        self.assertEqual((TOP_H, standings_design_size({})[1]), (44.0, 624.0))
        win = self.modules.create_module("standings")
        win.snapshot = self.snap
        state = {"px": 0.0}
        fake = lambda px, bold=False, semibold=False: types.SimpleNamespace(px=px)  # noqa: E731
        orig_sm, orig_mb = sm.make_font, mb.make_font
        sm.make_font = mb.make_font = fake
        p = MagicMock()
        p.setFont.side_effect = lambda f: state.update(px=f.px)
        p.fontMetrics.return_value.horizontalAdvance.side_effect = lambda t: len(t) * 0.52 * state["px"]  # tipo DIN
        try:
            win.paint_content(p, *win.design_size())
        finally:
            sm.make_font, mb.make_font = orig_sm, orig_mb
        fonts = self._font_of_texts(p)
        cols = {c.key: c for c in column_layout(get_standings_options({}))}
        rects = {c.args[-1]: c.args[0] for c in p.drawText.call_args_list if c.args[-1] in sm._TITLES.values()}
        for title, key in (("Laps", "laps"), ("Int", "int"), ("Gap", "gap"), ("Fastest", "best"), ("Last", "last"),
                           ("NRG", "nrg")):
            self.assertGreaterEqual(fonts[title].px, 16.0, title)  # bem maiores que os 13 anteriores
            self.assertEqual(fonts[title].px, TITLE_FONT_PX, title)  # cabem sem encolher
            r = rects[title]
            self.assertEqual((r.top(), r.height()), (TITLE_ROW_Y, TITLE_ROW_H), title)
            self.assertLessEqual(len(title) * 0.52 * fonts[title].px, r.width(), title)
        # "Tire" mora numa coluna de 36: encolhe só o necessário para caber
        tire = fonts["Tire"].px
        self.assertLessEqual(tire, TITLE_FONT_PX)
        self.assertGreaterEqual(tire, 12.0)
        self.assertLessEqual(len("Tire") * 0.52 * tire, WIDTHS["tire"] - 4 + 1e-6)

    def test_nrg_battery_has_clear_spacing_from_the_last_lap_text(self):
        """A bateria do NRG não pode ficar colada no texto da última volta."""
        from kerbhud.core.standings import NRG_ICON_X, NRG_TEXT_X, WIDTHS, column_layout, get_standings_options
        from kerbhud.ui import icons
        T4 = self._rel_helpers()
        cars = [T4.car(1, 1, driver_name="Lider", laps_completed=12, best_lap=100.0, last_lap=101.0, energy_pct=80.0),
                T4.car(2, 2, driver_name="Segundo", laps_completed=12, best_lap=100.5, last_lap=102.3, energy_pct=100.0)]
        win = self.modules.create_module("standings")
        win.snapshot = T4.snap(cars, me=2)
        batteries = []
        orig = icons.battery
        icons.battery = lambda p, x, y, pct: batteries.append(x)
        try:
            p = MagicMock(); win.paint_content(p, *win.design_size())
        finally:
            icons.battery = orig
        cols = {c.key: c for c in column_layout(get_standings_options({}))}
        last_text_right = cols["last"].x + cols["last"].w - 2  # texto alinhado à direita da coluna Last
        self.assertEqual(len(batteries), 2)
        for x in batteries:
            self.assertEqual(x, cols["nrg"].x + NRG_ICON_X)
            self.assertGreaterEqual(x - last_text_right, 14.0)  # antes eram só 6
        # a porcentagem vem logo depois da bateria (34 de largura) e cabe na coluna
        battery_right = NRG_ICON_X + 34.0 + 2.5
        self.assertGreater(NRG_TEXT_X, battery_right)
        self.assertLessEqual(NRG_TEXT_X - battery_right, 6.0)
        self.assertGreaterEqual(WIDTHS["nrg"] - NRG_TEXT_X - 4, 44.0)  # "100%" em negrito 19 cabe sem encolher

    def test_nrg_title_sits_over_the_battery(self):
        from kerbhud.core.standings import NRG_ICON_X, column_layout, get_standings_options
        win = self.modules.create_module("standings")
        win.snapshot = self.snap
        p = MagicMock(); win.paint_content(p, *win.design_size())
        cols = {c.key: c for c in column_layout(get_standings_options({}))}
        rect = next(c.args[0] for c in p.drawText.call_args_list if c.args[-1] == "NRG")
        self.assertAlmostEqual(rect.left(), cols["nrg"].x + NRG_ICON_X)

    # ---- ocultar / adaptar / apagar -------------------------------------- #
    def _practice_snapshot(self, with_time):
        T4 = self._rel_helpers()
        cars = [T4.car(i, i, "GT3", driver_name=f"Piloto {i}") for i in range(1, 6)]
        if with_time:
            cars[2].best_lap = 101.5
        return T4.snap(cars, session_type="Practice", me=1)

    def _paint_event_calls(self, win):
        """Roda paintEvent com um pintor falso e devolve ele (para ver se o painel foi desenhado)."""
        from kerbhud.ui import module_base as mb
        painter = MagicMock()
        painter.fontMetrics.return_value.horizontalAdvance.return_value = 80  # o Qt real devolve um inteiro
        orig = mb.QPainter
        mb.QPainter = MagicMock(return_value=painter)
        try:
            win.paintEvent(None)
        finally:
            mb.QPainter = orig
        return painter

    def test_standings_is_hidden_in_practice_until_somebody_sets_a_time(self):
        win = self.modules.create_module("standings")
        win.options = {"scale": 0.0005}
        win.setGeometry(0, 0, 1000, 600)
        win.snapshot = self._practice_snapshot(with_time=False)
        self.assertEqual(win.layout_size(1000, 600), (0.0, 0.0))  # nada a mostrar
        painter = self._paint_event_calls(win)
        self.assertFalse(painter.drawRoundedRect.called)  # nem o painel de fundo
        self.assertFalse(painter.drawText.called)
        win.snapshot = self._practice_snapshot(with_time=True)  # alguém fez tempo
        uw, uh = win.layout_size(1000, 600)
        self.assertGreater(uw, 0)
        self.assertGreater(uh, 0)
        painter = self._paint_event_calls(win)
        self.assertTrue(painter.drawRoundedRect.called)
        t = self._texts(painter)
        self.assertIn("Piloto 3", t)  # só quem fez tempo
        self.assertNotIn("Piloto 1", t)
        self.assertNotIn("Piloto 4", t)

    def test_hidden_standings_shows_a_placeholder_in_edit_mode_so_it_can_be_moved(self):
        win = self.modules.create_module("standings")
        win.options = {"scale": 0.0005}
        win.setGeometry(0, 0, 1000, 600)
        win.snapshot = self._practice_snapshot(with_time=False)
        win.set_edit_mode(True)
        uw, uh = win.layout_size(1000, 600)
        self.assertGreater(uw, 0)  # no modo de edição ocupa uma área para poder ser movido
        painter = self._paint_event_calls(win)
        self.assertTrue(painter.drawRoundedRect.called)
        self.assertIn("Aparece quando alguém fizer um tempo de volta", self._texts(painter))
        win.set_edit_mode(False)
        self.assertEqual(win.layout_size(1000, 600), (0.0, 0.0))

    def test_standings_panel_follows_the_number_of_drivers(self):
        """Poucos pilotos: o painel fica baixo, sem faixa vazia, e o rodapé vem logo depois das linhas."""
        from kerbhud.core.standings import FOOTER_H, PAD_BOTTOM, ROW_H, TOP_H
        T4 = self._rel_helpers()
        sizes = {}
        for n in (3, 12, 40):
            cars = [T4.car(i, i, "GT3", driver_name=f"Piloto {i}") for i in range(1, n + 1)]
            win = self.modules.create_module("standings")
            win.options = {"scale": 0.0005, "top_rows": 10, "around_rows": 20}
            win.snapshot = T4.snap(cars, me=2)
            sizes[n] = win.layout_size(1200, 2000)[1]
        self.assertEqual(sizes[3], TOP_H + (1 + 3) * ROW_H + FOOTER_H + PAD_BOTTOM)  # cabeçalho + 3 pilotos
        self.assertLess(sizes[3], sizes[12])
        self.assertLess(sizes[12], sizes[40])
        self.assertEqual(sizes[12], TOP_H + (1 + 12) * ROW_H + FOOTER_H + PAD_BOTTOM)

    def test_standings_race_shows_absent_drivers_dimmed_instead_of_dropping_them(self):
        from kerbhud.core.model import CarState, CarStatus
        T4 = self._rel_helpers()
        cars = [T4.car(1, 1, driver_name="Presente Um"), T4.car(2, 2, driver_name="Presente Dois"),
                CarState(idx=1003, position=3, class_name="GT3", driver_name="Quem Saiu", car_number="9",
                         status=CarStatus.OUT, in_session=False)]
        win = self.modules.create_module("standings")
        win.snapshot = T4.snap(cars, me=2)
        opacities, names = [], []
        p = MagicMock()
        p.drawText.side_effect = lambda *a: names.append((a[-1], opacities[-1] if opacities else 1.0))
        p.setOpacity.side_effect = lambda v: opacities.append(v)
        win.paint_content(p, *win.design_size())
        seen = dict(names)
        self.assertIn("Quem Saiu", seen)  # continua na lista
        self.assertAlmostEqual(seen["Quem Saiu"], 0.40, places=2)  # mas apagado (como o 2º print de exemplo)
        self.assertAlmostEqual(seen["Presente Um"], 1.0, places=2)
        self.assertIn("OUT", seen)  # com a marca OUT

    def test_relative_panel_follows_the_rows_and_text_size_is_unchanged(self):
        from kerbhud.core import relative as rc
        T4 = self._rel_helpers()
        full_w, full_h = rc.relative_design_size({})
        sizes = {}
        for label, others in (("nenhum", []), ("um", [{"idx": 1, "pct": 0.52}]),
                              ("tres", [{"idx": 1, "pct": 0.52}, {"idx": 2, "pct": 0.47}, {"idx": 3, "pct": 0.53}])):
            win = self.modules.create_module("relative")
            win.snapshot = T4.rel_snap(others=others)
            sizes[label] = win.layout_size(full_w, full_h)[1]
        self.assertEqual(sizes["um"], rc.HEADER_H + 2 * rc.ROW_H + rc.FOOTER_H)  # 1 carro + eu
        self.assertEqual(sizes["tres"], rc.HEADER_H + 4 * rc.ROW_H + rc.FOOTER_H)
        self.assertEqual(sizes["nenhum"], rc.HEADER_H + 3 * rc.ROW_H + rc.FOOTER_H)  # só a mensagem: 3 linhas
        self.assertLess(sizes["um"], sizes["tres"])
        self.assertLessEqual(max(sizes.values()), full_h)
        # o painel acompanha, mas a escala (tamanho do texto) continua a da janela
        win = self.modules.create_module("relative")
        win.snapshot = T4.rel_snap(others=[{"idx": 1, "pct": 0.52}])
        win.setGeometry(0, 0, int(full_w), int(full_h))
        scale_few = self._paint_events(win, [(int(full_w), int(full_h))])[0][0]
        win.snapshot = T4.rel_snap(others=[{"idx": i, "pct": 0.5 + 0.01 * i} for i in range(1, 4)]
                                   + [{"idx": 10 + i, "pct": 0.5 - 0.01 * i} for i in range(1, 4)])
        scale_many = self._paint_events(win, [(int(full_w), int(full_h))])[0][0]
        self.assertEqual(scale_few, scale_many)  # mais ou menos carros não mexe no tamanho do texto

    def test_relative_draws_no_blank_rows_and_footer_follows_the_last_row(self):
        from kerbhud.core import relative as rc
        from kerbhud.ui import relative_module as rm
        T4 = self._rel_helpers()
        win = self.modules.create_module("relative")
        win.snapshot = T4.rel_snap(others=[{"idx": 1, "pct": 0.52, "driver_name": "Ana Silva"}])
        seen = []
        from unittest import mock
        with mock.patch.object(rm.RelativeModule, "_footer", staticmethod(lambda p, w, y, view: seen.append(y))):
            p = MagicMock(); win.paint_content(p, *win.design_size())
        self.assertEqual(seen, [rc.HEADER_H + 2 * rc.ROW_H])  # 1 carro + eu, sem linhas vazias
        t = self._texts(p)
        self.assertLess(t.index("Ana Silva"), t.index("Eu"))

    def test_relative_dims_absent_cars_and_tags_them(self):
        from kerbhud.core.model import CarStatus
        T4 = self._rel_helpers()
        win = self.modules.create_module("relative")
        win.snapshot = T4.rel_snap(others=[
            {"idx": 1, "pct": 0.52, "driver_name": "NaPista"},
            {"idx": 2, "pct": 0.53, "driver_name": "NaGaragem", "status": CarStatus.GARAGE},
            {"idx": 3, "pct": 0.47, "driver_name": "Saiu", "status": CarStatus.OUT, "in_session": False}])
        opacities, seen = [], {}
        p = MagicMock()
        p.setOpacity.side_effect = lambda v: opacities.append(v)
        p.drawText.side_effect = lambda *a: seen.setdefault(a[-1], opacities[-1] if opacities else 1.0)
        win.paint_content(p, *win.design_size())
        self.assertAlmostEqual(seen["NaPista"], 1.0, places=2)
        self.assertAlmostEqual(seen["NaGaragem"], 0.40, places=2)  # apagados
        self.assertAlmostEqual(seen["Saiu"], 0.40, places=2)
        self.assertEqual(self._texts(p).count("OUT"), 2)  # os dois ausentes marcados
        self.assertIn("—", self._texts(p))  # e sem tempo (dado velho)

    # ---- coluna NRG só quando o MEU carro tem NRG ---------------------------- #
    def _nrg_cars(self, mine_has, others_have=True):
        T4 = self._rel_helpers()
        cars = [T4.car(1, 1, "Hypercar", driver_name="Hyper", laps_completed=5, energy_pct=60.0 if others_have else None),
                T4.car(2, 2, "LMP2", driver_name="Eu", laps_completed=5, energy_pct=80.0 if mine_has else None),
                T4.car(3, 3, "LMP2", driver_name="Outro", laps_completed=5, energy_pct=None)]
        return T4.snap(cars, me=2)

    def test_nrg_column_exists_when_any_category_has_nrg_and_values_only_for_those(self):
        from kerbhud.core.standings import WIDTHS
        win = self.modules.create_module("standings")
        win.options = {"scale": 0.0005}
        full_w, full_h = win.design_size()
        # meu carro (LMP2) TEM NRG e o Hypercar também: coluna e as duas baterias
        win.snapshot = self._nrg_cars(mine_has=True)
        p = MagicMock(); win.paint_content(p, full_w, full_h)
        t = self._texts(p)
        self.assertIn("NRG", t)
        self.assertIn("80%", t)
        self.assertIn("60%", t)
        with_w = win.layout_size(full_w, full_h)[0]
        # meu carro NÃO tem NRG, mas a categoria Hypercar tem: a coluna CONTINUA e só a linha do Hypercar mostra valor
        win2 = self.modules.create_module("standings")
        win2.options = {"scale": 0.0005}
        win2.snapshot = self._nrg_cars(mine_has=False, others_have=True)
        p = MagicMock(); win2.paint_content(p, full_w, full_h)
        t = self._texts(p)
        self.assertIn("NRG", t)
        self.assertIn("60%", t)
        self.assertNotIn("80%", t)
        self.assertAlmostEqual(with_w, win2.layout_size(full_w, full_h)[0])
        # nenhuma categoria da sessão tem NRG: a coluna some inteira (painel mais estreito)
        win3 = self.modules.create_module("standings")
        win3.options = {"scale": 0.0005}
        win3.snapshot = self._nrg_cars(mine_has=False, others_have=False)
        p = MagicMock(); win3.paint_content(p, full_w, full_h)
        self.assertNotIn("NRG", self._texts(p))
        self.assertAlmostEqual(with_w - win3.layout_size(full_w, full_h)[0], WIDTHS["nrg"])

    def test_nrg_column_is_stable_and_follows_the_session(self):
        win = self.modules.create_module("standings")
        win.options = {"scale": 0.0005}
        w, h = win.design_size()

        def titles(snapshot):
            win.snapshot = snapshot
            p = MagicMock(); win.paint_content(p, w, h)
            return "NRG" in self._texts(p)
        self.assertTrue(titles(self._nrg_cars(mine_has=True)))
        self.assertTrue(titles(self._nrg_cars(mine_has=False, others_have=False)))  # leitura falhou: não pisca
        T4 = self._rel_helpers()
        gt3_only = T4.snap([T4.car(1, 1, "GT3", driver_name="Eu", energy_pct=None, laps_completed=3)], me=1)
        self.assertFalse(titles(gt3_only))  # nenhum carro presente é de categoria com NRG: some
        # spectator / sem piloto local: vale a categoria dos carros presentes
        no_me = self._nrg_cars(mine_has=True)
        no_me.player_idx = None
        for c in no_me.cars:
            c.is_player = False
        self.assertTrue(titles(no_me))

    def test_user_can_still_hide_the_nrg_column_manually(self):
        win = self.modules.create_module("standings")
        win.options = {"scale": 0.0005, "columns": {"nrg": False}}
        win.snapshot = self._nrg_cars(mine_has=True)
        p = MagicMock(); win.paint_content(p, *win.design_size())
        self.assertNotIn("NRG", self._texts(p))

    # ---- fade-in -------------------------------------------------------------- #
    def _frame_alphas(self, win, clock, snapshot, times):
        """Opacidade aplicada ao PRIMEIRO setOpacity de cada paintEvent, em cada instante de `times`."""
        from kerbhud.ui import module_base as mb
        win.snapshot = snapshot
        out = []
        for t in times:
            clock.t = t
            painter = MagicMock()
            painter.fontMetrics.return_value.horizontalAdvance.return_value = 80
            orig = mb.QPainter
            mb.QPainter = MagicMock(return_value=painter)
            try:
                win.paintEvent(None)
            finally:
                mb.QPainter = orig
            out.append(painter.setOpacity.call_args_list[0].args[0] if painter.setOpacity.called else None)
        return out

    def test_standings_fades_in_when_the_first_lap_time_appears(self):
        from kerbhud.core.standings import NUM_FONT_PX  # noqa: F401  (só para garantir o import do módulo)
        from kerbhud.ui import standings_module as sm
        win = self.modules.create_module("standings")
        win.options = {"scale": 0.0005}
        win.setGeometry(0, 0, 1000, 600)
        clock = self._fake_clock()
        win._clock = clock
        # 1) sem tempos: oculto, nada a desenhar (a opacidade do quadro é a normal)
        self._frame_alphas(win, clock, self._practice_snapshot(with_time=False), [10.0])
        self.assertFalse(win.is_animating)
        # 2) alguém faz a primeira volta em t=20: o painel NÃO surge de repente, entra com fade
        alphas = self._frame_alphas(win, clock, self._practice_snapshot(with_time=True),
                                    [20.0, 20.15, 20.3, 20.45, 20.6, 21.0])
        self.assertAlmostEqual(alphas[0], 0.0, places=6)  # começa invisível
        self.assertTrue(all(a < b for a, b in zip(alphas[:5], alphas[1:5])))  # cresce de forma contínua
        self.assertTrue(0.0 < alphas[2] < 1.0)
        self.assertAlmostEqual(alphas[4], 1.0, places=6)  # 0,6 s depois: totalmente visível
        self.assertAlmostEqual(alphas[5], 1.0, places=6)
        self.assertEqual(sm.FADE_IN_S, 0.6)

    def test_fade_keeps_repainting_until_it_finishes_then_stops(self):
        win = self.modules.create_module("standings")
        win.options = {"scale": 0.0005}
        win.setGeometry(0, 0, 1000, 600)
        clock = self._fake_clock()
        win._clock = clock
        snap = self._practice_snapshot(with_time=True)
        self._frame_alphas(win, clock, snap, [5.0])
        painter = self._paint_event_calls(win)  # um quadro de conteúdo no meio do fade para ver o repaint
        self.assertTrue(win.is_animating)  # o gerenciador continua pedindo repintura durante o fade
        self._frame_alphas(win, clock, snap, [6.0])
        self.assertFalse(win.is_animating)  # terminou

    def test_fade_content_is_actually_faded_not_just_the_background(self):
        """As linhas usam a opacidade efetiva (usuário x fade); antes elas ignorariam o fade e apareceriam secas."""
        win = self.modules.create_module("standings")
        win.options = {"scale": 0.0005}
        win.setGeometry(0, 0, 1000, 600)
        clock = self._fake_clock()
        win._clock = clock
        win.set_opacity(0.8)  # o usuário escolheu 80%
        from kerbhud.ui import module_base as mb
        win.snapshot = self._practice_snapshot(with_time=True)
        clock.t = 30.0
        win._fade_t0 = None
        win._had_content = False
        painter = MagicMock()
        painter.fontMetrics.return_value.horizontalAdvance.return_value = 80
        orig = mb.QPainter
        mb.QPainter = MagicMock(return_value=painter)
        try:
            win.paintEvent(None)  # t=0 do fade
            clock.t = 30.3
            painter.reset_mock()
            win.paintEvent(None)  # metade do fade
        finally:
            mb.QPainter = orig
        opacities = [c.args[0] for c in painter.setOpacity.call_args_list]
        self.assertTrue(opacities)
        self.assertTrue(all(o <= 0.8 + 1e-9 for o in opacities))  # nenhuma linha passa da opacidade do quadro
        self.assertLess(max(opacities), 0.8)  # e todas estão abaixo do máximo do usuário (fade em curso)
        self.assertAlmostEqual(win.opacity, 0.8)  # a opacidade salva no layout NÃO é afetada pelo fade

    def test_resizing_or_changing_rows_does_not_repeat_the_fade(self):
        win = self.modules.create_module("standings")
        win.options = {"scale": 0.0005}
        win.setGeometry(0, 0, 1000, 600)
        clock = self._fake_clock()
        win._clock = clock
        snap = self._practice_snapshot(with_time=True)
        self._frame_alphas(win, clock, snap, [1.0, 3.0])  # fade já terminou
        win.setGeometry(0, 0, 700, 400)  # redimensionou
        self.assertEqual(self._frame_alphas(win, clock, snap, [3.1]), [1.0])
        snap2 = self._practice_snapshot(with_time=True)
        snap2.cars[0].best_lap = 100.0  # outro piloto fez tempo: a lista muda, mas já havia conteúdo
        self.assertEqual(self._frame_alphas(win, clock, snap2, [3.2]), [1.0])

    def test_fade_runs_again_when_content_disappears_and_comes_back(self):
        win = self.modules.create_module("standings")
        win.options = {"scale": 0.0005}
        win.setGeometry(0, 0, 1000, 600)
        clock = self._fake_clock()
        win._clock = clock
        self._frame_alphas(win, clock, self._practice_snapshot(with_time=True), [1.0, 3.0])
        self._frame_alphas(win, clock, self._practice_snapshot(with_time=False), [4.0])  # sessão nova: sem tempos
        again = self._frame_alphas(win, clock, self._practice_snapshot(with_time=True), [5.0, 5.3])
        self.assertAlmostEqual(again[0], 0.0, places=6)
        self.assertTrue(0.0 < again[1] < 1.0)

    def test_other_modules_have_no_fade(self):
        for module_id in ("relative", "inputs", "status"):
            win = self.modules.create_module(module_id)
            self.assertEqual(win.frame_alpha(400, 200), 1.0, module_id)
            self.assertEqual(win.effective_opacity, win.opacity)

    # ---- logos das fabricantes: arquivo, nome em texto e "o que falta" ---------- #
    def _brand_cars(self):
        T4 = self._rel_helpers()
        cars = [T4.car(1, 1, "LMP3", driver_name="Piloto Ligier", vehicle_raw="Ligier JS P320"),
                T4.car(2, 2, "FF", driver_name="Piloto Ray", vehicle_raw="Ray FF1600"),
                T4.car(3, 3, "FF", driver_name="Piloto Generico", vehicle_raw="Sprint Car"),
                T4.car(4, 4, "GT3", driver_name="Piloto Porsche", vehicle_raw="Porsche 911 GT3 R")]
        return T4.snap(cars, me=2)

    def test_brand_without_a_logo_file_shows_the_manufacturer_name(self):
        from kerbhud.ui.context import ModuleContext

        class Logos(self.FakeLogos):
            wordmark = True
        logos = Logos(available={"porsche"})  # só a Porsche tem arquivo
        win = self.modules.create_module("standings", ModuleContext(logos=logos))
        win.snapshot = self._brand_cars()
        p = MagicMock(); win.paint_content(p, *win.design_size())
        t = self._texts(p)
        self.assertIn("LIGIER", t)  # sem arquivo: o nome da fabricante, em texto
        self.assertIn("RAY", t)
        self.assertNotIn("PORSCHE", t)  # com arquivo: só a logo real (nada de texto)
        self.assertIn("porsche", logos.keys)
        self.assertNotIn("SPRINT CAR", t)  # carro genérico: nenhuma marca inventada
        self.assertEqual(sum(1 for x in t if x in ("LIGIER", "RAY", "PORSCHE")), 2)

    def test_wordmark_can_be_turned_off_and_never_appears_without_a_cache(self):
        from kerbhud.ui.context import ModuleContext

        class Off(self.FakeLogos):
            wordmark = False
        for logos in (Off(available=set()), None, self.FakeLogos(available=set())):  # este último nem tem o atributo
            win = self.modules.create_module("standings", ModuleContext(logos=logos))
            win.snapshot = self._brand_cars()
            p = MagicMock(); win.paint_content(p, *win.design_size())
            t = self._texts(p)
            self.assertNotIn("LIGIER", t)
            self.assertNotIn("RAY", t)

    def test_wordmark_layout_one_or_two_lines_fitted_to_the_column(self):
        from kerbhud.ui import icons
        cases = {"Ray": ["RAY"], "Dallara": ["DALLARA"], "Skip Barber": ["SKIP", "BARBER"],
                 "Aston Martin": ["ASTON", "MARTIN"], "Isotta Fraschini": ["ISOTTA", "FRASCHINI"],
                 "Mercedes-AMG": ["MERCEDES", "AMG"], "Lamborghini": ["LAMBORGHINI"]}
        for name, lines in cases.items():
            p = MagicMock()
            icons.wordmark(p, 100.0, 50.0, name)
            drawn = [c.args[-1] for c in p.drawText.call_args_list]
            self.assertEqual(drawn, lines, name)
            for c in p.drawText.call_args_list:
                r = c.args[0]
                self.assertLessEqual(r.width(), icons.WORDMARK_W + 1e-9)
                self.assertAlmostEqual(r.left() + r.width() / 2, 100.0)  # centralizado na coluna
        # com fonte larga cada linha encolhe até caber (nunca abaixo de 7)
        import types
        from kerbhud.ui import module_base as mb

        def wide_font(name, em):
            mb.clear_font_caches()  # o ajuste de fonte é guardado em cache: recomeça do zero
            state = {"px": 0.0}
            orig = (icons.make_font, mb.make_font)
            icons.make_font = mb.make_font = lambda px, bold=False, semibold=False: types.SimpleNamespace(px=px)
            p = MagicMock()
            p.setFont.side_effect = lambda f: state.update(px=f.px)
            p.fontMetrics.return_value.horizontalAdvance.side_effect = lambda t: len(t) * em * state["px"]
            try:
                icons.wordmark(p, 0.0, 0.0, name)
            finally:
                icons.make_font, mb.make_font = orig
            return p.setFont.call_args_list[-1].args[0].px
        px = wide_font("Ferrari", 0.60)  # 7 letras numa fonte larga: encolhe e passa a caber
        self.assertLess(px, 12.0)
        self.assertGreaterEqual(px, 7.0)
        self.assertLessEqual(len("FERRARI") * 0.60 * px, icons.WORDMARK_W + 1e-6)
        # palavra única muito longa numa fonte larga: vai até o mínimo (7) e não some nem fica menor que isso
        self.assertEqual(wide_font("Lamborghini", 0.60), 7.0)
        # com uma fonte estreita (tipo DIN, ~0,5 em) as marcas longas ainda ficam legíveis (>= 7 e cabem)
        px = wide_font("Lamborghini", 0.50)
        self.assertGreaterEqual(px, 7.0)
        self.assertLessEqual(len("LAMBORGHINI") * 0.50 * px, icons.WORDMARK_W + 1e-6)

    def test_logo_cache_reads_any_format_remembers_missing_brands_and_clears(self):
        from kerbhud.core.brands import brand_for
        from kerbhud.ui import icons
        ray, bmw = brand_for("Ray FF1600"), brand_for("BMW M4")
        loaded = []

        class Pm:
            def __init__(self, tag): self.tag = tag
            def width(self): return 60
            def height(self): return 30

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            cache = icons.LogoCache(d)
            cache._load = lambda path: (loaded.append(path.name) or Pm(path.suffix))
            (d / "bmw.webp").write_bytes(b"w")  # formato que não é png
            p = MagicMock()
            self.assertTrue(cache.draw(p, bmw, 10.0, 10.0, 30.0))
            self.assertEqual(loaded, ["bmw.webp"])
            self.assertFalse(cache.draw(p, ray, 10.0, 10.0, 30.0))  # sem arquivo
            self.assertEqual(list(cache.missing_seen), ["ray"])  # anotada para "Logos que faltam"
            self.assertNotIn("bmw", cache.missing_seen)
            cache.draw(p, bmw, 0, 0)  # segunda vez: vem do cache, não relê o arquivo
            self.assertEqual(loaded, ["bmw.webp"])
            (d / "ray.svg").write_text("<svg/>")  # o usuário copiou o arquivo e mandou recarregar
            cache.clear()
            self.assertEqual(cache.missing_seen, {})
            self.assertTrue(cache.draw(p, ray, 0, 0))
            self.assertEqual(loaded[-1], "ray.svg")
            self.assertEqual(cache.missing_seen, {})
            # fallback: Corvette sem arquivo usa o da Chevrolet
            corvette = brand_for("Corvette C8.R")
            (d / "chevrolet.png").write_bytes(b"p")
            self.assertTrue(cache.draw(p, corvette, 0, 0))
            self.assertEqual(loaded[-1], "chevrolet.png")

    def test_standings_collects_the_brands_that_are_missing_from_the_session(self):
        from kerbhud.ui import icons
        from kerbhud.ui.context import ModuleContext
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "porsche.png").write_bytes(b"p")
            cache = icons.LogoCache(Path(d))
            cache._load = lambda path: type("Pm", (), {"width": lambda s: 50, "height": lambda s: 50})()
            win = self.modules.create_module("standings", ModuleContext(logos=cache))
            win.snapshot = self._brand_cars()
            win.paint_content(MagicMock(), *win.design_size())
            self.assertEqual(sorted(cache.missing_seen), ["ligier", "ray"])  # só as que existem no jogo e faltam
            self.assertEqual(cache.missing_seen["ray"].display_name, "Ray")

    def test_wordmark_setting_defaults_to_on(self):
        from kerbhud.core.engine import load_settings
        self.assertTrue(load_settings().get("logo_wordmark"))

    def test_icons_helpers(self):
        from kerbhud.ui import icons
        self.assertEqual(icons.shade("#102030", 2.0), "#204060")
        self.assertEqual(icons.shade("#ffffff", 5.0), "#ffffff")  # satura sem estourar
        self.assertEqual(icons.shade("lixo", 0.5), "lixo")
        self.assertIsNone(icons.LogoCache(None).get("bmw"))
        from kerbhud.core.brands import brand_for
        self.assertFalse(icons.brand_logo(MagicMock(), 0, 0, brand_for("BMW M4"), None))  # sem cache: nada
        fake = self.FakeLogos()
        self.assertTrue(icons.brand_logo(MagicMock(), 0, 0, brand_for("BMW M4"), fake))
        self.assertEqual(fake.keys, ["bmw"])
        self.assertFalse(icons.brand_logo(MagicMock(), 0, 0, brand_for("BMW M4"), self.FakeLogos(available=set())))
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(icons.LogoCache(Path(d)).get("bmw"))  # arquivo inexistente: cai no selo

    def test_manager_set_column_persists(self):
        om = self.om
        om.current_screens = lambda: ([self.ScreenInfo("S1", 0, 0, 1920, 1080)], "S1")
        engine = MagicMock(); engine.latest.return_value = self.snap
        with tempfile.TemporaryDirectory() as d:
            store = self.LayoutStore(Path(d) / "layouts"); store.ensure_defaults()
            mgr = om.OverlayManager(engine, store, {"ui_hz": 30})
            mgr.load_active()
            mgr.set_column("standings", "tire", False)
            mgr.set_option("standings", "scope", "class")
            mgr.set_option("standings", "show_profile", False)
            mgr.set_option("relative", "ahead", 2)
            mgr._flush_save()
            lay = store.load(mgr.layout.name)
            self.assertFalse(lay.modules["standings"].options["columns"]["tire"])
            self.assertEqual(lay.modules["standings"].options["scope"], "class")
            self.assertFalse(lay.modules["standings"].options["show_profile"])
            self.assertEqual(lay.modules["relative"].options["ahead"], 2)

    def test_status_module_shows_version_and_demo_badge(self):
        from kerbhud import __version__
        from kerbhud.core.model import Sim, Snapshot
        win = self.modules.create_module("status")
        win.snapshot = None
        p = MagicMock(); win.paint_content(p, *win.design_size())
        t = self._texts(p)
        self.assertIn(f"v{__version__}", t)  # a versão aparece no próprio overlay
        self.assertIn("SEM SIMULADOR", t)
        win.snapshot = self.snap  # DEMO
        p = MagicMock(); win.paint_content(p, *win.design_size())
        t = self._texts(p)
        self.assertIn(f"v{__version__}", t)
        self.assertIn("DEMO", t)
        win.snapshot = Snapshot(sim=Sim.LMU, connected=True)
        p = MagicMock(); win.paint_content(p, *win.design_size())
        self.assertIn("LE MANS ULTIMATE", self._texts(p))  # nome longo continua inteiro

    def test_font_caches_reuse_objects_and_fit_results(self):
        from kerbhud.ui import module_base as mb

        class F:  # QFont mínimo: cada chamada cria um objeto diferente
            DemiBold = 63
            def __init__(self): self.px = 0
            def setFamilies(self, f): pass
            def setPixelSize(self, px): self.px = px
            def setBold(self, b): pass
            def setWeight(self, w): pass
        orig = mb.QFont
        mb.QFont = F
        try:
            self.assertIs(mb.make_font(17, True), mb.make_font(17, True))  # mesma fonte: mesmo objeto
            self.assertIsNot(mb.make_font(17, True), mb.make_font(18, True))
            self.assertEqual(mb.make_font(18, True).px, 18)
        finally:
            mb.QFont = orig
        mb.clear_font_caches()
        calls = []
        p = MagicMock()
        p.fontMetrics.return_value.horizontalAdvance.side_effect = lambda t: calls.append(t) or 10.0
        mb.fit_font(p, "Fulano", 18, 200)
        first = len(calls)
        mb.fit_font(p, "Fulano", 18, 200)
        self.assertEqual(len(calls), first)  # segunda vez: resultado vem do cache, sem medir de novo
        mb.fit_font(p, "Fulano", 18, 150)  # outro espaço disponível: mede de novo
        self.assertGreater(len(calls), first)

    def test_app_module_imports(self):
        from kerbhud.ui import app  # noqa: F401


if __name__ == "__main__":
    unittest.main()
