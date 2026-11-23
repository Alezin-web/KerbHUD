"""Volante mostrado no Inputs (sem Qt, testável): estilos genéricos desenhados pelo KerbHUD ou uma imagem da pessoa.

O KerbHUD não traz fotos nem desenhos de volantes de marcas (são produtos e imagens de terceiros): a pessoa escolhe um estilo
genérico ou aponta para a imagem que quiser (PNG, JPG, WEBP ou BMP, até 8 MB), que é só lida do disco.
"""
from __future__ import annotations

import os

WHEEL_STYLES = (("classic", "Clássico (aro redondo)"), ("gt", "GT (aro com base reta)"),
                ("formula", "Fórmula (retangular)"), ("custom", "Minha imagem"), ("hidden", "Sem volante"))
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def get_wheel_style(options: dict) -> str:
    v = options.get("wheel_style")
    return v if v in {k for k, _l in WHEEL_STYLES} else "classic"


def get_wheel_image(options: dict) -> str:
    v = options.get("wheel_image")
    return v if isinstance(v, str) else ""


def valid_image(path: str) -> bool:
    """Arquivo existente, de imagem e de tamanho razoável."""
    try:
        return bool(path) and path.lower().endswith(IMAGE_EXTS) and os.path.isfile(path) \
            and os.path.getsize(path) <= MAX_IMAGE_BYTES
    except OSError:
        return False
