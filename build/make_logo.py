"""
Apex Words — bot uchun 640x360 muqova rasmi.

Ranglar va shakllar web_app/style.css bilan bir xil: osmon gradienti,
oq laganda, oltin harf plitkalari va marjon rangli chiziq.

Rasm 3 barobar kattaroq chiziladi va oxirida kichraytiriladi — shunda
chetlari tekis va silliq chiqadi (Pillow'da antialiasing yo'q).

Ishga tushirish:
    python build/make_logo.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets"

W, H = 640, 360
S = 3                      # supersampling: shu koeffitsiyentda chizamiz
CW, CH = W * S, H * S

# --- style.css dagi ranglar ---
SKY_1 = (95, 216, 255)
SKY_2 = (47, 155, 247)
SKY_3 = (106, 92, 245)
GOLD_1 = (255, 225, 122)
GOLD_2 = (255, 201, 60)
GOLD_3 = (245, 161, 5)
GOLD_INK = (107, 61, 0)
CORAL = (255, 79, 111)
WHITE = (255, 255, 255)

FONTS = Path("C:/Windows/Fonts")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def sky_gradient(img: Image.Image):
    """Diagonalga yaqin uch bosqichli gradient."""
    w, h = img.size
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        if t < 0.45:
            c = lerp(SKY_1, SKY_2, t / 0.45)
        else:
            c = lerp(SKY_2, SKY_3, (t - 0.45) / 0.55)
        d.line([(0, y), (w, y)], fill=c)


def clouds(img: Image.Image):
    """Yumshoq bulutlar — alohida qatlamda chizilib xiralashtiriladi."""
    layer = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    def puff(cx, cy, r, a):
        for dx, dy, k in ((0, 0, 1.0), (-r * 0.75, r * 0.2, 0.7),
                          (r * 0.8, r * 0.15, 0.78), (r * 0.1, -r * 0.45, 0.6)):
            rr = r * k
            d.ellipse([cx + dx - rr, cy + dy - rr, cx + dx + rr, cy + dy + rr],
                      fill=(255, 255, 255, a))

    puff(90 * S, 62 * S, 30 * S, 105)
    puff(560 * S, 48 * S, 24 * S, 85)
    puff(500 * S, 300 * S, 34 * S, 60)
    puff(40 * S, 250 * S, 26 * S, 55)

    layer = layer.filter(ImageFilter.GaussianBlur(6 * S))
    img.alpha_composite(layer)


def overlay(img: Image.Image, draw_fn, blur: int = 0):
    """
    Shaffof elementni TO'G'RI qo'yadi.

    ImageDraw RGBA rasmga chizganda ranglarni aralashtirmaydi — piksel
    qiymatini alfasi bilan birga ALMASHTIRADI. Ya'ni fon ustiga alfasi 55
    bo'lgan oq to'rtburchak chizilsa, u yarim shaffof ko'rinmaydi: o'sha
    joyning alfasi 55 ga tushadi va oxirida RGB ga o'tkazilganda qip-qizil
    oq bo'lib qoladi. Shuning uchun har bir shaffof element alohida
    qatlamga chizilib, alpha_composite bilan qo'shiladi.
    """
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(layer)


GOLD_SET = (GOLD_1, GOLD_2, GOLD_3, (201, 132, 0), GOLD_INK)
CREAM_SET = ((255, 255, 255), (245, 249, 255), (219, 231, 247),
             (168, 190, 219), (23, 36, 107))


def tile(img: Image.Image, cx: int, cy: int, size: int, ch: str, angle: float = 0,
         palette=GOLD_SET):
    """Harf plitkasi. palette: (yuqori, o'rta, past, qalinlik, yozuv) ranglari."""
    c_top, c_mid, c_bot, c_edge, c_ink = palette
    pad = size // 2
    box = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    x0, y0 = pad, pad
    x1, y1 = pad + size, pad + size
    r = size * 0.30

    # pastki qalinlik (3D his)
    d.rounded_rectangle([x0, y0 + size * 0.08, x1, y1 + size * 0.10], r,
                        fill=c_edge + (255,))
    # yuza gradienti — gorizontal chiziqlar bilan
    face = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fd = ImageDraw.Draw(face)
    for i in range(size):
        t = i / max(1, size - 1)
        c = lerp(c_top, c_mid, t / 0.5) if t < 0.5 else lerp(c_mid, c_bot, (t - 0.5) / 0.5)
        fd.line([(0, i), (size, i)], fill=c + (255,))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], r, fill=255)
    box.paste(face, (x0, y0), mask)
    d.rounded_rectangle([x0, y0, x1, y1], r, outline=(255, 255, 255, 255),
                        width=max(2, size // 16))

    if ch:
        f = font("seguibl.ttf", int(size * 0.62))
        tb = d.textbbox((0, 0), ch, font=f)
        d.text((x0 + size / 2 - (tb[2] - tb[0]) / 2 - tb[0],
                y0 + size / 2 - (tb[3] - tb[1]) / 2 - tb[1]),
               ch, font=f, fill=c_ink + (255,))

    if angle:
        box = box.rotate(angle, resample=Image.BICUBIC, expand=False)
    img.alpha_composite(box, (cx - box.width // 2, cy - box.height // 2))


def wheel(img: Image.Image, cx: int, cy: int, radius: int, word: str):
    """Oq laganda + atrofida harflar + ularni tutashtiruvchi marjon chiziq."""
    # laganda soyasi
    overlay(img, lambda d: d.ellipse(
        [cx - radius, cy - radius + 10 * S, cx + radius, cy + radius + 10 * S],
        fill=(0, 0, 0, 90)), blur=9 * S)

    d = ImageDraw.Draw(img)
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
              fill=(255, 255, 255, 255))
    inner = int(radius * 0.74)
    overlay(img, lambda d2: d2.ellipse(
        [cx - inner, cy - inner, cx + inner, cy + inner],
        outline=(150, 190, 235, 90), width=3 * S))

    n = len(word)
    ring = int(radius * 0.66)
    pts = []
    for i in range(n):
        a = -math.pi / 2 + i * 2 * math.pi / n
        pts.append((cx + int(ring * math.cos(a)), cy + int(ring * math.sin(a))))

    # harflarni tutashtiruvchi chiziq (o'yinda barmoq izi)
    line = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    ImageDraw.Draw(line).line(pts, fill=CORAL + (235,), width=9 * S, joint="curve")
    img.alpha_composite(line)

    for (x, y), ch in zip(pts, word):
        tile(img, x, y, int(radius * 0.42), ch)


def save(img: Image.Image, name: str, out=(W, H)):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    final = img.convert("RGB").resize(out, Image.LANCZOS)
    path = OUT_DIR / name
    final.save(path, "PNG", optimize=True)
    print(f"  {name}  ({final.width}x{final.height}, "
          f"{path.stat().st_size / 1024:.0f} KB)")


# --------------------------- Kvadrat avatar ---------------------------------
# Telegram bot rasmini DOIRA qilib kesadi, shuning uchun barcha muhim narsa
# markazdagi doira ichida turishi kerak — burchaklar ko'rinmaydi.
AV = 512
AVC = AV * S


def avatar_letter(name: str):
    """Bitta yirik plitka. Kichik o'lchamda eng yaxshi o'qiladi."""
    img = Image.new("RGBA", (AVC, AVC), (0, 0, 0, 0))
    sky_gradient(img)
    c = AVC // 2
    overlay(img, lambda d: d.ellipse(
        [c - AVC * 0.34, c - AVC * 0.30, c + AVC * 0.34, c + AVC * 0.38],
        fill=(0, 0, 0, 90)), blur=int(0.05 * AVC))
    tile(img, c, c, int(AVC * 0.56), "A", angle=-4)
    save(img, name, out=(AV, AV))


def avatar_cross(name: str):
    """Chalkash so'z shakli — kvadratga siqilgan."""
    img = Image.new("RGBA", (AVC, AVC), (0, 0, 0, 0))
    dark_bg(img)
    c = AVC // 2
    s = int(AVC * 0.235)
    step = int(AVC * 0.265)
    overlay(img, lambda d: d.ellipse(
        [c - AVC * 0.40, c - AVC * 0.36, c + AVC * 0.40, c + AVC * 0.42],
        fill=(0, 0, 0, 80)), blur=int(0.05 * AVC))
    for i in (-1, 0, 1):
        tile(img, c + i * step, c, s, "", palette=GOLD_SET)
    for j in (-1, 1):
        tile(img, c, c + j * step, s, "", palette=CREAM_SET)
    save(img, name, out=(AV, AV))


def avatar_path(name: str):
    """Barmoq izi: uchta plitka va ularni bog'lovchi chiziq."""
    img = Image.new("RGBA", (AVC, AVC), (0, 0, 0, 0))
    sky_gradient(img)
    s = int(AVC * 0.26)
    pts = [(int(AVC * 0.30), int(AVC * 0.66)),
           (int(AVC * 0.50), int(AVC * 0.33)),
           (int(AVC * 0.71), int(AVC * 0.63))]
    overlay(img, lambda d: d.line(pts, fill=(0, 0, 0, 85),
                                  width=int(AVC * 0.045), joint="curve"),
            blur=int(0.02 * AVC))
    overlay(img, lambda d: d.line(pts, fill=CORAL + (245,),
                                  width=int(AVC * 0.042), joint="curve"))
    for i, (x, y) in enumerate(pts):
        tile(img, x, y, s, "", angle=4 if i % 2 else -4,
             palette=GOLD_SET if i != 1 else CREAM_SET)
    save(img, name, out=(AV, AV))


def plain(word: str, name: str):
    """
    Mini App uchun sof rasm: faqat fon va o'yin g'ildiragi.
    Sarlavha, shior va boshqa yozuvlar yo'q — BotFather shuni so'raydi.
    """
    img = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    sky_gradient(img)
    clouds(img)
    wheel(img, cx=CW // 2, cy=CH // 2, radius=int(132 * S), word=word)
    save(img, name)


def tile_word(img, word, cy, size, gap, palette, tilt=2.4):
    """So'zni plitkalar qatori sifatida markazga joylashtiradi."""
    n = len(word)
    total = n * size + (n - 1) * gap
    x = CW // 2 - total // 2 + size // 2
    for i, ch in enumerate(word):
        # Har plitka biroz qiyshiq — qo'lda terilgandek jonli ko'rinadi
        angle = tilt if i % 2 == 0 else -tilt
        tile(img, x + i * (size + gap), cy, size, ch, angle=angle, palette=palette)


def style_tiles(name: str):
    """
    Ikkinchi uslub: g'ildirak yo'q, APEX va WORDS plitkalardan terilgan.
    Fon to'q — oltin plitkalar yorqinroq ajralib turadi.
    """
    img = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))

    # To'q diagonal fon
    d0 = ImageDraw.Draw(img)
    top, bot = (26, 38, 104), (58, 30, 122)
    for y in range(CH):
        d0.line([(0, y), (CW, y)], fill=lerp(top, bot, y / (CH - 1)))

    # Markazdagi yumshoq yorug'lik
    overlay(img, lambda d: d.ellipse(
        [CW * 0.16, CH * 0.02, CW * 0.84, CH * 0.98],
        fill=(120, 150, 255, 70)), blur=40 * S)

    # Fon bezagi: sochilgan mayda plitkalar
    for gx, gy, gs in ((52, 58, 30), (588, 96, 24), (78, 300, 22),
                       (566, 292, 30), (306, 34, 18), (330, 330, 20)):
        overlay(img, lambda d, a=gx, b=gy, c=gs: d.rounded_rectangle(
            [(a - c // 2) * S, (b - c // 2) * S, (a + c // 2) * S, (b + c // 2) * S],
            int(c * 0.3 * S), fill=(255, 255, 255, 26)))

    size, gap = int(64 * S), int(9 * S)

    # Plitkalar ostidagi umumiy soya
    overlay(img, lambda d: d.rounded_rectangle(
        [CW * 0.20, CH * 0.20, CW * 0.80, CH * 0.86], 40 * S,
        fill=(0, 0, 0, 80)), blur=26 * S)

    tile_word(img, "APEX", int(126 * S), size, gap, CREAM_SET)
    tile_word(img, "WORDS", int(232 * S), size, gap, GOLD_SET)

    save(img, name)


def dark_bg(img, top=(26, 38, 104), bot=(58, 30, 122), glow=True):
    w, h = img.size
    d = ImageDraw.Draw(img)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=lerp(top, bot, y / (h - 1)))
    if glow:
        overlay(img, lambda dd: dd.ellipse(
            [w * 0.18, h * 0.04, w * 0.82, h * 0.96],
            fill=(120, 150, 255, 66)), blur=int(0.06 * w))


def empty_cell(img, cx, cy, size, angle=0):
    """O'yin to'ridagi bo'sh katak — to'ldirilmagan joy."""
    pad = size // 2
    box = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    d.rounded_rectangle([pad, pad, pad + size, pad + size], size * 0.28,
                        fill=(10, 24, 66, 105), outline=(255, 255, 255, 120),
                        width=max(2, size // 18))
    if angle:
        box = box.rotate(angle, resample=Image.BICUBIC, expand=False)
    img.alpha_composite(box, (cx - box.width // 2, cy - box.height // 2))


def style_cross(name):
    """1-uslub: chalkash so'z (crossword) shakli — bo'sh va to'la kataklar."""
    img = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    dark_bg(img)

    s = int(58 * S)
    step = int(67 * S)
    cx, cy = CW // 2, CH // 2

    overlay(img, lambda d: d.rounded_rectangle(
        [cx - step * 2.7, cy - step * 2.0, cx + step * 2.7, cy + step * 2.0],
        44 * S, fill=(0, 0, 0, 74)), blur=26 * S)

    # Gorizontal qator — oltin
    for i in range(-2, 3):
        tile(img, cx + i * step, cy, s, "", palette=GOLD_SET)
    # Vertikal ustun — kumush (markaz allaqachon chizilgan)
    for j in (-1, 1):
        tile(img, cx, cy + j * step, s, "", palette=CREAM_SET)
    # Atrofda bo'sh kataklar — to'r davom etayotgandek
    for dx, dy in ((-2, -1), (2, 1), (-1, 1), (1, -1)):
        empty_cell(img, cx + dx * step, cy + dy * step, s)

    save(img, name)


def style_path(name):
    """2-uslub: barmoq izi — plitkalar to'lqin bo'ylab chiziq bilan bog'langan."""
    img = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    sky_gradient(img)
    clouds(img)

    s = int(62 * S)
    pts = [(int(x * S), int(y * S)) for x, y in
           ((128, 232), (232, 128), (352, 216), (472, 112), (556, 236))]

    overlay(img, lambda d: d.line(pts, fill=(0, 0, 0, 80),
                                  width=12 * S, joint="curve"), blur=8 * S)
    overlay(img, lambda d: d.line(pts, fill=CORAL + (240,),
                                  width=11 * S, joint="curve"))

    for i, (x, y) in enumerate(pts):
        tile(img, x, y, s, "", angle=3 if i % 2 else -3,
             palette=GOLD_SET if i % 2 == 0 else CREAM_SET)

    save(img, name)


def style_grid(name):
    """3-uslub: tartibli plitkalar to'ri — sokin, belgiga o'xshash."""
    img = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    dark_bg(img, top=(18, 30, 88), bot=(76, 36, 128))

    s = int(70 * S)
    gap = int(12 * S)
    cols, rows = 4, 2
    tw = cols * s + (cols - 1) * gap
    th = rows * s + (rows - 1) * gap
    x0 = CW // 2 - tw // 2 + s // 2
    y0 = CH // 2 - th // 2 + s // 2

    overlay(img, lambda d: d.rounded_rectangle(
        [CW // 2 - tw * 0.62, CH // 2 - th * 0.78,
         CW // 2 + tw * 0.62, CH // 2 + th * 0.82],
        40 * S, fill=(0, 0, 0, 76)), blur=24 * S)

    for r in range(rows):
        for c in range(cols):
            pal = GOLD_SET if (r + c) % 2 == 0 else CREAM_SET
            tile(img, x0 + c * (s + gap), y0 + r * (s + gap), s, "", palette=pal)

    save(img, name)


def main():
    print("Yozildi:")
    style_cross("plain_1_cross.png")
    style_path("plain_2_path.png")
    style_grid("plain_3_grid.png")
    avatar_letter("avatar_1_letter.png")
    avatar_cross("avatar_2_cross.png")
    avatar_path("avatar_3_path.png")
    # Matnsiz variantlar
    plain("WORDS", "webapp_640x360.png")
    plain("     ", "webapp_640x360_blank.png")   # plitkalar ham bo'sh

    # Yozuvli muqova (bot tavsifi uchun) — pastda
    img = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    sky_gradient(img)
    clouds(img)

    # Chapda o'yin g'ildiragi
    wheel(img, cx=int(158 * S), cy=int(180 * S), radius=int(118 * S), word="WORDS")

    d = ImageDraw.Draw(img)

    def text_with_shadow(xy, text, f, fill, sh_alpha=105, sh_off=3, anchor=None):
        x, y = xy
        # Soya yumshoq bo'lishi uchun alohida qatlamda chizilib xiralashtiriladi
        overlay(img, lambda dd: dd.text(
            (x + sh_off * S, y + sh_off * S), text, font=f,
            fill=(4, 26, 70, sh_alpha), anchor=anchor), blur=int(2.5 * S))
        d.text((x, y), text, font=f, fill=fill, anchor=anchor)

    left = int(310 * S)
    f_title = font("seguibl.ttf", int(58 * S))
    f_sub = font("segoeuib.ttf", int(19 * S))

    text_with_shadow((left, int(96 * S)), "APEX", f_title, WHITE + (255,), anchor="ls")
    text_with_shadow((left, int(160 * S)), "WORDS", f_title, GOLD_2 + (255,), anchor="ls")

    # Ajratuvchi chiziqcha
    d.rounded_rectangle([left, int(178 * S), left + int(96 * S), int(184 * S)],
                        3 * S, fill=CORAL + (255,))

    text_with_shadow((left, int(216 * S)), "Ingliz tilini", f_sub, WHITE + (240,),
                     sh_alpha=90, sh_off=2, anchor="ls")
    text_with_shadow((left, int(244 * S)), "o'ynab o'rganing", f_sub, WHITE + (240,),
                     sh_alpha=90, sh_off=2, anchor="ls")

    # Pastda kichik belgi: ochko va bosqichlar
    f_pill = font("segoeuib.ttf", int(15 * S))
    pill_y = int(276 * S)
    dx = 0
    for label in ("12 bosqich", "3000 puzzle"):
        tb = d.textbbox((0, 0), label, font=f_pill)
        w = tb[2] - tb[0]
        x0 = left + dx
        x1 = x0 + w + int(24 * S)
        # Yarim shaffof fon alohida qatlamda, yozuv esa ustidan to'liq oq
        overlay(img, lambda dd, a=x0, b=x1: dd.rounded_rectangle(
            [a, pill_y, b, pill_y + int(28 * S)], int(14 * S),
            fill=(255, 255, 255, 60), outline=(255, 255, 255, 150), width=2 * S))
        d.text((x0 + int(12 * S), pill_y + int(14 * S)), label, font=f_pill,
               fill=WHITE + (255,), anchor="lm")
        dx += w + int(24 * S) + int(12 * S)

    save(img, "cover_640x360.png")


if __name__ == "__main__":
    main()
