"""Acesso SOMENTE LEITURA à memória compartilhada dos simuladores.

Decisão de segurança importante: usamos `OpenFileMappingW` +
`MapViewOfFile(FILE_MAP_READ)` em vez de `mmap.mmap(..., tagname=...)`.
O `mmap` do Python usa `CreateFileMapping`, que CRIA um mapeamento com aquele
nome caso ele ainda não exista. Se o overlay fosse aberto antes do simulador,
ele poderia criar o mapeamento antes do jogo e interferir no funcionamento
dele. `OpenFileMapping` nunca cria nada: se o simulador não publicou o
mapeamento, a abertura simplesmente falha.
"""
from __future__ import annotations

import ctypes
import sys
from abc import ABC, abstractmethod
from typing import Callable


class MappingNotFound(Exception):
    """O simulador (ainda) não publicou o mapeamento."""


class MappingBoundsError(Exception):
    """Leitura fora dos limites do mapeamento (layout diferente do esperado)."""


class MemoryView(ABC):
    @property
    @abstractmethod
    def size(self) -> int: ...

    @abstractmethod
    def read(self, offset: int, length: int) -> bytes: ...

    def close(self) -> None:  # pragma: no cover - trivial
        pass

    def _check(self, offset: int, length: int) -> None:
        if offset < 0 or length < 0 or offset + length > self.size:
            raise MappingBoundsError(
                f"leitura fora do mapeamento: offset={offset} len={length} size={self.size}"
            )


class BytesMapping(MemoryView):
    """Mapeamento em memória comum. Usado em testes e em arquivos de captura."""

    def __init__(self, data: bytes | bytearray):
        self._data = data

    @property
    def size(self) -> int:
        return len(self._data)

    def read(self, offset: int, length: int) -> bytes:
        self._check(offset, length)
        return bytes(self._data[offset : offset + length])

    def replace(self, data: bytes | bytearray) -> None:
        self._data = data


# --------------------------------------------------------------------------- #
# Implementação Windows
# --------------------------------------------------------------------------- #
FILE_MAP_READ = 0x0004


class _MemoryBasicInformation(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_ulong),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
    ]


def _kernel32():
    k = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    k.OpenFileMappingW.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_wchar_p]
    k.OpenFileMappingW.restype = ctypes.c_void_p
    k.MapViewOfFile.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_size_t,
    ]
    k.MapViewOfFile.restype = ctypes.c_void_p
    k.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    k.UnmapViewOfFile.restype = ctypes.c_int
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    k.CloseHandle.restype = ctypes.c_int
    k.VirtualQuery.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    k.VirtualQuery.restype = ctypes.c_size_t
    return k


class WinNamedMapping(MemoryView):
    def __init__(self, name: str):
        if sys.platform != "win32":
            raise MappingNotFound("memória compartilhada nomeada só existe no Windows")
        k = _kernel32()
        handle = k.OpenFileMappingW(FILE_MAP_READ, 0, name)
        if not handle:
            raise MappingNotFound(f"{name} (erro {ctypes.get_last_error()})")
        base = k.MapViewOfFile(handle, FILE_MAP_READ, 0, 0, 0)  # 0 = mapeamento inteiro
        if not base:
            err = ctypes.get_last_error()
            k.CloseHandle(handle)
            raise MappingNotFound(f"{name}: MapViewOfFile falhou (erro {err})")
        mbi = _MemoryBasicInformation()
        k.VirtualQuery(base, ctypes.byref(mbi), ctypes.sizeof(mbi))
        self._k = k
        self._handle = handle
        self._base = base
        self._size = int(mbi.RegionSize)
        self.name = name

    @property
    def size(self) -> int:
        return self._size

    def read(self, offset: int, length: int) -> bytes:
        if not self._base:
            raise MappingNotFound(f"{self.name} já foi fechado")
        self._check(offset, length)
        return ctypes.string_at(self._base + offset, length)

    def close(self) -> None:
        if self._base:
            self._k.UnmapViewOfFile(self._base)
            self._base = None
        if self._handle:
            self._k.CloseHandle(self._handle)
            self._handle = None


def open_named_mapping(name: str) -> MemoryView:
    """Abre um mapeamento nomeado existente, somente leitura."""
    return WinNamedMapping(name)


Opener = Callable[[], MemoryView]
