"""
Skrinshotdan vertikal (9:16) video yasaydi — Replicate / Stable Video Diffusion.

    python build/make_video.py screenshot.jpg

MUHIM IKKI CHEKLOV (skript ularni o'zi hal qiladi):

  1. Stable Video Diffusion MATN QABUL QILMAYDI. U image-to-video modeli:
     kirishi faqat rasm. Shuning uchun prompt modelga yuborilmaydi —
     u video.json ichiga eslatma sifatida yoziladi. Skript ishga
     tushganda modelning HAQIQIY parametrlarini API'dan so'raydi va
     agar "prompt" maydoni bor bo'lsa, o'shanda uzatadi.

  2. SVD bir chaqiruvda ~1-4 SONIYA beradi (14 yoki 25 kadr), 15 emas.
     15 soniyaga yetish uchun skript bir necha bo'lak yasaydi: har
     bo'lakning OXIRGI KADRI keyingisiga kirish rasmi bo'ladi.
     Bo'laklar ffmpeg bilan ulanadi va 1080x1920 ga keltiriladi.

Token: REPLICATE_API_TOKEN muhit o'zgaruvchisidan olinadi.
    PowerShell:  $env:REPLICATE_API_TOKEN = "r8_..."
    bash:        export REPLICATE_API_TOKEN=r8_...
Yo'q bo'lsa, skript uni ekranda ko'rsatmasdan so'raydi.
"""
from __future__ import annotations

import getpass
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

API = "https://api.replicate.com/v1"
MODEL = os.getenv("REPLICATE_MODEL", "stability-ai/stable-video-diffusion")

TARGET_SECONDS = 15
OUT_W, OUT_H = 1080, 1920          # 9:16
FPS = 24

PROMPT = ("Apex Words o'yini. Harflar yoniladi, qo'shib so'zlar hosil "
          "bo'ladi. Educational, warm tone.")


# ----------------------------- yordamchilar ----------------------------------

def die(msg: str) -> "NoReturn":
    sys.exit(f"XATO: {msg}")


def token() -> str:
    t = os.getenv("REPLICATE_API_TOKEN", "").strip()
    if not t:
        # Terminalda yozilgani ko'rinmaydi va tarixga tushmaydi
        t = getpass.getpass("REPLICATE_API_TOKEN: ").strip()
    if not t:
        die("token berilmadi.")
    return t


def ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        die("ffmpeg topilmadi. O'rnating: pip install imageio-ffmpeg")


def run(args: list[str]):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        die("ffmpeg xato berdi:\n" + (r.stderr or "")[-1500:])


# ------------------------------ Replicate ------------------------------------

class Replicate:
    def __init__(self, tok: str):
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {tok}",
                               "Content-Type": "application/json"})

    def schema(self, model: str) -> dict:
        """
        Modelning HAQIQIY kirish parametrlarini oladi.

        Qattiq yozib qo'yilgan parametrlar bilan ishlash xavfli: Replicate
        modellari versiyadan versiyaga maydon nomini o'zgartiradi va
        noto'g'ri nom 422 xatosi bilan qaytadi. Sxemani so'rab olsak,
        skript o'zi moslashadi.
        """
        r = self.s.get(f"{API}/models/{model}")
        if r.status_code == 404:
            die(f"model topilmadi: {model}")
        r.raise_for_status()
        d = r.json()
        ver = d.get("latest_version") or {}
        props = (ver.get("openapi_schema", {})
                    .get("components", {})
                    .get("schemas", {})
                    .get("Input", {})
                    .get("properties", {}))
        return {"version": ver.get("id"), "props": props}

    def create(self, version: str, payload: dict) -> dict:
        r = self.s.post(f"{API}/predictions",
                        json={"version": version, "input": payload})
        if r.status_code >= 400:
            die(f"so'rov rad etildi ({r.status_code}):\n{r.text[:1200]}")
        return r.json()

    def wait(self, pred: dict, every: float = 3.0) -> dict:
        url = pred["urls"]["get"]
        seen = None
        while True:
            r = self.s.get(url)
            r.raise_for_status()
            p = r.json()
            if p["status"] != seen:
                seen = p["status"]
                print(f"    holat: {seen}")
            if seen in ("succeeded", "failed", "canceled"):
                if seen != "succeeded":
                    die(f"generatsiya tugamadi ({seen}): {p.get('error')}")
                return p
            time.sleep(every)


# ------------------------------ video ishlari --------------------------------

def prepare_start(src: Path, work: Path) -> Path:
    """
    Kirish rasmini vertikal qilib tayyorlaydi.

    SVD kirish rasmining nisbatiga qarab chiqish o'lchamini tanlaydi,
    shuning uchun 9:16 ni ALDIN beramiz — aks holda gorizontal video
    chiqib, oxirida kesishga to'g'ri kelardi.
    """
    from PIL import Image
    im = Image.open(src).convert("RGB")
    w, h = im.size
    want = OUT_W / OUT_H

    if abs(w / h - want) > 0.01:
        if w / h > want:                       # juda keng -> yon tomonlarni kesamiz
            nw = int(h * want)
            im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:                                  # juda baland -> tepa/pastdan
            nh = int(w / want)
            im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))

    im = im.resize((576, 1024), Image.LANCZOS)   # SVD uchun qulay o'lcham
    out = work / "start.png"
    im.save(out)
    return out


def last_frame(video: Path, work: Path, i: int) -> Path:
    """Bo'lakning oxirgi kadri — keyingi bo'lakka kirish rasmi."""
    out = work / f"link_{i}.png"
    run([ffmpeg(), "-y", "-sseof", "-0.2", "-i", str(video),
         "-vframes", "1", "-q:v", "2", str(out)])
    return out


def upload_data_uri(path: Path) -> str:
    """
    Rasmni data: URI sifatida beramiz.

    Replicate fayl yuklash uchun alohida endpoint ham beradi, lekin
    data: URI hamma modellarda ishlaydi va qo'shimcha so'rov talab
    qilmaydi. Skrinshot kichik, hajm muammo emas.
    """
    import base64
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    b = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b}"


def build_input(props: dict, image_uri: str) -> dict:
    """
    Sxemaga qarab kirish to'plamini yig'adi.

    Faqat modelda HAQIQATAN mavjud maydonlar yuboriladi.
    """
    inp: dict = {}

    # Rasm maydonining nomi modeldan modelga farq qiladi
    for name in ("input_image", "image", "cond_image", "init_image"):
        if name in props:
            inp[name] = image_uri
            break
    else:
        die("modelda rasm uchun kirish maydoni topilmadi: " + ", ".join(props))

    # Eng uzun variantni tanlaymiz — kamroq bo'lak kerak bo'ladi
    if "video_length" in props:
        opts = props["video_length"].get("enum") or []
        inp["video_length"] = "25_frames_with_svd_xt" if \
            "25_frames_with_svd_xt" in opts else (opts[-1] if opts else None)
        if inp["video_length"] is None:
            inp.pop("video_length")
    if "frames" in props:
        inp["frames"] = 25
    if "num_frames" in props:
        inp["num_frames"] = 25

    if "frames_per_second" in props:
        inp["frames_per_second"] = 6
    elif "fps" in props:
        inp["fps"] = 6

    # Harakat MO''TADIL bo'lsin. Kattaroq qiymatda model interfeysni
    # "eritib" yuboradi: harflar o'qib bo'lmaydigan bo'lib qoladi.
    if "motion_bucket_id" in props:
        inp["motion_bucket_id"] = 40
    if "cond_aug" in props:
        inp["cond_aug"] = 0.02
    if "sizing_strategy" in props:
        opts = props["sizing_strategy"].get("enum") or []
        if "maintain_aspect_ratio" in opts:
            inp["sizing_strategy"] = "maintain_aspect_ratio"

    # Model matn qabul qilsa — beramiz. SVD qabul qilmaydi.
    if "prompt" in props:
        inp["prompt"] = PROMPT

    return inp


def seconds_of(video: Path) -> float:
    import imageio_ffmpeg as iff
    r = iff.read_frames(str(video))
    meta = next(r)
    r.close()
    return float(meta["duration"])


# --------------------------------- asosiy ------------------------------------

def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "screenshot.jpg")
    if not src.exists():
        die(f"{src} topilmadi. Foydalanish: python build/make_video.py screenshot.jpg")

    out = Path(sys.argv[2] if len(sys.argv) > 2 else "video.mp4")
    rp = Replicate(token())

    print(f"[1/5] Model sxemasi so'ralmoqda: {MODEL}")
    sch = rp.schema(MODEL)
    if not sch["version"]:
        die("model versiyasi aniqlanmadi.")
    props = sch["props"]
    print("      mavjud parametrlar:", ", ".join(sorted(props)) or "(yo'q)")
    if "prompt" not in props:
        print("      DIQQAT: bu model matn (prompt) qabul qilmaydi — "
              "u faqat rasmdan video yasaydi.")

    work = Path(tempfile.mkdtemp(prefix="apexvid_"))
    print(f"[2/5] Kirish rasmi 9:16 ga keltirilmoqda")
    frame = prepare_start(src, work)

    parts: list[Path] = []
    total = 0.0
    i = 0
    print(f"[3/5] Bo'laklar yasalmoqda (maqsad {TARGET_SECONDS} s)")
    while total < TARGET_SECONDS and i < 12:
        i += 1
        inp = build_input(props, upload_data_uri(frame))
        print(f"  bo'lak {i}...")
        pred = rp.wait(rp.create(sch["version"], inp))

        url = pred["output"]
        if isinstance(url, list):
            url = url[-1]
        if not isinstance(url, str):
            die(f"kutilmagan javob: {pred.get('output')!r}")

        part = work / f"part_{i}.mp4"
        part.write_bytes(requests.get(url, timeout=300).content)
        parts.append(part)
        total += seconds_of(part)
        print(f"      jami: {total:.1f} s")

        if total < TARGET_SECONDS:
            frame = last_frame(part, work, i)

    print(f"[4/5] {len(parts)} bo'lak ulanmoqda")
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts),
                   encoding="utf-8")
    joined = work / "joined.mp4"
    run([ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(joined)])

    print(f"[5/5] {OUT_W}x{OUT_H}, {FPS} fps, {TARGET_SECONDS} s ga keltirilmoqda")
    # setpts — bo'laklar sekin (6 fps) yasalgani uchun cho'zib, keyin
    # aynan TARGET_SECONDS ga kesamiz.
    run([ffmpeg(), "-y", "-i", str(joined),
         "-vf", (f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,"
                 f"crop={OUT_W}:{OUT_H},fps={FPS}"),
         "-t", str(TARGET_SECONDS),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
         "-movflags", "+faststart", str(out)])

    meta = out.with_suffix(".json")
    meta.write_text(json.dumps({
        "model": MODEL,
        "version": sch["version"],
        "prompt": PROMPT,
        "prompt_sent_to_model": "prompt" in props,
        "source_image": str(src),
        "parts": len(parts),
        "raw_seconds": round(total, 2),
        "output": str(out),
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nTayyor: {out}  ({out.stat().st_size / 1e6:.1f} MB)")
    print(f"Ma'lumot: {meta}")


if __name__ == "__main__":
    main()
