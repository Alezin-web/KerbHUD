"""Gera as imagens da identidade do KerbHUD (logo, ícone .ico, banners do changelog, esquemas do guia). Requer Pillow.

Uso (na raiz do projeto):  PYTHONPATH=src python tools/make_brand_assets.py
As imagens são ilustrações desenhadas em código (não capturas de tela do programa).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from kerbhud.core import brand as B

ROOT = Path(__file__).resolve().parents[1]
SS = 4  # supersampling para bordas lisas


def _font(size: int, bold: bool = True, italic: bool = False):
    names = []
    if bold and italic:
        names = ["/usr/share/fonts/opentype/inter/Inter-BlackItalic.otf", "/usr/share/fonts/opentype/inter/Inter-SemiBoldItalic.otf",
                 "arialbi.ttf", "/usr/share/fonts/truetype/freefont/FreeSansBoldOblique.ttf"]
    elif bold:
        names = ["/usr/share/fonts/opentype/inter/Inter-Bold.otf", "arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    else:
        names = ["/usr/share/fonts/opentype/inter/Inter-Regular.otf", "arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


def logo(size: int = 512) -> Image.Image:
    """O quadrado do logo (K + zebra) com fundo transparente fora dos cantos arredondados."""
    big = size * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    tile = Image.new("RGBA", (big, big), B.ASPHALT)
    d = ImageDraw.Draw(tile)
    P = lambda pts: [(x * big, y * big) for x, y in pts]  # noqa: E731
    for pts, color in B.kerb_stripes():
        d.polygon(P(pts), fill=color)
    for pts, color in B.k_parts():
        d.polygon(P(pts), fill=color)
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=int(B.TILE_RADIUS * big), fill=255)
    img.paste(tile, (0, 0), mask)
    ImageDraw.Draw(img).rounded_rectangle((SS, SS, big - SS - 1, big - SS - 1), radius=int(B.TILE_RADIUS * big),
                                          outline=B.LINE, width=SS * 2)
    return img.resize((size, size), Image.LANCZOS)


def wordmark(height: int) -> Image.Image:
    """"KERB" em branco + "HUD" em vermelho, itálico pesado."""
    f = _font(int(height * 0.95), True, True)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    w1 = probe.textlength("KERB", font=f)
    w2 = probe.textlength("HUD", font=f)
    img = Image.new("RGBA", (int(w1 + w2 + height * 0.1), int(height * 1.3)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((0, 0), "KERB", font=f, fill=B.WHITE)
    d.text((w1 + height * 0.06, 0), "HUD", font=f, fill=B.RED)
    return img.crop(img.getbbox())


def kerb_strip(w: int, h: int, offset: float = 0.0) -> Image.Image:
    img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sw, slant = h * 1.4 * SS, h * SS * 0.8
    x, i = -slant - sw + offset, 0
    while x < w * SS + slant:
        d.polygon([(x + slant, 0), (x + slant + sw, 0), (x + sw, h * SS), (x, h * SS)], fill=B.RED if i % 2 == 0 else B.WHITE)
        x += sw
        i += 1
    return img.resize((w, h), Image.LANCZOS)


def banner(version: str, subtitle: str, width: int = 960, height: int = 240) -> Image.Image:
    img = Image.new("RGBA", (width, height), B.ASPHALT)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, width, 6), fill=B.RED)
    img.alpha_composite(logo(150), (36, 36))
    wm = wordmark(64)
    img.alpha_composite(wm, (216, 46))
    d.text((216, 46 + wm.height + 14), subtitle, font=_font(26, False), fill=B.GRAY)
    d.text((width - 36, 44), f"v{version}", font=_font(40, True, True), fill=B.WHITE, anchor="ra")
    img.alpha_composite(kerb_strip(width, 22), (0, height - 22))
    return img.convert("RGB")


def tree_diagram(app: str = B.NAME) -> Image.Image:
    img = Image.new("RGBA", (960, 330), B.ASPHALT)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 960, 6), fill=B.RED)
    d.text((30, 26), f"{app} folder", font=_font(26, True), fill=B.WHITE)
    rows = [(f"{app}.exe  /  src/", 0, B.WHITE), ("dados/   (yours only; updates never touch it)", 0, "#14c05a"),
            ("logos/   flags/   badges/", 1, B.GRAY), ("layouts/   tracks/", 1, B.GRAY),
            (".backup/   (copy of what an update replaced)", 0, B.GRAY), ("CHANGELOG.md", 0, B.GRAY)]
    y = 80
    for t, lvl, c in rows:
        d.text((50 + lvl * 40, y), t, font=_font(24, False), fill=c)
        y += 40
    img.alpha_composite(kerb_strip(960, 14), (0, 316))
    return img.convert("RGB")


def window_map(lang: str) -> Image.Image:
    """Esquema ilustrativo da janela principal, com legendas numeradas."""
    pt = lang == "pt"
    W, H = 960, 560
    img = Image.new("RGBA", (W, H), "#0f0f12")
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 6), fill=B.RED)
    # janela
    x0, y0, x1, y1 = 40, 40, 520, 520
    d.rounded_rectangle((x0, y0, x1, y1), radius=10, fill=B.PANEL, outline=B.LINE, width=2)
    d.rectangle((x0 + 2, y0 + 2, x1 - 2, y0 + 34), fill="#1c1c22")
    img.alpha_composite(logo(24), (x0 + 10, y0 + 6))
    d.text((x0 + 44, y0 + 8), "KerbHUD", font=_font(18, True), fill=B.WHITE)
    # menu bar
    mx = x0 + 16
    for m in ("Overlay", "Simulador" if pt else "Simulator", "Config", "Ferramentas" if pt else "Tools", "Janela" if pt else "Window", "Ajuda" if pt else "Help"):
        d.text((mx, y0 + 46), m, font=_font(15, False), fill=B.GRAY)
        mx += int(d.textlength(m, font=_font(15, False))) + 16
    # update bar
    d.rounded_rectangle((x0 + 12, y0 + 78, x1 - 12, y0 + 118), radius=6, fill="#18181d")
    d.text((x0 + 24, y0 + 89), "KerbHUD 0.17.0", font=_font(15, True), fill=B.WHITE)
    d.rounded_rectangle((x1 - 220, y0 + 86, x1 - 24, y0 + 110), radius=5, fill="#1f8f3a")
    d.text((x1 - 122, y0 + 98), "Baixar e instalar" if pt else "Download and install", font=_font(13, True), fill="white", anchor="mm")
    # tabs
    d.text((x0 + 24, y0 + 134), "Widgets", font=_font(16, True), fill=B.WHITE)
    d.line((x0 + 20, y0 + 158, x0 + 92, y0 + 158), fill=B.RED, width=3)
    d.text((x0 + 120, y0 + 134), "Layouts", font=_font(16, False), fill=B.GRAY)
    # widget rows
    for i, name in enumerate(("Standings", "Relative", "Inputs", "Radar", "Spotter")):
        yy = y0 + 176 + i * 50
        d.rounded_rectangle((x0 + 12, yy, x1 - 12, yy + 40), radius=6, fill="#18181d")
        d.rounded_rectangle((x0 + 22, yy + 12, x0 + 40, yy + 28), radius=3, fill=B.RED if i != 3 else "#3a3a42")
        d.text((x0 + 52, yy + 11), name, font=_font(16, False), fill=B.WHITE)
        d.rounded_rectangle((x1 - 230, yy + 7, x1 - 150, yy + 33), radius=5, outline=B.LINE, width=2)
        d.text((x1 - 190, yy + 20), "Config", font=_font(13, False), fill=B.GRAY, anchor="mm")
        d.rounded_rectangle((x1 - 136, yy + 7, x1 - 24, yy + 33), radius=5, outline=B.LINE, width=2)
        d.text((x1 - 80, yy + 20), "Regra geral" if pt else "Global rule", font=_font(13, False), fill=B.GRAY, anchor="mm")
    img.alpha_composite(kerb_strip(480, 10), (x0, y1 - 14))
    # legendas
    notes = [
        (y0 + 34, "1", "Menus do programa" if pt else "Program menus"),
        (y0 + 86, "2", "Versão e botão de atualização" if pt else "Version and update button"),
        (y0 + 128, "3", "Abas Widgets e Layouts" if pt else "Widgets and Layouts tabs"),
        (y0 + 184, "4", "Liga/desliga cada módulo" if pt else "Turn each module on/off"),
        (y0 + 234, "5", "Config: opções do módulo" if pt else "Config: module options"),
        (y0 + 284, "6", "Quando o módulo aparece" if pt else "When the module appears"),
    ]
    for ny, n, text in notes:
        cx, cy = 560, ny + 12
        d.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), fill=B.RED)
        d.text((cx, cy), n, font=_font(16, True), fill="white", anchor="mm")
        d.text((cx + 28, cy), text, font=_font(17, False), fill=B.WHITE, anchor="lm")
    d.text((560, 470), "Esquema ilustrativo (não é uma captura de tela)." if pt else "Illustrative diagram (not a screenshot).",
           font=_font(14, False), fill=B.GRAY)
    return img.convert("RGB")


# ---------------------------------------------------------------- imagens do README (docs/img) #
def hero(width: int = 1280, height: int = 420) -> Image.Image:
    """Capa do README."""
    img = Image.new("RGBA", (width, height), B.ASPHALT)
    d = ImageDraw.Draw(img)
    # brilho vermelho discreto atrás do logo
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(260, 0, -20):
        a = int(26 * (1 - r / 260))
        gd.ellipse((200 - r, height // 2 - r, 200 + r, height // 2 + r), fill=(225, 6, 0, a))
    img.alpha_composite(glow)
    d.rectangle((0, 0, width, 8), fill=B.RED)
    ls = 200
    img.alpha_composite(logo(ls), (90, (height - ls) // 2 - 10))
    x = 90 + ls + 60
    wm = wordmark(96)
    y = height // 2 - wm.height - 20
    img.alpha_composite(wm, (x, y))
    d.text((x, y + wm.height + 26), "Overlay de sim racing", font=_font(30, False), fill=B.WHITE)
    d.text((x, y + wm.height + 72), "iRacing   ·   Le Mans Ultimate", font=_font(28, True), fill=B.GRAY)
    img.alpha_composite(kerb_strip(width, 30), (0, height - 30))
    return img.convert("RGB")


MODULES = [
    ("Standings", "Classificação por classe, com logos e bandeiras", "Standings by class, with logos and flags"),
    ("Relative", "Quem está à frente e atrás, na pista", "Who is ahead and behind on track"),
    ("Inputs", "Pedais, marcha, velocidade, volante e shift light", "Pedals, gear, speed, wheel and shift lights"),
    ("Telemetria", "Gráficos de pedais, velocidade, RPM e direção", "Pedals, speed, RPM and steering graphs"),
    ("Track Map", "Traçado real da pista com todos os carros", "Real track outline with every car"),
    ("Combustível", "Consumo, voltas restantes e quanto abastecer", "Usage, laps left and how much to refuel"),
    ("Car Damage", "Saúde do carro e tempos de reparo", "Car health and repair times"),
    ("Pneus", "Desgaste, temperatura por zona e pressão", "Wear, temperature per zone and pressure"),
    ("Spotter", "Aviso visual de carro ao lado", "Visual car-alongside warning"),
    ("Radar", "Carros próximos em volta de você", "Nearby cars around you"),
    ("DigFlag", "Bandeiras da corrida em destaque", "Race flags, big and clear"),
    ("Status", "Conexão com o simulador e versão", "Simulator connection and version"),
]


def modules_grid(lang: str) -> Image.Image:
    pt = lang == "pt"
    cols, cw, ch, gap, pad = 3, 400, 104, 20, 30
    rows = (len(MODULES) + cols - 1) // cols
    W = pad * 2 + cols * cw + (cols - 1) * gap
    H = 96 + rows * ch + (rows - 1) * gap + pad + 16
    img = Image.new("RGBA", (W, H), B.ASPHALT)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 6), fill=B.RED)
    d.text((pad, 30), "12 módulos, cada um na sua janela" if pt else "12 modules, each in its own window", font=_font(30, True), fill=B.WHITE)
    for i, (name, dpt, den) in enumerate(MODULES):
        r, c = divmod(i, cols)
        x, y = pad + c * (cw + gap), 96 + r * (ch + gap)
        d.rounded_rectangle((x, y, x + cw, y + ch), radius=12, fill=B.PANEL, outline=B.LINE, width=2)
        d.rounded_rectangle((x, y, x + 8, y + ch), radius=4, fill=B.RED)
        title = name if not (not pt and name in ("Telemetria", "Combustível", "Pneus")) else {"Telemetria": "Telemetry", "Combustível": "Fuel", "Pneus": "Tires"}[name]
        d.text((x + 28, y + 20), title, font=_font(24, True), fill=B.WHITE)
        d.text((x + 28, y + 60), dpt if pt else den, font=_font(18, False), fill=B.GRAY)
    img.alpha_composite(kerb_strip(W, 14), (0, H - 14))
    return img.convert("RGB")


def update_flow(lang: str) -> Image.Image:
    pt = lang == "pt"
    steps = ([("GitHub", "nova versão publicada"), ("Verificar", "botão na tela inicial"), ("SHA-256", "arquivo conferido"),
              ("Instalar", "um clique, com backup"), ("dados/", "suas pastas intactas")] if pt else
             [("GitHub", "new version released"), ("Check", "button on the home screen"), ("SHA-256", "file verified"),
              ("Install", "one click, with backup"), ("dados/", "your folders untouched")])
    W, H = 1280, 250
    img = Image.new("RGBA", (W, H), B.ASPHALT)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 6), fill=B.RED)
    d.text((30, 26), "Atualização direto pela interface" if pt else "Updates straight from the interface", font=_font(28, True), fill=B.WHITE)
    bw, gap, x = 212, 40, 30
    for i, (t, sub) in enumerate(steps):
        y = 90
        last = i == len(steps) - 1
        d.rounded_rectangle((x, y, x + bw, y + 110), radius=12, fill=B.PANEL, outline="#14c05a" if last else B.LINE, width=2)
        d.ellipse((x + 16, y + 16, x + 46, y + 46), fill=B.RED)
        d.text((x + 31, y + 31), str(i + 1), font=_font(16, True), fill="white", anchor="mm")
        d.text((x + 58, y + 18), t, font=_font(22, True), fill=B.WHITE)
        d.text((x + 18, y + 66), sub, font=_font(16, False), fill=B.GRAY)
        if not last:
            ax = x + bw + 8
            d.polygon([(ax, y + 47), (ax + 22, y + 55), (ax, y + 63)], fill=B.RED)
        x += bw + gap
    img.alpha_composite(kerb_strip(W, 14), (0, H - 14))
    return img.convert("RGB")


def readme_images() -> None:
    out = ROOT / "docs" / "img"
    out.mkdir(parents=True, exist_ok=True)
    hero().save(out / "hero.png")
    logo(256).save(out / "logo.png")
    for lang in ("pt", "en"):
        modules_grid(lang).save(out / f"modulos-{lang}.png")
        update_flow(lang).save(out / f"atualizacao-{lang}.png")
    print("imagens do README em", out)


def main() -> None:
    out = ROOT / "changelog"
    out.mkdir(exist_ok=True)
    logo(256).save(out / "logo.png")
    logo(256).save(ROOT / "build_exe" / "kerbhud.ico", format="ICO", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    for old in out.glob("banner-*.png"):
        old.unlink()
    banner("0.15.0", "Atualização à vista e novidades").save(out / "banner-0.15.0.png")
    banner("0.17.0", "Agora é KerbHUD").save(out / "banner-0.17.0.png")
    tree_diagram().save(out / "pasta-dados.png")
    window_map("pt").save(out / "guia-janela-pt.png")
    window_map("en").save(out / "guia-janela-en.png")
    print("imagens geradas em", out)
    readme_images()


if __name__ == "__main__":
    main()
