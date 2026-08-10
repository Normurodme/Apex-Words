"""
Instagram uchun brend rasmlarini yasaydi.

O'yinning "Illuminated Atlas" pergament mavzusidagi ranglar ishlatiladi —
mavjud assets/ ichidagi avatarlar eski ko'k dizayndan qolgan va endi
ilovaga umuman o'xshamaydi.

Ishga tushirish:
    python build/make_instagram.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "instagram"
OUT.mkdir(parents=True, exist_ok=True)

# style.css dagi o'zgaruvchilar bilan bir xil
P1, P2, P3 = (0xF6, 0xE8, 0xC8), (0xED, 0xDA, 0xAE), (0xE0, 0xC7, 0x8D)
INK = (0x23, 0x30, 0x1F)
G1, G2, G3 = (0xF0, 0xD1, 0x87), (0xC9, 0x94, 0x2A), (0x9A, 0x6D, 0x14)
MOSS = (0x2F, 0x7A, 0x52)

SERIF = "C:/Windows/Fonts/georgiab.ttf"
SERIF_R = "C:/Windows/Fonts/georgia.ttf"


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def parchment(w: int, h: int) -> Image.Image:
    """Pergament foni: yumshoq nur + qog'oz chizig'i."""
    img = Image.new("RGB", (w, h), P2)
    d = ImageDraw.Draw(img)

    # Markazdan yorug'lik
    glow = Image.new("L", (w, h), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-w * 0.15, -h * 0.35, w * 1.15, h * 0.95], fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(w // 6))
    img = Image.composite(Image.new("RGB", (w, h), P1), img, glow)

    # Daftar chiziqlari — juda past kontrastda
    d = ImageDraw.Draw(img, "RGBA")
    step = max(18, h // 34)
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=(122, 90, 30, 16), width=1)
    return img


def frame(img, pad, radius, width=6):
    """Oltin ramka."""
    d = ImageDraw.Draw(img)
    w, h = img.size
    d.rounded_rectangle([pad, pad, w - pad, h - pad], radius=radius,
                        outline=G3, width=width)
    d.rounded_rectangle([pad + width + 6, pad + width + 6,
                         w - pad - width - 6, h - pad - width - 6],
                        radius=max(4, radius - 10), outline=(154, 109, 20, 90),
                        width=2)


def tile(size, letter, fnt_path=SERIF):
    """O'yindagi harf toshi."""
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(s * 0.22)
    # Soya / qalinlik
    d.rounded_rectangle([0, int(s * 0.09), s, s], radius=r, fill=G3)
    # Yuzasi — tepadan pastga oltin o'tish
    face = Image.new("RGB", (s, s), G1)
    fd = ImageDraw.Draw(face)
    for y in range(s):
        t = y / s
        fd.line([(0, y), (s, y)],
                fill=tuple(int(G1[i] + (G2[i] - G1[i]) * t) for i in range(3)))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s, int(s * 0.91)], radius=r,
                                           fill=255)
    img.paste(face, (0, 0), mask)

    f = font(fnt_path, int(s * 0.62))
    bbox = d.textbbox((0, 0), letter, font=f)
    d.text(((s - bbox[2] - bbox[0]) / 2, (s * 0.91 - bbox[3] - bbox[1]) / 2),
           letter, font=f, fill=(0x3F, 0x2C, 0x05))
    return img


def centred(d, text, f, y, size, fill):
    """Matnni gorizontal markazga qo'yadi. y — yuqori chekka, ulushda."""
    bb = d.textbbox((0, 0), text, font=f)
    d.text(((size - bb[2] - bb[0]) / 2, size * y - bb[1]), text, font=f, fill=fill)


def make_avatar(path, size=1080):
    """
    Profil rasmi.

    Instagram kvadratni DOIRA qilib kesadi. Shuning uchun hamma narsa
    ichki doiradan ham torroq "xavfsiz" hududda turadi (~78% diametr),
    aks holda pastki yozuv va ramka kesilib ketardi.
    """
    img = parchment(size, size)
    d = ImageDraw.Draw(img)

    # Halqa kesish chizig'idan ANCHA ichkarida
    m = int(size * 0.105)
    d.ellipse([m, m, size - m, size - m], outline=G3, width=int(size * 0.016))
    m2 = int(size * 0.135)
    d.ellipse([m2, m2, size - m2, size - m2], outline=G2, width=max(2, size // 360))

    # "A" toshi
    ts = int(size * 0.27)
    t = tile(ts, "A")
    img.paste(t, ((size - ts) // 2, int(size * 0.235)), t)

    f1 = font(SERIF, int(size * 0.098))
    f2 = font(SERIF_R, int(size * 0.040))
    centred(d, "APEX", f1, 0.555, size, INK)
    centred(d, "WORDS", f1, 0.655, size, G3)

    # Ajratuvchi chiziqcha
    y = int(size * 0.752)
    d.line([(size * 0.40, y), (size * 0.60, y)], fill=G2, width=2)

    centred(d, "ENGLISH · UZBEK", f2, 0.775, size, MOSS)

    img.save(path, quality=95)
    return path


def make_post(path, title, subtitle, word=None, size=1080):
    """Kvadrat post shabloni."""
    img = parchment(size, size)
    frame(img, int(size * 0.045), int(size * 0.05))
    d = ImageDraw.Draw(img)

    if word:
        # Tosh o'lchami SO'Z UZUNLIGIGA qarab hisoblanadi. Qat'iy qiymatda
        # olti harfli so'z ramkadan chiqib ketardi.
        avail = size * 0.78
        n = len(word)
        ts = int(min(size * 0.15, avail / (n + (n - 1) * 0.14)))
        gap = int(ts * 0.14)
        total = n * ts + (n - 1) * gap
        x = (size - total) // 2
        for ch in word:
            t = tile(ts, ch)
            img.paste(t, (x, int(size * 0.36)), t)
            x += ts + gap

    f1 = font(SERIF, int(size * 0.082))
    f2 = font(SERIF_R, int(size * 0.044))
    bb = d.textbbox((0, 0), title, font=f1)
    d.text(((size - bb[2] - bb[0]) / 2, size * 0.17), title, font=f1, fill=INK)

    y = size * 0.62
    for line in subtitle.split("\n"):
        bb = d.textbbox((0, 0), line, font=f2)
        d.text(((size - bb[2] - bb[0]) / 2, y), line, font=f2, fill=(0x4A, 0x5A, 0x3E))
        y += size * 0.065

    f3 = font(SERIF, int(size * 0.038))
    tag = "@apex.words"
    bb = d.textbbox((0, 0), tag, font=f3)
    d.text(((size - bb[2] - bb[0]) / 2, size * 0.88), tag, font=f3, fill=G3)

    img.save(path, quality=95)
    return path


if __name__ == "__main__":
    made = [make_avatar(OUT / "profile_1080.png")]
    made.append(make_post(OUT / "post_1_hello.png",
                          "3000 puzzles.", "12 chapters. 60 levels.\nOne word at a time.",
                          word="APEX"))
    made.append(make_post(OUT / "post_2_word.png",
                          "Word of the day", "COUSIN — amakivachcha\nSwipe the letters. Learn for free.",
                          word="COUSIN"))
    made.append(make_post(OUT / "post_3_bonus.png",
                          "Bonus words", "Find a real word that isn't listed\nand collect keys.",
                          word="BONUS"))
    for p in made:
        print("yozildi:", p.relative_to(ROOT))
