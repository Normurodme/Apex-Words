"""make_video.py ning tokensiz ishlaydigan qismlarini tekshiradi."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import make_video as M  # noqa: E402

work = Path(tempfile.mkdtemp(prefix="t_"))
ok = []

# --- 1. Kirish rasmini 9:16 ga keltirish ---
from PIL import Image  # noqa: E402

# gorizontal (video muammosi shunday edi) va vertikal manbalar
for name, size in (("landscape", (1280, 720)), ("tall", (1080, 2400)),
                   ("square", (1000, 1000))):
    p = work / f"{name}.png"
    Image.new("RGB", size, (200, 180, 140)).save(p)
    out = M.prepare_start(p, work)
    w, h = Image.open(out).size
    ok.append((f"{name} -> 576x1024", (w, h) == (576, 1024)))

# Haqiqiy skrinshot bilan ham
real = ROOT / "assets/instagram/reels_cover_1080x1920.png"
if real.exists():
    out = M.prepare_start(real, work)
    ok.append(("haqiqiy rasm 9:16", Image.open(out).size == (576, 1024)))

# --- 2. Bo'laklarni ulash + 1080x1920 ga keltirish ---
ff = M.ffmpeg()
parts = []
for i in range(4):                      # 4 x 1.5 s = 6 s xom material
    p = work / f"part_{i}.mp4"
    M.run([ff, "-y", "-loop", "1", "-i", str(work / "start.png"),
           "-t", "1.5", "-r", "6", "-c:v", "libx264",
           "-pix_fmt", "yuv420p", str(p)])
    parts.append(p)

lst = work / "list.txt"
lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
joined = work / "joined.mp4"
M.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
       str(joined)])
ok.append(("bo'laklar ulandi", joined.exists()))
ok.append(("ulangan uzunlik ~6 s", abs(M.seconds_of(joined) - 6.0) < 0.6))

final = work / "video.mp4"
M.run([ff, "-y", "-i", str(joined),
       "-vf", (f"scale={M.OUT_W}:{M.OUT_H}:force_original_aspect_ratio=increase,"
               f"crop={M.OUT_W}:{M.OUT_H},fps={M.FPS}"),
       "-t", "5", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
       "-movflags", "+faststart", str(final)])

import imageio_ffmpeg as iff  # noqa: E402
r = iff.read_frames(str(final))
meta = next(r)
r.close()
ok.append(("chiqish 1080x1920", meta["size"] == (M.OUT_W, M.OUT_H)))
ok.append(("chiqish 24 fps", abs(meta["fps"] - M.FPS) < 0.5))
ok.append(("uzunlik kesildi (5 s)", abs(meta["duration"] - 5.0) < 0.4))

# --- 3. Sxemaga qarab kirish yig'ish ---
svd_props = {
    "input_image": {"type": "string"},
    "video_length": {"enum": ["14_frames_with_svd", "25_frames_with_svd_xt"]},
    "frames_per_second": {"type": "integer"},
    "motion_bucket_id": {"type": "integer"},
    "cond_aug": {"type": "number"},
    "sizing_strategy": {"enum": ["maintain_aspect_ratio", "crop_to_16_9"]},
    "seed": {"type": "integer"},
}
inp = M.build_input(svd_props, "data:image/png;base64,AAAA")
ok.append(("rasm maydoni topildi", inp.get("input_image") is not None))
ok.append(("eng uzun variant tanlandi",
           inp.get("video_length") == "25_frames_with_svd_xt"))
ok.append(("prompt YUBORILMADI (SVD qabul qilmaydi)", "prompt" not in inp))
ok.append(("mavjud bo'lmagan maydon qo'shilmadi",
           set(inp) <= set(svd_props)))

# Boshqacha nomlangan model
alt = {"image": {"type": "string"}, "prompt": {"type": "string"},
       "num_frames": {"type": "integer"}, "fps": {"type": "integer"}}
inp2 = M.build_input(alt, "data:image/png;base64,AAAA")
ok.append(("boshqa nomdagi rasm maydoni ham topiladi",
           inp2.get("image") is not None))
ok.append(("model qabul qilsa prompt yuboriladi", inp2.get("prompt") == M.PROMPT))
ok.append(("alt modelga ortiqcha maydon ketmadi", set(inp2) <= set(alt)))

print()
bad = 0
for name, res in ok:
    print(("  OK   " if res else "  XATO ") + name)
    bad += not res
print(f"\n{len(ok) - bad}/{len(ok)} tekshiruv o'tdi")
sys.exit(1 if bad else 0)
