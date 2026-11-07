"""Turns a phone screen recording (an .mp4 from the phone's own recorder) into a recording that make_video2.py can
show inside the phone frame, like the ones record2.js makes.

    python import_clip.py <clip.mp4> <rec dir> <name> [--start S] [--end S] [--fps 30] [--blur x,y,w,h ...]

Writes <rec dir>/<name>/00000.jpg... (780 x 1688, the size of our own recordings) and index.json, and adds the
marks "<name>:start" and "<name>:end" (seconds into the clip) to <rec dir>/marks.json, so a beat can use
src=("<name>", "start", "end"). --blur boxes are in those 780 x 1688 pixels and are blurred on every frame, for a
phone number, a name or a notification that must not be seen."""
import argparse
import json
import os
import subprocess

from PIL import Image, ImageFilter

W, H = 780, 1688

ap = argparse.ArgumentParser()
ap.add_argument("clip")
ap.add_argument("rec")
ap.add_argument("name")
ap.add_argument("--start", type=float, default=0.0)
ap.add_argument("--end", type=float, default=None)
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--blur", action="append", default=[])
a = ap.parse_args()

out = os.path.join(a.rec, a.name)
os.makedirs(out, exist_ok=True)
for f in os.listdir(out):
    if f.endswith(".jpg"):
        os.remove(os.path.join(out, f))

# scale until the clip covers 780 x 1688, then crop the middle: no bars, whatever the phone's aspect ratio
vf = f"fps={a.fps},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}"
cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{a.start:.3f}", "-i", a.clip]
if a.end is not None:
    cmd += ["-t", f"{a.end - a.start:.3f}"]
cmd += ["-vf", vf, "-q:v", "3", os.path.join(out, "%05d.jpg")]
subprocess.run(cmd, check=True)

files = sorted(f for f in os.listdir(out) if f.endswith(".jpg"))
boxes = [tuple(int(v) for v in b.split(",")) for b in a.blur]
for f in files:
    p = os.path.join(out, f)
    im = Image.open(p).convert("RGB")
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS)
    for x, y, w, h in boxes:
        im.paste(im.crop((x, y, x + w, y + h)).filter(ImageFilter.GaussianBlur(18)), (x, y))
    im.save(p, quality=90)

ix = [[a.start + i / a.fps, f] for i, f in enumerate(files)]
json.dump(ix, open(os.path.join(out, "index.json"), "w"))
mp = os.path.join(a.rec, "marks.json")
m = json.load(open(mp))
m["marks"][f"{a.name}:start"] = a.start
m["marks"][f"{a.name}:end"] = ix[-1][0] if ix else a.start
json.dump(m, open(mp, "w"))
print(f"{a.name}: {len(files)} frames, {ix[0][0]:.2f} to {ix[-1][0]:.2f} s" if ix else f"{a.name}: no frames")
