"""Identidade visual do KerbHUD (sem Qt): paleta e a geometria do logo, usadas pelo ícone, pelos PNGs e pelo changelog.

Conceito: *kerb* é a zebra (o "curb") de pista, vermelha e branca. O logo é um **K** de cantos cortados sobre uma faixa
de zebra inclinada, dentro de um quadrado arredondado cor de asfalto. Tudo em coordenadas de 0 a 1 (quadrado unitário).
"""
from __future__ import annotations

NAME = "KerbHUD"
TAGLINE_PT = "Seu painel de corrida, só de leitura."
TAGLINE_EN = "Your racing HUD, read-only."

ASPHALT = "#0b0b0d"   # fundo (mesmo do tema do overlay)
PANEL = "#121216"
LINE = "#2a2a31"
RED = "#e10600"       # vermelho da zebra
WHITE = "#f4f4f5"     # branco da zebra
GRAY = "#8b8b95"

TILE_RADIUS = 0.22

# O "K": haste, braço de cima (vermelho) e perna de baixo. Polígonos em (x, y) do quadrado unitário.
K_STEM = ((0.20, 0.13), (0.35, 0.13), (0.35, 0.67), (0.20, 0.67))
K_ARM = ((0.35, 0.40), (0.62, 0.13), (0.82, 0.13), (0.55, 0.40))
K_LEG = ((0.35, 0.40), (0.55, 0.40), (0.82, 0.67), (0.62, 0.67))

# Faixa de zebra no pé do quadrado: paralelogramas alternando vermelho/branco.
KERB_Y0, KERB_Y1 = 0.78, 0.92
KERB_STRIPE_W = 0.14
KERB_SLANT = 0.08


def kerb_stripes() -> list[tuple[tuple[tuple[float, float], ...], str]]:
    """Paralelogramas da zebra: [(pontos, cor), ...]; os de fora do quadrado são recortados por quem desenha."""
    out = []
    x, i = -KERB_SLANT - KERB_STRIPE_W, 0
    while x < 1.0 + KERB_SLANT:
        pts = ((x + KERB_SLANT, KERB_Y0), (x + KERB_SLANT + KERB_STRIPE_W, KERB_Y0),
               (x + KERB_STRIPE_W, KERB_Y1), (x, KERB_Y1))
        out.append((pts, RED if i % 2 == 0 else WHITE))
        x += KERB_STRIPE_W
        i += 1
    return out


def k_parts() -> list[tuple[tuple[tuple[float, float], ...], str]]:
    return [(K_STEM, WHITE), (K_ARM, RED), (K_LEG, WHITE)]
