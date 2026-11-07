"""Video v2: Priya's story, cut to the voice, with zoom-in callouts, a music bed and sound effects.

    python3 make_video2.py <rec dir> <voice dir> <out dir> [neerja] [prabhat] [guide] [--wa <dir>]

<rec dir>   output of record2.js (frames, marks.json, console.png)
<voice dir> holds neerja/ and prabhat/ with <line>.mp3 + <line>.json (word timings) from tts.py
versions    neerja / prabhat: AI voice-over. guide: no voice, a karaoke strip of the script at Neerja's timing,
            for recording your own voice over it. Default: all three.
--wa <dir>  real WhatsApp screen recordings (open.mp4, status.mp4) to use instead of the in-app tracker shots.
Writes <out>/<version>.mp4, <out>/<version>.srt and <out>/timings.md.
"""
import bisect
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sound  # noqa: E402

args = [a for a in sys.argv[1:]]
WA = None
if "--wa" in args:
    i = args.index("--wa")
    WA = args[i + 1]
    del args[i:i + 2]
REC, VOICE, OUT = args[:3]
VERSIONS = args[3:] or ["neerja", "prabhat", "guide"]
os.makedirs(OUT, exist_ok=True)
TMP = os.path.join(OUT, "tmp")
os.makedirs(TMP, exist_ok=True)

W, H, FPS, SR = 1920, 1080, 30, sound.SR
IMG = os.path.join(HERE, "..", "source", "img")
INK, INK2, RED, WHITE = (27, 31, 59), (44, 50, 99), (226, 62, 87), (255, 255, 255)
GREY, DIM, GREEN = (196, 201, 222), (128, 134, 168), (52, 199, 125)
FD = "/usr/share/fonts/opentype/inter/{}.otf"
_fonts = {}


def font(name, size):
    k = (name, size)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(FD.format(name), size)
    return _fonts[k]


def ease_out(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = min(1.0, max(0.0, x))
    return 3 * x * x - 2 * x * x * x


def back_out(x, s=1.4):
    x = min(1.0, max(0.0, x))
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def sh(cmd, inp=None):
    r = subprocess.run(cmd, input=inp, capture_output=True)
    if r.returncode:
        raise SystemExit(" ".join(cmd) + "\n" + r.stderr.decode()[-3000:])
    return r.stdout


SCRIPT = {s["id"]: s["text"] for s in json.load(open(os.path.join(HERE, "script_v2.json"), encoding="utf-8"))}
REC_META = json.load(open(os.path.join(REC, "marks.json")))
M, RECTS, TAPS = REC_META["marks"], REC_META.get("rects", {}), REC_META.get("taps", [])


# ---------------------------------------------------------------- voice
def decode(path):
    raw = sh(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"])
    return np.frombuffer(raw, dtype=np.float32).copy()


def tighten(audio, words, max_gap=0.42):
    """Trims the silence around a line and shortens long pauses between sentences, so it flows like speech."""
    start = max(0.0, words[0][0] - 0.05)
    end = min(len(audio) / SR, words[-1][1] + 0.28)
    cuts = []
    for (s0, e0, _), (s1, e1, _) in zip(words, words[1:]):
        if s1 - e0 > max_gap:
            cuts.append((e0 + max_gap / 2, s1 - max_gap / 2))
    keep, t = [], start
    for a, b in cuts:
        keep.append((t, a))
        t = b
    keep.append((t, end))
    fade = int(0.008 * SR)
    parts = []
    for a, b in keep:
        seg = audio[int(a * SR):int(b * SR)].copy()
        if len(seg) > 2 * fade:
            seg[:fade] *= np.linspace(0, 1, fade)
            seg[-fade:] *= np.linspace(1, 0, fade)
        parts.append(seg)
    out = np.concatenate(parts)

    def remap(x):
        shift = start + sum(b - a for a, b in cuts if b <= x)
        return x - shift
    return out, [[remap(s), remap(e), w] for s, e, w in words]


def load_voice(voice):
    lines = {}
    for lid in SCRIPT:
        mp3 = os.path.join(VOICE, voice, lid + ".mp3")
        words = json.load(open(mp3[:-4] + ".json", encoding="utf-8"))
        lines[lid] = tighten(decode(mp3), words)
    return lines


# ---------------------------------------------------------------- recordings
class Frames:
    """Screen frames of one recording, looked up by wall-clock time."""
    def __init__(self, name):
        self.dir = os.path.join(REC, name)
        ix = json.load(open(os.path.join(self.dir, "index.json")))
        self.ts = [a for a, b in ix]
        self.files = [b for a, b in ix]

    def path(self, t):
        i = max(0, bisect.bisect_right(self.ts, t) - 1)
        return os.path.join(self.dir, self.files[i])


_frames = {}


def frames(name):
    if name not in _frames:
        _frames[name] = Frames(name)
    return _frames[name]


PX, PY, PW, PH = 252, 50, 452, 978   # the phone's screen on the canvas (780 x 1688 recordings scaled 0.58)
CENTER_DX = W // 2 - (PX + PW // 2)  # the cold open shows the phone alone, in the middle
_screen_cache = {}


def screen(path):
    if path not in _screen_cache:
        if len(_screen_cache) > 400:
            _screen_cache.clear()
        im = Image.open(path).convert("RGB")
        _screen_cache[path] = np.asarray(im.resize((PW, PH), Image.LANCZOS, reducing_gap=2.0))
    return _screen_cache[path]


# ---------------------------------------------------------------- static art
def background():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    d = (x / W * 0.62 + y / H * 0.38)
    a, b = np.array(INK, np.float32), np.array(INK2, np.float32)
    img = a + (b - a) * np.clip(d, 0, 1)[..., None] * 0.85
    glow = np.exp(-(((x - 1750) / 700) ** 2 + ((y - 1150) / 520) ** 2))
    img = img + (np.array(RED, np.float32) - img) * (glow[..., None] * 0.42)
    vig = 1 - 0.28 * (((x - W / 2) / (W * 0.75)) ** 2 + ((y - H / 2) / (H * 0.8)) ** 2)
    return np.clip(img * vig[..., None], 0, 255).astype(np.uint8)


BG = background()


def brand(im_arr):
    """Small Accel Saathi mark, top right."""
    im = Image.fromarray(im_arr)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((W - 318, 40, W - 278, 80), 10, fill=RED)
    d.text((W - 298, 60), "A", font=font("Inter-Bold", 24), fill=WHITE, anchor="mm")
    d.text((W - 266, 60), "Accel Saathi", font=font("Inter-SemiBold", 24), fill=WHITE, anchor="lm")
    return np.asarray(im).copy()


BG_BRAND = brand(BG)


def phone_art():
    """Bezel and shadow around the screen (RGBA, full canvas), and the screen's rounded mask."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh_ = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh_).rounded_rectangle((PX - 10, PY + 20, PX + PW + 10, PY + PH + 34), 64, fill=150)
    sh_ = sh_.filter(ImageFilter.GaussianBlur(28))
    layer.paste((5, 6, 14, 255), (0, 0), sh_)
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((PX - 15, PY - 15, PX + PW + 15, PY + PH + 15), 62, fill=(12, 13, 24, 255), outline=(78, 84, 120, 255), width=2)
    mask = Image.new("L", (PW, PH), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, PW - 1, PH - 1), 46, fill=255)
    return np.asarray(layer), (np.asarray(mask, np.float32) / 255.0)[..., None]


def tight(rgba, x=0, y=0):
    """Crops an RGBA layer to its visible pixels; returns (layer, x, y) so blending touches only what shows."""
    ys, xs = np.nonzero(rgba[..., 3])
    if not len(xs):
        return rgba[:1, :1], x, y
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    return np.ascontiguousarray(rgba[y0:y1, x0:x1]), x + int(x0), y + int(y0)


def over_t(canvas, layer, dx=0, dy=0, alpha=1.0):
    arr, x, y = layer
    over(canvas, arr, x + dx, y + dy, alpha)


def over(canvas, rgba, x=0, y=0, alpha=1.0):
    """Alpha-composites an RGBA numpy image onto the canvas (in place), clipped to the canvas."""
    h, w = rgba.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0 or alpha <= 0:
        return
    src = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = src[..., 3:4].astype(np.uint16)
    if alpha < 1:
        a = (a * int(alpha * 256)) >> 8
    dst = canvas[y0:y1, x0:x1].astype(np.uint16)
    canvas[y0:y1, x0:x1] = ((dst * (255 - a) + src[..., :3].astype(np.uint16) * a) // 255).astype(np.uint8)


PHONE_LAYER, PHONE_MASK = phone_art()
PHONE_MASK8 = (PHONE_MASK * 255).astype(np.uint16)
PHONE_T = tight(PHONE_LAYER)
PHONE_BASE = BG_BRAND.copy()
over_t(PHONE_BASE, PHONE_T)


def put_screen(canvas, scr, dx=0, dy=0, alpha=1.0):
    x, y = PX + dx, PY + dy
    m = PHONE_MASK8 if alpha >= 1 else (PHONE_MASK8 * int(alpha * 256)) >> 8
    dst = canvas[y:y + PH, x:x + PW].astype(np.uint16)
    canvas[y:y + PH, x:x + PW] = ((dst * (255 - m) + scr.astype(np.uint16) * m) // 255).astype(np.uint8)


def wrap(text, fnt, width):
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    out = []
    for para in text.split("\n"):
        line = ""
        for w_ in para.split():
            t = (line + " " + w_).strip()
            if d.textlength(t, font=fnt) <= width or not line:
                line = t
            else:
                out.append(line)
                line = w_
        out.append(line)
    return out


def tracked(d, xy, text, fnt, fill, track=3):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textlength(ch, font=fnt) + track
    return x


PANEL_X, PANEL_W = 820, 1000


def text_panel(kicker, head, sub, top=None, head_size=68):
    """Kicker, headline and subline as one RGBA layer at (PANEL_X, 0). Returns (layer, bottom y)."""
    im = Image.new("RGBA", (PANEL_W + 40, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    hf, sf, kf = font("InterDisplay-Bold", head_size), font("Inter-Regular", 32), font("Inter-Bold", 24)
    hl = wrap(head, hf, PANEL_W) if head else []
    sl = wrap(sub, sf, PANEL_W - 40) if sub else []
    block = (40 if kicker else 0) + len(hl) * int(head_size * 1.14) + (18 + len(sl) * 46 if sl else 0)
    y = top if top is not None else int(H / 2 - block / 2 - 20)
    if kicker:
        tracked(d, (0, y), kicker, kf, RED)
        y += 44
    for ln in hl:
        d.text((0, y), ln, font=hf, fill=WHITE)
        y += int(head_size * 1.14)
    if sl:
        y += 18
        for ln in sl:
            d.text((0, y), ln, font=sf, fill=GREY)
            y += 46
    return tight(np.asarray(im), PANEL_X, 0), y


def card_from(img, radius=24, border=3, shadow=True):
    """A screenshot crop as a floating card: rounded, white rim, soft shadow (RGBA numpy)."""
    w, h = img.size
    pad = 40 if shadow else 0
    out = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    if shadow:
        s = Image.new("L", out.size, 0)
        ImageDraw.Draw(s).rounded_rectangle((pad, pad + 14, pad + w, pad + h + 14), radius, fill=170)
        out.paste((0, 0, 10, 255), (0, 0), s.filter(ImageFilter.GaussianBlur(18)))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius, fill=255)
    out.paste(img.convert("RGB"), (pad, pad), m)
    ImageDraw.Draw(out).rounded_rectangle((pad, pad, pad + w - 1, pad + h - 1), radius, outline=(255, 255, 255, 255), width=border)
    return np.asarray(out), pad


# ---------------------------------------------------------------- beats
class Beat:
    def __init__(self, bid, line=None, dur=0.0, kind="phone", src=None, kicker="", head="", sub="", callout=None,
                 pre=0.0, post=0.3, **kw):
        self.id, self.line, self.dur, self.kind, self.src = bid, line, dur, kind, src
        self.kicker, self.head, self.sub, self.callout, self.pre, self.post = kicker, head, sub, callout, pre, post
        self.kw = kw


P = "priya"
BEATS = [
    Beat("cold", None, dur=3.0, kind="phone", src=(P, "livetop", "livetop", 0.2, 0.25), notify=0.55, enter=True, post=0),
    Beat("open", "v01_open", src=(P, "livetop", "end", 0.3, 0), kicker="A DEMO STORY · PRIYA, CORAL MEDICALS, JAIPUR", pre=0.1, big=True),
    Beat("rewind", None, dur=1.1, kind="rewind", src=(P, "home", "end"), kicker="REWIND", head="Five days earlier.", post=0),
    Beat("problem", "v02_problem", src=(P, "home", "gstin", 0, -0.2), kicker="SATURDAY, RUSH HOUR",
         head="She tells it what went wrong.\nIn one line.", callout="noted", lag=2.2, pre=0.15),
    Beat("gstin", "v03_gstin", src=(P, "gstin", "needs", -0.2, 0), kicker="GST REGISTRY, CONSENT FIRST",
         head="It finds her shop,\nand asks before using it.", callout="registry", lag=1.8),
    Beat("needs", "v04_needs", src=(P, "needs", "why"), kicker="ADVICE, NOT A PRICE LIST",
         head="Her problems,\nturned into a plan.", callout="ticks"),
    Beat("why", "v05_why", src=(P, "why", "objection"), kicker="WHY THIS BUNDLE",
         head="It shows its reasoning.", sub="Ranked from 368 real Accel customers. Every ₹ from the catalogue, never from the AI.",
         callout="why", crop_frac=0.757, zoom=1),
    Beat("objection", "v06_objection", src=(P, "objection", "recommend"), kicker="“THIS IS TOO EXPENSIVE”",
         head="Choices, each with a price.", sub="No silent cuts. She decides.", callout="choices", lag=1.4),
    Beat("recommend", "v07_recommend", src=(P, "recommend", "quote", 0, 0.6), kicker="IT SELLS",
         head="It recommends,\nin her own words.", sub="Then it asks for the order.", callout="reasons", lag=1.4),
    Beat("kyc", "v08_kyc", src=(P, "quote", "checkout", 0, -0.5), kicker="ONE CLEAR PRICE",
         head="₹3,593 a month.\nOne bill.", sub="Five services, 12-month price before GST.", callout="verified", zoom=1,
         switch=("kyc", "SMART KYC · DPDP CONSENT", "Verified in about 2 minutes.",
                 "Consent per purpose · DigiLocker · Aadhaar OTP. No paper, no office.")),
    Beat("fraud", "v09_fraud", src=("k06", "loaded", "end", -0.6, 0), kicker="FRAUD CHECK · SPECIMEN K06",
         head="A tampered certificate? Caught.", callout="fail", post=1.2),
    Beat("tracker", "v10_tracker", src=(P, "tracker", "updates"), kicker="TRACKER",
         head="Her slot.\nA date for every service.", callout="slots", shot=2.1, lag=-1.5),
    # real WhatsApp on Sujal's phone (import_clip.py): an update arrives, then she types STATUS and gets the reply
    Beat("whatsapp", "v11_whatsapp", src=[("wa_open", "start", "start", 3.6, 7.6), ("wa_status", "start", "start", 2.0, 9.6)],
         split=[0.28, 0.72], kicker="WHATSAPP UPDATES · REAL PHONE", head="3 calls chasing status → 0.",
         sub="She can reply STATUS, RESCHEDULE or PROBLEM any time.", post=1.5, zf=1.25),
    Beat("lang", "v12_lang", src=[("hi", "start", "end"), ("ta", "start", "end")], kicker="10 INDIAN LANGUAGES",
         head="Her language. Typed or spoken.", sub="Speak into the mic, or have any reply read aloud.", langs=True, mic=True,
         zoom=None, post=1.3),
    Beat("chain", "v12b_chain", src=("chain", "start", "end"), kicker="SMALL MULTI-SITE · 5 RESTAURANTS",
         head="Each outlet set up\nfor its size. One bill.",
         sub="Lighter setup for the 2 small outlets: ₹33,819 → ₹32,221 a month. Installs run side by side.",
         callout="outlets", lag=3.2, pre=0.15),
    Beat("partner", "v13_partner", kind="console", kicker="PARTNERS SELL MORE, NOT LESS",
         head="A local partner who speaks her language.",
         sub="Leads the advisor can't close go to a partner matched by city and language. Assisted sales stay theirs for 30 days.",
         pre=0.2, post=0.4, calllist=True),
    Beat("funnel", "v14_funnel", kind="funnel", pre=0.3, post=0.4),
    Beat("impact", "v15_impact", kind="impact", pre=0.2, post=2.2),  # the last number holds 2 s before the end card
    Beat("close", "v16_close", kind="close", pre=0.3, post=4.0),
]
GROUP = {"phone": "phone", "rewind": "phone", "console": "console", "funnel": "funnel", "impact": "impact", "close": "close"}


def plan(lines):
    t = 0.0
    for b in BEATS:
        b.L = len(lines[b.line][0]) / SR if b.line else 0.0
        b.words = lines[b.line][1] if b.line else []
        b.D = b.pre + b.L + b.post if b.line else b.dur
        b.t0 = t
        t += b.D
    return t


# ---------------------------------------------------------------- phone timing
def src_map(name, a_key, b_key, a_off, b_off, D):
    a, b = M[f"{name}:{a_key}"] + a_off, M[f"{name}:{b_key}"] + b_off
    clip = max(0.05, b - a)
    s = min(2.4, max(0.92, clip / max(0.1, D - 0.2)))
    if clip / s > D:
        a = b - D * s
    return a, b, s


def beat_src(b):
    if b.kind != "phone" or not b.src:
        return []
    srcs = b.src if isinstance(b.src, list) else [b.src]
    n = len(srcs)
    split = b.kw.get("split") or [1.0 / n] * n  # share of the beat each recording gets
    out, s0 = [], 0.0
    for s, fr in zip(srcs, split):
        name, ak, bk = s[:3]
        ao, bo = (s[3], s[4]) if len(s) > 3 else (0.0, 0.0)
        part = b.D * fr
        a, e, sp = src_map(name, ak, bk, ao, bo, part)
        out.append((s0, part, name, a, e, sp))
        s0 += part
    return out


def phone_path(b, tau):
    if b.kind == "rewind":
        name, ak, bk = b.src
        a, e = M[f"{name}:{ak}"], M[f"{name}:{bk}"]
        return frames(name).path(e - (e - a) * ease_io(tau / b.D))
    for (s0, part, name, a, e, sp) in reversed(b._src):
        if tau >= s0:
            return frames(name).path(min(e, a + (tau - s0) * sp))
    return None


def to_beat_time(b, wall, name):
    """Where a moment of the recording lands inside this beat (or None if it isn't shown)."""
    for (s0, part, n, a, e, sp) in b._src:
        if n == name and a <= wall <= e:
            return s0 + (wall - a) / sp
    return None


# ---------------------------------------------------------------- overlays
def callout_card(b):
    if not b.callout:
        return None
    name = b._src[0][2]
    key = f"{name}:{b.callout}"
    r = RECTS.get(key)
    if not r:
        print("  (no rect for", key, ")")
        return None
    im = Image.open(frames(name).path(r["t"] + b.kw.get("shot", 0.08))).convert("RGB")  # shot: show the card after her tap
    pad = 10
    hh = r["h"] * b.kw.get("crop_frac", 1.0)
    box = (max(0, int(r["x"] * 2) - pad), max(0, int(r["y"] * 2) - pad),
           min(im.width, int((r["x"] + r["w"]) * 2) + pad), min(im.height, int((r["y"] + hh) * 2) + pad))
    crop = im.crop(box)
    top = b._text_bottom + 34
    maxw, maxh = PANEL_W, 1036 - top
    sc = min(maxw / crop.width, maxh / crop.height, 1.3)
    crop = crop.resize((int(crop.width * sc), int(crop.height * sc)), Image.LANCZOS)
    card, pad2 = card_from(crop)
    s0, part, n, a, e, sp = b._src[0]
    at = to_beat_time(b, min(e, max(a, r["t"] - b.kw.get("lag", 0.0))), name)
    at = 0.7 if at is None else min(max(0.6, at), max(0.6, b.D - 1.8))
    return {"img": card, "x": PANEL_X - pad2, "y": top - pad2, "at": at}


def notification():
    s = 2
    w, h = (PW - 24) * s, 104 * s
    im = Image.new("RGBA", (w + 40 * s, h + 40 * s), (0, 0, 0, 0))
    sh_ = Image.new("L", im.size, 0)
    ImageDraw.Draw(sh_).rounded_rectangle((20 * s, 26 * s, 20 * s + w, 26 * s + h), 22 * s, fill=120)
    im.paste((0, 0, 0, 255), (0, 0), sh_.filter(ImageFilter.GaussianBlur(14 * s)))
    d = ImageDraw.Draw(im)
    x0, y0 = 20 * s, 20 * s
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), 22 * s, fill=(250, 250, 252, 248))
    d.rounded_rectangle((x0 + 14 * s, y0 + 16 * s, x0 + 50 * s, y0 + 52 * s), 9 * s, fill=RED)
    d.text((x0 + 32 * s, y0 + 34 * s), "A", font=font("Inter-Bold", 21 * s), fill=WHITE, anchor="mm")
    d.text((x0 + 62 * s, y0 + 15 * s), "Accel Saathi", font=font("Inter-SemiBold", 17 * s), fill=(20, 22, 34))
    d.text((x0 + w - 16 * s, y0 + 16 * s), "now", font=font("Inter-Regular", 14 * s), fill=(120, 124, 140), anchor="ra")
    msg = wrap("All 5 services are live. One bill, one support number: 121. Welcome to Accel Business!",
               font("Inter-Regular", 15 * s), w - 80 * s)
    for i, ln in enumerate(msg[:2]):
        d.text((x0 + 62 * s, y0 + (42 + 20 * i) * s), ln, font=font("Inter-Regular", 15 * s), fill=(55, 58, 72))
    im = im.resize((im.width // s, im.height // s), Image.LANCZOS)
    return np.asarray(im)


NOTIF = None


def big_lines(b):
    """'5 days.' and '0 calls.' pop in on the words that say them."""
    def word_at(*targets):
        for s, e, w_ in b.words:
            if w_.lower().strip(".,") in targets:
                return s
        return None
    out = []
    for text, color, trig, y in (("5 days.", WHITE, word_at("five"), 330), ("0 calls.", RED, word_at("phone", "call"), 500)):
        im = Image.new("RGBA", (900, 200), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((0, 10), text, font=font("InterDisplay-ExtraBold", 150), fill=color)
        out.append((tight(np.asarray(im), PANEL_X - 6, y), b.pre + (trig if trig is not None else 1.0)))
    return out


def lang_chips():
    names = ["English", "Hindi", "Tamil", "Bengali", "Telugu", "Marathi", "Gujarati", "Kannada", "Malayalam", "Punjabi"]
    im = Image.new("RGBA", (PANEL_W + 40, 260), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font("Inter-SemiBold", 30)
    x, y, boxes = 0, 0, []
    for n in names:
        tw = d.textlength(n, font=f)
        if x + tw + 48 > PANEL_W:
            x, y = 0, y + 74
        boxes.append((x, y, x + tw + 44, y + 56, n))
        x += tw + 60
    layers = []
    for (x0, y0, x1, y1, n) in boxes:
        c = Image.new("RGBA", im.size, (0, 0, 0, 0))
        dc = ImageDraw.Draw(c)
        hl = n in ("Hindi", "Tamil")
        dc.rounded_rectangle((x0, y0, x1, y1), 28, fill=(RED + (255,)) if hl else (255, 255, 255, 26),
                             outline=None if hl else (255, 255, 255, 90), width=2)
        dc.text(((x0 + x1) / 2, (y0 + y1) / 2), n, font=f, fill=WHITE, anchor="mm")
        layers.append(tight(np.asarray(c)))
    return layers


# ---------------------------------------------------------------- full-screen beats
def counter(a, b, x, fmt):
    return fmt(a + (b - a) * ease_out(x))


def word_time(b, *targets, default=0.0, last=False):
    """When a word is spoken in this beat (seconds from the beat start): the first match, or the last with last=True."""
    hits = [b.pre + s for s, e, w_ in b.words if w_.lower().strip(".,:;") in targets]
    return (hits[-1] if last else hits[0]) if hits else default


def draw_funnel(b, tau):
    im = Image.fromarray(BG_BRAND.copy())
    d = ImageDraw.Draw(im)
    tracked(d, (160, 150), "ACCEL'S SMALL-BUSINESS FUNNEL · APR–JUN 2026", font("Inter-Bold", 24), RED)
    a_head = ease_out((tau - 0.1) / 0.5)
    t_money = word_time(b, "thirty-five", "thirty", default=1.6)
    d.text((160, 196 + 20 * (1 - a_head)), "5,000 small-business leads a quarter.", font=font("InterDisplay-Bold", 64),
           fill=tuple(int(c * a_head + INK[i] * (1 - a_head)) for i, c in enumerate(WHITE)))
    # the bar: live / lost to the journey / other reasons
    x0, x1, y0, y1 = 160, 1760, 400, 500
    grow = ease_io((tau - 0.3) / 1.0)
    total = 5000
    segs = [(368, (238, 240, 248)), (1583, RED), (3049, (78, 84, 122))]
    t_one = word_time(b, "one", default=5.0)
    xx = x0
    for i, (n, col) in enumerate(segs):
        w = (x1 - x0) * n / total * grow
        if w > 1:
            c = col
            if i == 1:
                pulse = 0.5 + 0.5 * math.sin(max(0, tau - t_one) * 6) if tau > t_one else 0
                k = 0.25 * pulse if tau < t_one + 1.2 else 0
                c = tuple(min(255, int(v + (255 - v) * k)) for v in col)
            d.rounded_rectangle((xx, y0, xx + w, y1), 14 if i in (0, 2) else 4, fill=c)
        xx += w
    lab = ease_out((tau - 1.0) / 0.5)
    if lab > 0:
        fl, fs = font("InterDisplay-Bold", 46), font("Inter-Regular", 26)
        sx = [x0, x0 + (x1 - x0) * 368 / total, x0 + (x1 - x0) * (368 + 1583) / total]
        col = [WHITE, RED, GREY]
        txt = [("368", "went live"), ("1,583", "left because of the journey"), ("3,049", "other reasons")]
        for i in range(3):
            xi = sx[i] + (0 if i != 1 else 18)
            if i == 0:
                xi = x0
            d.text((xi if i != 0 else x0, 528), txt[i][0], font=fl, fill=col[i])
            d.text((xi if i != 0 else x0, 584), txt[i][1], font=fs, fill=GREY)
    # money
    am = ease_out((tau - t_money) / 0.5)
    if am > 0:
        d.text((160, 690 + 16 * (1 - am)), "₹35.6 lakh", font=font("InterDisplay-ExtraBold", 96), fill=WHITE)
        for j, line in enumerate(("of ₹55.4 lakh spent each quarter", "went on leads that were never won")):
            d.text((160, 806 + 42 * j + 16 * (1 - am)), line, font=font("Inter-Regular", 32), fill=GREY)
    # why they walked away, as the voice names it
    chips = [(("visits",), "Visits  ·  827"), (("paperwork",), "Paperwork  ·  273"), (("waiting",), "Waiting on quotes and installs  ·  483")]
    cx = 1080
    if tau >= word_time(b, "visits", default=8):
        tracked(d, (cx, 664), "WHY THE 1,583 LEFT", font("Inter-Bold", 22), GREY)
    for i, (keys, label) in enumerate(chips):
        tc = word_time(b, *keys, default=8 + i)
        if tau >= tc:
            f = font("Inter-SemiBold", 28)
            tw = d.textlength(label, font=f)
            y = 708 + i * 78
            d.rounded_rectangle((cx, y, cx + tw + 48, y + 58), 29, outline=RED, width=3, fill=(RED[0] // 4 + 20, 20, 40))
            d.text((cx + 24, y + 29), label, font=f, fill=WHITE, anchor="lm")
    return np.asarray(im).copy()


def draw_impact(b, tau):
    im = Image.fromarray(BG_BRAND.copy())
    d = ImageDraw.Draw(im)
    tracked(d, (160, 150), "SAME LEADS · MODELLED, RUNNING COSTS INCLUDED", font("Inter-Bold", 24), RED)
    a = ease_out((tau - 0.05) / 0.5)
    d.text((160, 196 + 20 * (1 - a)), "Saathi fixes the journey.", font=font("InterDisplay-Bold", 64), fill=WHITE)
    cols = [
        # each number arrives on the word that says it: "Live in a week…", "…twice the customers, at half the cost"
        (word_time(b, "week", default=1.5), (17.6, 7.0), lambda v: f"{v:.1f}".rstrip("0").rstrip("."), "17.6 →", "days from lead to live", ""),
        (word_time(b, "twice", default=5.0), (368, 760), lambda v: f"{int(round(v)):,}", "368 →", "customers a quarter", "2×"),
        (word_time(b, "half", default=6.5, last=True), (15053, 7746), lambda v: f"₹{int(round(v)):,}", "₹15,053 →", "cost per customer", "½"),
    ]
    for i, (tc, (v0, v1), fmt, before, label, badge) in enumerate(cols):
        x = 160 + i * 560
        ap = ease_out((tau - tc) / 0.5)
        if ap <= 0:
            continue
        y = 360 + 30 * (1 - ap)
        d.rounded_rectangle((x, y, x + 500, y + 380), 28, fill=(255, 255, 255, 18) if False else (39, 44, 84), outline=(84, 92, 140), width=2)
        d.text((x + 40, y + 44), before, font=font("InterDisplay-SemiBold", 40), fill=GREY)
        d.text((x + 40, y + 100), counter(v0, v1, (tau - tc) / 1.1, fmt), font=font("InterDisplay-ExtraBold", 104),
               fill=RED if i > 0 else WHITE)
        d.text((x + 40, y + 250), label, font=font("Inter-Regular", 32), fill=GREY)
        if badge and tau > tc + 1.0:
            ab = back_out((tau - tc - 1.0) / 0.35)
            r = 44 * ab
            d.ellipse((x + 440 - r, y + 40 - r, x + 440 + r, y + 40 + r), fill=WHITE)
            d.text((x + 440, y + 40), badge, font=font("InterDisplay-ExtraBold", int(44 * max(0.2, ab))), fill=INK, anchor="mm")
    af = ease_out((tau - 2.0) / 0.6)
    if af > 0:
        for j, ln in enumerate(("Model: half of the journey losses removed at each step; every other loss stays. Same ₹55.4 lakh spend, plus ₹3.5 lakh",
                                "a quarter to run Saathi (cloud, private AI, e-KYC, WhatsApp). With a 5-person team, about ₹11,700 each. Workings: deck appendix.")):
            d.text((160, 810 + 34 * j), ln, font=font("Inter-Regular", 24), fill=DIM)
    return np.asarray(im).copy()


QR = Image.open(os.path.join(IMG, "qr_app.png")).convert("RGB").resize((280, 280), Image.NEAREST)


def draw_close(b, tau):
    im = Image.fromarray(BG.copy())
    d = ImageDraw.Draw(im)

    def a(t0, dur=0.6):
        return ease_out((tau - t0) / dur)
    k = a(0.1)
    y = 300 + 30 * (1 - k)
    if k > 0:
        d.rounded_rectangle((160, y, 280, y + 120), 30, fill=RED)
        d.text((220, y + 60), "A", font=font("InterDisplay-Bold", 78), fill=WHITE, anchor="mm")
        d.text((320, y - 6), "Accel Saathi", font=font("InterDisplay-Bold", 120), fill=WHITE)
    t_line = word_time(b, "every", default=1.2)
    k = a(t_line)
    if k > 0:
        d.text((164, 470 + 20 * (1 - k)), "Every small business, online in one conversation.", font=font("InterDisplay-Medium", 50), fill=WHITE)
    k = a(t_line + 1.4)
    if k > 0:
        d.text((164, 600 + 16 * (1 - k)), "Try it live:  udyam.openforge.online", font=font("Inter-SemiBold", 42), fill=RED)
        d.text((164, 670 + 16 * (1 - k)), "Team TouristGuide_NIT_Jamshedpur · Sujal Bhatu · Prince Mehta", font=font("Inter-Regular", 32), fill=GREY)
        q = Image.new("RGB", (320, 320), WHITE)
        q.paste(QR, (20, 20))
        m = Image.new("L", (320, 320), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, 319, 319), 26, fill=int(255 * k))
        im.paste(q, (1440, 380 + int(20 * (1 - k))), m)
        d.text((1600, 730 + 16 * (1 - k)), "Scan to try it", font=font("Inter-Regular", 26), fill=GREY, anchor="ma")
    arr = np.asarray(im).astype(np.float32)
    fade = min(1.0, max(0.0, (b.D - tau) / 0.9))
    return (arr * fade).astype(np.uint8)


# ---------------------------------------------------------------- console (laptop)
CON = None
LX, LY, LW, LH = 96, 170, 1150, 719


def console_art():
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    s = Image.new("L", (W, H), 0)
    ImageDraw.Draw(s).rounded_rectangle((LX - 30, LY + 30, LX + LW + 30, LY + LH + 70), 30, fill=150)
    layer.paste((4, 5, 12, 255), (0, 0), s.filter(ImageFilter.GaussianBlur(30)))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((LX - 18, LY - 18, LX + LW + 18, LY + LH + 18), 26, fill=(14, 15, 26, 255), outline=(80, 86, 120, 255), width=2)
    d.polygon([(LX - 80, LY + LH + 18), (LX + LW + 80, LY + LH + 18), (LX + LW + 40, LY + LH + 52), (LX - 40, LY + LH + 52)], fill=(170, 175, 196, 255))
    d.rounded_rectangle((LX + LW / 2 - 90, LY + LH + 18, LX + LW / 2 + 90, LY + LH + 28), 5, fill=(120, 124, 146, 255))
    return np.asarray(layer)


def console_cams():
    """Camera keyframes over the console screenshot (2x pixels): the whole page, the leads, the assisted card."""
    im = CON
    ar = LW / LH

    def fit(x, y, w, h, pad=40):
        x, y, w, h = x * 2 - pad, y * 2 - pad, w * 2 + 2 * pad, h * 2 + 2 * pad
        if w / h < ar:
            nw = h * ar
            x -= (nw - w) / 2
            w = nw
        else:
            nh = w / ar
            y -= (nh - h) / 2
            h = nh
        if w > im.width:
            w, h = im.width, im.width / ar
        x = min(max(0, x), im.width - w)
        y = min(max(0, y), im.height - h)
        return (x, y, w, h)
    r = {k.split(":")[1]: v for k, v in RECTS.items() if k.startswith("console:")}
    full = (0, 0, im.width, im.width / ar) if im.width / ar <= im.height else (0, 0, im.height * ar, im.height)
    # tight crops, so a judge can read the console: the top of the scored call list, then the assisted-chat card
    # with its counter QR. The camera ends there: the recorded partner sales table is all zeros (fresh demo data),
    # which would undercut "the sale stays theirs".
    def part(key, w, h=None):
        q = r[key]
        return fit(q["x"], q["y"] + q.get("sy", 0), min(w, q["w"]), min(h or q["h"], q["h"]), pad=16)
    leads = part("leads", 560, 330) if "leads" in r else full
    assist = part("assist", 600) if "assist" in r else full
    return [(0.0, full), (0.08, full), (0.22, leads), (0.5, leads), (0.64, assist), (1.0, assist)]


def console_view(b, tau):
    x = tau / b.D
    cams = b._cams
    for (t0, c0), (t1, c1) in zip(cams, cams[1:]):
        if t0 <= x <= t1:
            k = ease_io((x - t0) / max(1e-6, t1 - t0))
            c = [c0[i] + (c1[i] - c0[i]) * k for i in range(4)]
            break
    else:
        c = cams[-1][1]
    crop = CON.crop((int(c[0]), int(c[1]), int(c[0] + c[2]), int(c[1] + c[3]))).resize((LW, LH), Image.LANCZOS)
    return np.asarray(crop)



# ---------------------------------------------------------------- punch-in zooms, the mic, the call list
ZOOM = 1.45


def zoom_points(b):
    """One punch-in per phone beat, on the tap that matters (kw zoom = which tap in the beat; None = no zoom)."""
    pick = b.kw.get("zoom", 0)
    if pick is None:
        return []
    pts = []
    for name, wall, *rest in TAPS:
        if len(rest) < 3 or rest[2] != "tap" or rest[0] is None:
            continue
        bt = to_beat_time(b, wall, name)
        if bt is not None and 0.5 <= bt <= b.D - 1.2:
            pts.append((bt, rest[0] * 2, rest[1] * 2))
    return pts[pick:pick + 1] if pick < len(pts) else pts[-1:]


def zoom_at(b, tau):
    best = (1.0, None)
    for bt, cx, cy in b._zooms:
        if tau < bt - 0.55 or tau > bt + 1.6:
            continue
        e = ease_io((tau - (bt - 0.55)) / 0.45) if tau < bt - 0.1 else 1.0 if tau <= bt + 1.0 else 1 - ease_io((tau - bt - 1.0) / 0.6)
        z = 1 + (b.kw.get("zf", ZOOM) - 1) * e  # zf: a gentler zoom for a wide bubble
        if z > best[0]:
            best = (z, (cx, cy))
    return best


def zoomed(path, z, c):
    """The phone screen magnified around the tap, still inside the phone (recordings are 780 x 1688)."""
    im = Image.open(path).convert("RGB")
    w, h = im.width / z, im.height / z
    x = min(max(0.0, c[0] - w / 2), im.width - w)
    y = min(max(0.0, c[1] - h * 0.45), im.height - h)
    return np.asarray(im.resize((PW, PH), Image.LANCZOS, box=(x, y, x + w, y + h)))


def mic_ring_at(b):
    r = RECTS.get("hi:mic")
    if not r:
        print("  (no rect for hi:mic)")
        return None
    # measured on the frames: the bottom bar draws about 20 CSS px above its layout box at the viewport edge
    return (PX + (r["x"] + r["w"] / 2) * PW / 390, PY + (r["y"] + r["h"] / 2 - 20) * PH / 844)


def ring_draw(canvas, b, tau):
    """A soft pulse around the microphone while the Hindi chat is on screen: it can be spoken to, no transcript faked."""
    part = b.D / max(1, len(b._src))
    if not 0.5 <= tau <= part - 0.2:
        return
    k = min(ease_out((tau - 0.5) / 0.3), 1 - ease_io((tau - (part - 0.5)) / 0.3))
    cx, cy = b._mic
    s = 2
    size = 132
    im = Image.new("RGBA", (size * s, size * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for j in range(2):
        ph = ((tau - 0.5) * 0.9 + j * 0.5) % 1.0
        rad = (30 + 28 * ph) * s
        al = int(230 * (1 - ph) * k)
        d.ellipse((size * s / 2 - rad, size * s / 2 - rad, size * s / 2 + rad, size * s / 2 + rad), outline=RED + (al,), width=3 * s)
    d.ellipse((size * s / 2 - 30 * s, size * s / 2 - 30 * s, size * s / 2 + 30 * s, size * s / 2 + 30 * s), outline=RED + (int(255 * k),), width=4 * s)
    im = im.resize((size, size), Image.LANCZOS)
    over(canvas, np.asarray(im), int(cx - size / 2), int(cy - size / 2))


def call_list_tag():
    im = Image.new("RGBA", (760, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f1, f2 = font("Inter-Bold", 24), font("Inter-Medium", 24)
    t1, t2 = "SCORED CALL LIST", "  ·  chance, why, next best action"
    w = d.textlength(t1, font=f1) + d.textlength(t2, font=f2) + 44
    d.rounded_rectangle((0, 4, w, 58), 27, fill=RED + (255,))
    d.text((22, 31), t1, font=f1, fill=WHITE, anchor="lm")
    d.text((22 + d.textlength(t1, font=f1), 31), t2, font=f2, fill=WHITE, anchor="lm")
    return np.ascontiguousarray(np.asarray(im)[:, :int(w) + 2])


# ---------------------------------------------------------------- render
def text_alpha(b, tau):
    a_in = ease_out((tau - 0.05) / 0.45)
    a_out = 1 - ease_io((tau - (b.D - 0.3)) / 0.3) if b.D > 0.6 else 1
    return a_in * a_out, 24 * (1 - a_in)


def prepare(b):
    b._src = beat_src(b)
    b._text, b._text_bottom = (None, 0)
    if b.kind in ("phone", "rewind", "console"):
        if b.kw.get("big"):
            b._text, b._text_bottom = text_panel(b.kicker, "", "", top=250)
        elif b.kind == "rewind":
            b._text, b._text_bottom = text_panel(b.kicker, b.head, "", top=440, head_size=84)
        elif b.kind == "console":
            im = Image.new("RGBA", (560, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            y = 250
            tracked(d, (0, y), b.kicker, font("Inter-Bold", 22), RED, track=2)
            y += 46
            for ln in wrap(b.head, font("InterDisplay-Bold", 54), 540):
                d.text((0, y), ln, font=font("InterDisplay-Bold", 54), fill=WHITE)
                y += 64
            y += 18
            for ln in wrap(b.sub, font("Inter-Regular", 28), 530):
                d.text((0, y), ln, font=font("Inter-Regular", 28), fill=GREY)
                y += 40
            b._text = tight(np.asarray(im), 1300, 0)
        else:
            b._text, b._text_bottom = text_panel(b.kicker, b.head, b.sub, top=150 if b.callout else None)
    b._text2, b._switch_t = None, None
    if b.kw.get("switch"):  # the headline changes on a spoken word ("One clear price…" → "Then KYC…")
        word, k2, h2, s2 = b.kw["switch"]
        b._text2, bottom2 = text_panel(k2, h2, s2, top=150 if b.callout else None)
        b._switch_t = word_time(b, word, default=b.D / 3)
        b._text_bottom = max(b._text_bottom, bottom2)
    b._callout = callout_card(b) if b.kind == "phone" else None
    b._zooms = zoom_points(b) if b.kind == "phone" else []
    b._mic = mic_ring_at(b) if b.kw.get("mic") else None
    b._calllist = call_list_tag() if b.kw.get("calllist") else None
    b._big = big_lines(b) if b.kw.get("big") else []
    b._langs = lang_chips() if b.kw.get("langs") else []
    if b.kind == "console":
        b._cams = console_cams()
    b._taps = []
    for name, wall, *_ in TAPS:
        bt = to_beat_time(b, wall, name) if b._src else None
        if bt is not None and 0 <= bt < b.D:
            b._taps.append(bt)


CONSOLE_LAYER = None


def render_beat(b, tau, guide=None):
    g = GROUP[b.kind]
    if g == "funnel":
        return draw_funnel(b, tau)
    if g == "impact":
        return draw_impact(b, tau)
    if g == "close":
        return draw_close(b, tau)
    if g == "console":
        canvas = BG_BRAND.copy()
        k = ease_out(tau / 0.6)
        over_t(canvas, CONSOLE_LAYER, 0, int(30 * (1 - k)), k)
        scr = console_view(b, tau)
        dst = canvas[LY + int(30 * (1 - k)):LY + int(30 * (1 - k)) + LH, LX:LX + LW].astype(np.float32)
        canvas[LY + int(30 * (1 - k)):LY + int(30 * (1 - k)) + LH, LX:LX + LW] = (dst + (scr - dst) * k).astype(np.uint8)
        a, dy = text_alpha(b, tau)
        over_t(canvas, b._text, 0, int(dy), a)
        if b._calllist is not None:  # while the camera is on the leads table
            x = tau / b.D
            k = min(ease_out((x - 0.24) / 0.06), 1 - ease_io((x - 0.5) / 0.05))
            if k > 0:
                over(canvas, b._calllist, LX - 18, LY - 92 + int(10 * (1 - k)), k)  # above the laptop, so nothing on it is hidden
        return canvas
    # phone
    enter = ease_out(tau / 0.7) if b.kw.get("enter") else 1.0
    dy = int(50 * (1 - enter))
    dx = CENTER_DX if b.id == "cold" else int(CENTER_DX * (1 - ease_io(tau / 1.0))) if b.id == "open" else 0
    if dx or dy or enter < 1:
        canvas = BG_BRAND.copy()
        over_t(canvas, PHONE_T, dx, dy, enter)
    else:
        canvas = PHONE_BASE.copy()
    p = phone_path(b, tau)
    if p:
        z, c = zoom_at(b, tau)
        put_screen(canvas, zoomed(p, z, c) if z > 1.002 else screen(p), dx, dy, enter)
    if b._mic is not None:
        ring_draw(canvas, b, tau)
    if b.kw.get("notify") is not None:
        global NOTIF
        if NOTIF is None:
            NOTIF = notification()
        k = ease_out((tau - b.kw["notify"]) / 0.45)
        if k > 0:
            over(canvas, NOTIF, PX - 8 + dx, PY - 12 + int(-130 * (1 - k)) + dy, min(1, k * 1.5))
    if b.kind == "rewind":
        # a quick scan-line flicker sells the rewind
        k = math.sin(math.pi * min(1, tau / b.D))
        reg = canvas[PY:PY + PH, PX:PX + PW].astype(np.float32)
        reg[::4] *= 1 - 0.18 * k
        canvas[PY:PY + PH, PX:PX + PW] = reg.astype(np.uint8)
    if b._text is not None:
        a, ty = text_alpha(b, tau - (0.75 if b.id == "open" else 0))  # the phone moves aside first
        if b.kind == "rewind":
            a = math.sin(math.pi * min(1, tau / b.D)) ** 0.5
        if b._text2 is not None:
            k = ease_io((tau - b._switch_t + 0.1) / 0.4)
            if k < 1:
                over_t(canvas, b._text, 0, int(ty - 14 * k), a * (1 - k))
            if k > 0:
                over_t(canvas, b._text2, 0, int(14 * (1 - k)), a * k)
        else:
            over_t(canvas, b._text, 0, int(ty), a)
    for layer, t_on in b._big:
        k = back_out((tau - t_on) / 0.4)
        if tau >= t_on:
            a, _ = text_alpha(b, tau)
            over_t(canvas, layer, 0, int(26 * (1 - min(1, k))), min(1.0, (tau - t_on) / 0.2) * (a if tau > b.D - 0.3 else 1))
    if b._langs:
        n = len(b._langs)
        for i, layer in enumerate(b._langs):
            t_on = 0.5 + i * (max(1.5, b.D - 2.0) / n)
            k = ease_out((tau - t_on) / 0.3)
            if k > 0:
                a, _ = text_alpha(b, tau)
                over_t(canvas, layer, PANEL_X, b._text_bottom + 36 + int(12 * (1 - k)), k * a)
    c = b._callout
    if c is not None and tau >= c["at"]:
        k = ease_out((tau - c["at"]) / 0.4)
        a_out = 1 - ease_io((tau - (b.D - 0.3)) / 0.3)
        img = c["img"]
        if k < 1:
            s = 0.94 + 0.06 * k
            pil = Image.fromarray(img)
            pil = pil.resize((max(1, int(pil.width * s)), max(1, int(pil.height * s))), Image.BILINEAR)
            img = np.asarray(pil)
        over(canvas, img, c["x"], c["y"] + int(18 * (1 - k)), k * a_out)
    return canvas


def guide_strip(b, tau, canvas):
    """Karaoke line for recording your own voice: spoken words white, coming words grey."""
    if not b.line or tau < b.pre - 0.4 or tau > b.pre + b.L + 0.2:
        return
    key = (b.id, sum(1 for s, e, w in b.words if b.pre + s <= tau))
    if key not in GUIDE_CACHE:
        words = SCRIPT[b.line].split()
        n_done = key[1]
        im = Image.new("RGBA", (W, 130), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, W, 130), fill=(0, 0, 0, 175))
        f = font("Inter-Medium", 34)
        lines, cur = [], []
        for w_ in words:
            if d.textlength(" ".join(cur + [w_]), font=f) > W - 240 and cur:
                lines.append(cur)
                cur = []
            cur.append(w_)
        lines.append(cur)
        i = 0
        for li, ln in enumerate(lines[:2]):
            x = 120
            for w_ in ln:
                d.text((x, 22 + li * 48), w_, font=f, fill=WHITE if i < n_done else (150, 155, 175))
                x += d.textlength(w_ + " ", font=f)
                i += 1
        GUIDE_CACHE[key] = np.asarray(im)
    over(canvas, GUIDE_CACHE[key], 0, H - 130)


GUIDE_CACHE = {}


def frame_at(T, guide):
    i = max(0, bisect.bisect_right(STARTS, T) - 1)
    b = BEATS[i]
    tau = T - b.t0
    img = render_beat(b, tau)
    nb = BEATS[i + 1] if i + 1 < len(BEATS) else None
    if nb and GROUP[nb.kind] != GROUP[b.kind] and tau > b.D - 0.45:  # cross-fade between layouts
        k = ease_io((tau - (b.D - 0.45)) / 0.45)
        nxt = render_beat(nb, 0.0)
        img = (img.astype(np.float32) * (1 - k) + nxt.astype(np.float32) * k).astype(np.uint8)
    if guide:
        img = img.copy()
        guide_strip(b, tau, img)
    elif SUBS:
        img = overlay_text(img, T)
    return img


SUBS = os.environ.get("SUBS") == "1"
CHUNKS = []  # (start, end, text) for burned-in subtitles


def make_chunks():
    """Subtitle chunks from each line's word timings: phrases broken at sentence ends and commas, long ones split in
    balanced halves (at most ~54 characters), numbers as figures, never overlapping, no flicker between close chunks."""
    show = {"thirty-five": "₹35", "eighteen": "18", "ten": "10"}
    out = []
    for b in BEATS:
        if not b.line:
            continue
        text, words = SCRIPT[b.line].split(), b.words
        if len(words) != len(text):
            print(f"  note: {b.line} has {len(words)} timed words for {len(text)} script words")
        disp = [show.get(w_, w_) for w_ in text]
        for i in range(len(text) - 2):  # "thirty-five lakh rupees" reads as "₹35 lakh"
            if text[i] == "thirty-five" and text[i + 2].startswith("rupees"):
                disp[i + 2] = ""
        ends = [i for i, w_ in enumerate(text) if w_.endswith((".", "?", "!", ":"))] + [len(text) - 1]
        segs, cur = [], []
        for i, w_ in enumerate(text):
            cur.append(i)
            s = " ".join(disp[j] for j in cur if disp[j])
            rest = " ".join(disp[j] for j in range(cur[0], next(e for e in ends if e >= i) + 1) if disp[j])
            if (w_.endswith((".", "?", "!", ":")) or i == len(text) - 1
                    or (w_.endswith(",") and len(s) >= 18 and len(rest) > 54)):
                segs.append(cur)
                cur = []
        for seg in segs:
            full = " ".join(disp[j] for j in seg if disp[j])
            parts = -(-len(full) // 54)
            if parts > 1:  # balanced split at word boundaries
                target, acc, pieces, piece = len(full) / parts, 0, [], []
                for j in seg:
                    piece.append(j)
                    acc += len(disp[j]) + 1
                    if acc >= target * (len(pieces) + 1) and len(pieces) < parts - 1:
                        pieces.append(piece)
                        piece = []
                if piece:
                    pieces.append(piece)
            else:
                pieces = [seg]
            for pc in pieces:
                a = words[min(pc[0], len(words) - 1)][0]
                e = words[min(pc[-1], len(words) - 1)][1]
                out.append([b.t0 + b.pre + a, b.t0 + b.pre + e + 0.25, " ".join(disp[j] for j in pc if disp[j])])
    out.sort()
    for k in range(len(out) - 1):
        nxt = out[k + 1][0]
        if out[k][1] > nxt - 0.04 or nxt - out[k][1] < 0.4:
            out[k][1] = nxt - 0.04
    return out


def overlay_text(img, T):
    """Burned-in subtitle at the bottom centre, and a 'recorded on the live app' note in the opening seconds."""
    sub = next((c for c in CHUNKS if c[0] <= T < c[1]), None)
    note = 0.4 <= T < 15.4
    if not sub and not note:
        return img
    im = Image.fromarray(img).convert("RGBA")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    if sub:
        f = font("Inter-SemiBold", 36)
        tw = d.textlength(sub[2], font=f)
        x0, y1 = (W - tw) / 2, H - 38
        d.rounded_rectangle((x0 - 22, y1 - 56, x0 + tw + 22, y1), 12, fill=(12, 14, 30, 215))
        d.text((W / 2, y1 - 28), sub[2], font=f, fill=WHITE, anchor="mm")
    if note:
        a = int(255 * min(1.0, (T - 0.4) / 0.4, (15.4 - T) / 0.4))
        d.text((W - 80, 104), "Recorded on the live app · udyam.openforge.online", font=font("Inter-Regular", 22),
               fill=GREY + (a,), anchor="rm")
    return np.asarray(Image.alpha_composite(im, ov).convert("RGB")).copy()


# ---------------------------------------------------------------- audio
def mix(lines, total, with_voice):
    n = int(total * SR) + SR
    voice = np.zeros(n, np.float32)
    for b in BEATS:
        if b.line and with_voice:
            a = lines[b.line][0]
            i = int((b.t0 + b.pre) * SR)
            voice[i:i + len(a)] += a[: n - i]
    if with_voice:
        peak = np.percentile(np.abs(voice[voice != 0]), 99.5) if np.any(voice) else 1
        voice *= 0.5 / max(1e-6, peak)
    sect = {"groove": next(b.t0 for b in BEATS if b.id == "problem"), "tension": next(b.t0 for b in BEATS if b.id == "funnel"),
            "lift": next(b.t0 for b in BEATS if b.id == "impact"), "close": next(b.t0 for b in BEATS if b.id == "close")}
    music = sound.make_music(sect, n / SR)
    # duck the music under the voice
    env = np.abs(voice)
    win = int(0.05 * SR)
    env = np.convolve(env, np.ones(win) / win, mode="same")
    env = np.minimum(1, env / 0.06)
    att, rel = 1 - math.exp(-1 / (0.06 * SR / 64)), 1 - math.exp(-1 / (0.45 * SR / 64))
    ds = env[::64]
    sm = np.zeros_like(ds)
    y = 0.0
    for i, v in enumerate(ds):
        y += (att if v > y else rel) * (v - y)
        sm[i] = y
    duck = np.interp(np.arange(n), np.arange(len(sm)) * 64, sm)
    # music sits ~13 dB under the voice between lines and ~21 dB under it while she speaks; louder on the end card
    def rms(x):
        return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 1e-6
    v_rms = rms(voice[np.abs(voice) > 0.02]) if with_voice else 0.1
    m_rms = rms(music[int(sect["groove"] * SR):int(sect["tension"] * SR)])
    g = v_rms / max(1e-6, m_rms) * 10 ** (-13 / 20)
    cold = BEATS[0].D
    last = BEATS[-1]
    spoken_end = last.t0 + last.pre + last.L
    pts = [(0, g * 4.5), (cold, g * 4.5), (cold + 0.6, g * 1.3), (sect["groove"], g), (sect["tension"], g), (sect["lift"], g * 1.25),
           (sect["close"], g * 2.0), (spoken_end, g * 2.0), (spoken_end + 0.6, g * 2.8), (n / SR, g * 2.8)]
    level = np.interp(np.arange(n) / SR, *zip(*pts))
    if len(music) < n:
        music = np.concatenate([music, np.zeros((n - len(music), 2), np.float32)])
    gain = level * (1 - 0.6 * duck)
    out = music[:n] * gain[:, None]
    out[:, 0] += voice
    out[:, 1] += voice
    # effects
    fx = np.zeros((n, 2), np.float32)
    for b in BEATS:
        for bt in b._taps:
            sound.place(fx, sound.tap(), b.t0 + bt, 0.22)
        if b.kw.get("notify") is not None:
            sound.place(fx, sound.ding(), b.t0 + b.kw["notify"] + 0.1, 0.32)
        if b.kind == "rewind":
            sound.place(fx, sound.whoosh(b.D + 0.2, up=False), b.t0 - 0.1, 0.55)
        if b.id in ("partner", "funnel", "close"):
            sound.place(fx, sound.whoosh(0.6), b.t0 - 0.42, 0.3)
        if b.id == "impact":
            sound.place(fx, sound.riser(1.3), b.t0 - 1.3, 0.35)
    out += fx
    return out[: int(total * SR)]


def write_audio(arr, path, target=-16.0):
    """Two-pass loudness normalisation in linear mode: one gain for the whole mix, so the music stays under the voice."""
    raw = os.path.join(TMP, "mix.f32")
    open(raw, "wb").write(np.ascontiguousarray(arr, dtype=np.float32).tobytes())
    inp = ["-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", raw]
    r = subprocess.run(["ffmpeg", "-hide_banner", *inp, "-af", f"loudnorm=I={target}:TP=-1.5:LRA=20:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    af = (f"loudnorm=I={target}:TP=-1.5:LRA=20:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
    sh(["ffmpeg", "-y", "-v", "error", *inp, "-af", af, "-ar", str(SR), "-c:a", "pcm_s16le", path])


def srt(path):
    def ts(t):
        return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(t * 1000 % 1000):03d}"
    out, k = [], 1
    for b in BEATS:
        if not b.line:
            continue
        words, text = b.words, SCRIPT[b.line].split()
        # chunks of up to ~7 words, split on sentence ends
        chunk, start_i = [], 0
        for i, w_ in enumerate(text):
            chunk.append(w_)
            if len(chunk) >= 7 or w_.endswith((".", "?", ":")) or i == len(text) - 1:
                a = words[min(start_i, len(words) - 1)][0]
                e = words[min(i, len(words) - 1)][1]
                out.append(f"{k}\n{ts(b.t0 + b.pre + a)} --> {ts(b.t0 + b.pre + e + 0.15)}\n{' '.join(chunk)}\n")
                k, chunk, start_i = k + 1, [], i + 1
    open(path, "w", encoding="utf-8").write("\n".join(out))


def render(version, lines, total):
    guide = version == "guide"
    wav = os.path.join(TMP, f"{version}.wav")
    write_audio(mix(lines, total, with_voice=not guide), wav, target=-27.0 if guide else -16.0)
    out = os.path.join(OUT, f"{version}.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    nf = int(total * FPS)
    for f in range(nf):
        ff.stdin.write(frame_at(f / FPS, guide).tobytes())
        if f % 300 == 0:
            print(f"  {version}: {f / FPS:6.1f}s / {total:.1f}s", flush=True)
    ff.stdin.close()
    if ff.wait():
        raise SystemExit("ffmpeg failed")
    srt(os.path.join(OUT, f"{version}.srt"))
    return out


def main():
    global STARTS, CON, CONSOLE_LAYER
    CON = Image.open(os.path.join(REC, "console.png")).convert("RGB")
    CONSOLE_LAYER = tight(console_art())
    timing_voice = "neerja"
    for version in VERSIONS:
        lines = load_voice(timing_voice if version == "guide" else version)
        total = plan(lines)
        STARTS = [b.t0 for b in BEATS]
        for b in BEATS:
            prepare(b)
        CHUNKS[:] = make_chunks() if SUBS and version != "guide" else []
        if CHUNKS:
            with open(os.path.join(OUT, f"{version}_subtitles.srt"), "w", encoding="utf-8") as fh:
                ts = lambda t: f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(t * 1000 % 1000):03d}"
                fh.write("\n".join(f"{k + 1}\n{ts(a)} --> {ts(e)}\n{s}\n" for k, (a, e, s) in enumerate(CHUNKS)))
        print(version, f"total {total:.1f}s")
        render(version, lines, total)
        if version in ("neerja", "guide"):
            md = ["# Accel Saathi demo: voice-over timings", "",
                  f"Total {int(total // 60)}:{total % 60:04.1f}. Each line starts at the time shown; the karaoke strip in the guide video follows the same timing.",
                  "", "| Starts | Seconds | Line |", "|---|---|---|"]
            for b in BEATS:
                if b.line:
                    t = b.t0 + b.pre
                    md.append(f"| {int(t // 60)}:{t % 60:04.1f} | {b.L:.1f} | {SCRIPT[b.line]} |")
            open(os.path.join(OUT, "timings.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")


STARTS = []
if __name__ == "__main__":
    main()
