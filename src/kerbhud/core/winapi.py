"""Helpers Win32 via ctypes (sem Qt). No-ops fora do Windows.

Tudo aqui afeta APENAS as janelas do próprio overlay (estilo, z-order) e registra
atalhos globais. Nada toca em processos ou janelas do simulador.
"""
from __future__ import annotations

import sys
from typing import Optional

IS_WIN = sys.platform == "win32"

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000

_user32 = None


def _u32():
    global _user32
    if _user32 is None:
        import ctypes
        from ctypes import wintypes
        u = ctypes.WinDLL("user32", use_last_error=True)  # type: ignore[attr-defined]
        get = getattr(u, "GetWindowLongPtrW", None) or u.GetWindowLongW
        setl = getattr(u, "SetWindowLongPtrW", None) or u.SetWindowLongW
        get.argtypes = [wintypes.HWND, ctypes.c_int]
        get.restype = ctypes.c_ssize_t
        setl.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        setl.restype = ctypes.c_ssize_t
        u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wintypes.UINT]
        u.SetWindowPos.restype = wintypes.BOOL
        u.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        u.RegisterHotKey.restype = wintypes.BOOL
        u.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        u.UnregisterHotKey.restype = wintypes.BOOL
        u._get, u._set = get, setl  # type: ignore[attr-defined]
        _user32 = u
    return _user32


def _modify_exstyle(hwnd: int, add: int = 0, remove: int = 0) -> bool:
    if not IS_WIN or not hwnd:
        return False
    u = _u32()
    cur = u._get(hwnd, GWL_EXSTYLE)  # type: ignore[attr-defined]
    new = (cur | add) & ~remove
    if new != cur:
        u._set(hwnd, GWL_EXSTYLE, new)  # type: ignore[attr-defined]
    return True


def set_click_through(hwnd: int, enabled: bool) -> bool:
    """Cliques atravessam a janela (vão para o simulador) quando `enabled`."""
    flags = WS_EX_LAYERED | WS_EX_TRANSPARENT
    return _modify_exstyle(hwnd, add=flags) if enabled else _modify_exstyle(hwnd, add=WS_EX_LAYERED, remove=WS_EX_TRANSPARENT)


def set_no_activate(hwnd: int) -> bool:
    """Janela nunca rouba o foco do simulador e não aparece na barra de tarefas."""
    return _modify_exstyle(hwnd, add=WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)


def begin_timer_resolution(ms: int = 1) -> bool:
    """Pede ao Windows temporizador de ~1 ms (o padrão é ~15,6 ms: esperas e QTimer ficam irregulares, e a overlay "engasga")."""
    if not IS_WIN:
        return False
    try:
        import ctypes
        return ctypes.windll.winmm.timeBeginPeriod(int(ms)) == 0
    except Exception:  # noqa: BLE001 - só uma melhoria de ritmo; nunca pode impedir de abrir
        return False


def end_timer_resolution(ms: int = 1) -> None:
    if not IS_WIN:
        return
    try:
        import ctypes
        ctypes.windll.winmm.timeEndPeriod(int(ms))
    except Exception:  # noqa: BLE001
        pass


def set_topmost(hwnd: int, on: bool = True) -> bool:
    if not IS_WIN or not hwnd:
        return False
    return bool(_u32().SetWindowPos(hwnd, HWND_TOPMOST if on else HWND_NOTOPMOST, 0, 0, 0, 0,
                                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE))


#: janelas do próprio Windows que a pessoa usa com o mouse: barra de tarefas, bandeja, menus, Iniciar, pesquisa
SHELL_CLASSES = frozenset({
    "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "TrayNotifyWnd", "NotifyIconOverflowWindow",
    "TopLevelWindowForOverflowXamlIsland", "XamlExplorerHostIslandWindow", "Windows.UI.Core.CoreWindow",
    "#32768",  # menu de contexto (inclusive o da bandeja)
    "TaskListThumbnailWnd", "TaskListOverlayWnd", "MultitaskingViewFrame", "Shell_InputSwitchTopLevelWindow",
    "ForegroundStaging", "DV2ControlHost", "SearchPane",
})


def is_shell_class(name: str) -> bool:
    return name in SHELL_CLASSES


def foreground_class() -> str:
    """Nome da classe da janela em primeiro plano ("" se não der para saber / fora do Windows)."""
    if not IS_WIN:
        return ""
    try:
        import ctypes
        u = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return ""
        buf = ctypes.create_unicode_buffer(256)
        return buf.value if u.GetClassNameW(hwnd, buf, 256) else ""
    except (OSError, AttributeError):
        return ""


def shell_has_focus() -> bool:
    """A pessoa está usando a barra de tarefas, a bandeja, um menu ou o Iniciar? O overlay não deve cobri-los."""
    return is_shell_class(foreground_class())


# --------------------------------------------------------------------------- #
# Atalhos globais
# --------------------------------------------------------------------------- #
_NAMED_KEYS = {"SPACE": 0x20, "TAB": 0x09, "ENTER": 0x0D, "ESC": 0x1B, "INSERT": 0x2D, "DELETE": 0x2E,
               "HOME": 0x24, "END": 0x23, "PAGEUP": 0x21, "PAGEDOWN": 0x22,
               "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28}
_MODS = {"CTRL": MOD_CONTROL, "CONTROL": MOD_CONTROL, "ALT": MOD_ALT, "SHIFT": MOD_SHIFT,
         "WIN": MOD_WIN, "META": MOD_WIN}


def parse_hotkey(text: str) -> tuple[int, int]:
    """"Ctrl+Alt+E" -> (modificadores, código de tecla virtual). Levanta ValueError."""
    parts = [p.strip().upper() for p in text.split("+") if p.strip()]
    if len(parts) < 2:
        raise ValueError(f"atalho precisa de modificador + tecla: {text!r}")
    mods = 0
    for m in parts[:-1]:
        if m not in _MODS:
            raise ValueError(f"modificador desconhecido: {m!r}")
        mods |= _MODS[m]
    key = parts[-1]
    if len(key) == 1 and key.isalnum() and key.isascii():
        vk = ord(key)
    elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    elif key in _NAMED_KEYS:
        vk = _NAMED_KEYS[key]
    else:
        raise ValueError(f"tecla desconhecida: {key!r}")
    return mods, vk


def set_app_user_model_id(app_id: str) -> bool:
    """Windows: identifica o programa na barra de tarefas (senão ela agrupa com o Python e mostra o ícone dele)."""
    if not IS_WIN:
        return False
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(str(app_id))
        return True
    except (OSError, AttributeError):
        return False


class HotkeyRegistry:
    """Registra atalhos globais (somente Windows). Falhas são reportadas, não fatais."""

    def __init__(self) -> None:
        self._actions: dict[int, str] = {}
        self.errors: list[str] = []

    def register_all(self, mapping: dict[str, str]) -> None:
        self.unregister_all()
        next_id = 1
        for action, text in mapping.items():
            if not text:
                continue
            try:
                mods, vk = parse_hotkey(text)
            except ValueError as exc:
                self.errors.append(f"{action}: {exc}")
                continue
            if not IS_WIN:
                continue
            if _u32().RegisterHotKey(None, next_id, mods | MOD_NOREPEAT, vk):
                self._actions[next_id] = action
            else:
                self.errors.append(f"{action}: {text} já está em uso por outro programa")
            next_id += 1

    def action_for(self, hotkey_id: int) -> Optional[str]:
        return self._actions.get(hotkey_id)

    def unregister_all(self) -> None:
        if IS_WIN:
            for hid in list(self._actions):
                _u32().UnregisterHotKey(None, hid)
        self._actions.clear()
