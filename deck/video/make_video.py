"""Builds the 3-minute demo video from the screen recordings, the narration and (optionally) voice files.

    python3 make_video.py <rec dir> <out dir> [voice dir with neerja/ prabhat/ ...]

<rec dir> holds priya.webm, hindi.webm and marks.json from record.js (recorded at 390 x 844 CSS pixels, top-left).
Writes <out>/<version>.mp4 for each voice found plus "captions_only.mp4", and <out>/voiceover_script.md (timed).
"""
import json
import math
import os
import subprocess
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REC, OUT = sys.argv[1], sys.argv[2]
VOICE = sys.argv[3] if len(sys.argv) > 3 else None
IMG = os.path.join(HERE, "..", "source", "img")
W, H, FPS = 1920, 1080, 30
F = "/usr/share/fonts/opentype/inter/Inter-{}.otf"
RED, WHITE, GREY, DIM = (229, 57, 53), (255, 255, 255), (184, 188, 198), (120, 124, 134)
os.makedirs(OUT, exist_ok=True)
TMP = os.path.join(OUT, "tmp")
os.makedirs(TMP, exist_ok=True)


def font(weight, size):
    return ImageFont.truetype(F.format(weight), size)


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(" ".join(cmd) + "\n" + r.stderr[-3000:])
    return r.stdout


def duration(path):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).strip())


SCRIPT = {s["id"]: s["text"] for s in json.load(open(os.path.join(HERE, "script.json"), encoding="utf-8"))}
MARKS = json.load(open(os.path.join(REC, "marks.json")))
VOICES = sorted(d for d in os.listdir(VOICE) if os.path.isdir(os.path.join(VOICE, d))) if VOICE else []

# scene: (id, kind, source, label, headline, subline)
P = "priya"
SCENES = [
    ("s01_hook", "hook", None, "", "", ""),
    ("s02_intro", "intro", None, "", "", ""),
    ("s03_gstin", "app", (P, "gstin", "pains"), "STEP 1 OF 6 · ONE MESSAGE", "One line.\nProfile filled.", "Her GSTIN is looked up in the GST registry, and she confirms it is her shop."),
    ("s04_pains", "app", (P, "pains", "why"), "STEP 2 OF 6 · IT ASKS, LIKE A SALESPERSON", "It asks about her shop, not product codes.", "Every problem she taps ticks the service that fixes it."),
    ("s05_why", "app", (P, "why", "objection"), "STEP 3 OF 6 · ONE PRICE, WITH REASONS", "Her bundle, explained in her words.", "Ranked from 368 real Accel customers. Every ₹ comes from the catalogue."),
    ("s06_objection", "app", (P, "objection", "kyc"), "STEP 4 OF 6 · \"TOO EXPENSIVE?\"", "Choices with prices.\nNever a silent cut.", "A lighter bundle, 24 months or her own budget. She decides."),
    ("s07_kyc", "app", (P, "kyc", "tracker"), "STEP 5 OF 6 · KYC IN ABOUT 2 MINUTES", "No paper.\nNo office visit.", "One consent switch per purpose · DigiLocker · Aadhaar OTP · registry checks."),
    ("s08_tracker", "app", (P, "tracker", "end"), "STEP 6 OF 6 · LIVE IN ABOUT 5 DAYS", "A tracker,\nnot phone calls.", "She books the install slot. Every stage reaches her on WhatsApp. One bill, one number."),
    ("s09_lang", "app", ("hindi", "start", "end"), "10 INDIAN LANGUAGES", "The same advisor, in her language.", "English, Hindi and 8 more, typed or spoken, in the app and on WhatsApp."),
    ("s10_partner", "partner", None, "", "", ""),
    ("s11_tech", "tech", None, "", "", ""),
    ("s12_close", "close", None, "", "", ""),
]
APP_STEPS = [s[0] for s in SCENES if s[1] == "app"][:6]


def scene_len(sid):
    """Narration length (longest voice), or an estimate from the words; plus breathing room."""
    lens = [duration(os.path.join(VOICE, v, sid + ".mp3")) for v in VOICES if os.path.exists(os.path.join(VOICE, v, sid + ".mp3"))]
    n = max(lens) if lens else len(SCRIPT[sid].split()) / 2.45
    return round(n + 0.6, 2), n


# ---------- frames ----------
def base():
    im = Image.new("RGB", (W, H), (18, 18, 24))
    d = ImageDraw.Draw(im)
    for y in range(H):  # soft vertical gradient
        c = int(18 + 10 * y / H)
        d.line([(0, y), (W, y)], fill=(c, c, c + 7))
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((1250, -420, 2350, 560), fill=120)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    im = Image.composite(Image.new("RGB", (W, H), (120, 20, 24)), im, glow)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((W - 330, 44, W - 286, 88), 10, fill=RED)
    d.text((W - 308, 66), "A", font=font("Bold", 28), fill=WHITE, anchor="mm")
    d.text((W - 274, 66), "Accel Saathi", font=font("SemiBold", 26), fill=WHITE, anchor="lm")
    return im


def wrap(d, text, fnt, width):
    out = []
    for para in text.split("\n"):
        line = ""
        for w in para.split():
            t = (line + " " + w).strip()
            if d.textlength(t, font=fnt) <= width:
                line = t
            else:
                out.append(line)
                line = w
        out.append(line)
    return out


def block(d, x, y, lines, fnt, fill, gap):
    for ln in lines:
        d.text((x, y), ln, font=fnt, fill=fill)
        y += gap
    return y


PHONE = (262, 86, 420, 909)  # x, y, w, h of the screen


def app_frame(sid, label, head, sub):
    im = base()
    d = ImageDraw.Draw(im)
    x, y, w, h = PHONE
    d.rounded_rectangle((x - 14, y - 14, x + w + 14, y + h + 14), 62, fill=(8, 8, 12), outline=(60, 60, 70), width=2)
    # steps
    if sid in APP_STEPS:
        i = APP_STEPS.index(sid)
        for k in range(6):
            d.rounded_rectangle((820 + k * 74, 250, 820 + k * 74 + 60, 258), 4, fill=RED if k <= i else (70, 72, 82))
    d.text((820, 290), label, font=font("Bold", 24), fill=RED)
    yy = block(d, 820, 336, wrap(d, head, font("Bold", 66), 960), font("Bold", 66), WHITE, 80)
    block(d, 820, yy + 24, wrap(d, sub, font("Regular", 32), 940), font("Regular", 32), GREY, 46)
    p = os.path.join(TMP, sid + "_bg.png")
    im.save(p)
    return p


def mask():
    m = Image.new("L", (PHONE[2], PHONE[3]), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, PHONE[2] - 1, PHONE[3] - 1), 48, fill=255)
    p = os.path.join(TMP, "mask.png")
    m.save(p)
    return p


def frame_hook():
    im = base()
    d = ImageDraw.Draw(im)
    d.text((160, 200), "ACCEL'S SMALL-BUSINESS FUNNEL TODAY · APR–JUN 2026", font=font("Bold", 26), fill=RED)
    stats = [("7.4%", "of 5,000 leads go live"), ("17.6 days", "from lead to live"), ("3 calls", "chasing status, per customer")]
    for i, (n, t) in enumerate(stats):
        x = 160 + i * 560
        d.rounded_rectangle((x, 300, x + 500, 640), 28, fill=(32, 32, 40), outline=(64, 64, 76), width=2)
        d.text((x + 40, 370), n, font=font("Bold", 92), fill=WHITE)
        d.text((x + 44, 520), t, font=font("Regular", 30), fill=GREY)
    d.text((160, 760), "₹35.6 lakh of ₹55.4 lakh spent on leads that were never won.", font=font("SemiBold", 40), fill=WHITE)
    d.text((160, 830), "Leads are lost to the journey, not to demand.", font=font("Regular", 36), fill=GREY)
    p = os.path.join(TMP, "s01_hook_bg.png")
    im.save(p)
    return p


def frame_intro(phone_still):
    im = base()
    d = ImageDraw.Draw(im)
    x, y, w, h = PHONE
    d.rounded_rectangle((x - 14, y - 14, x + w + 14, y + h + 14), 62, fill=(8, 8, 12), outline=(60, 60, 70), width=2)
    shot = Image.open(phone_still).convert("RGB").crop((0, 0, 390, 844)).resize((w, h), Image.LANCZOS)
    m = Image.open(mask())
    im.paste(shot, (x, y), m)
    d.text((820, 300), "PROJECT UDYAM DIGITAL · TEAM TOURISTGUIDE, NIT JAMSHEDPUR", font=font("Bold", 24), fill=RED)
    d.text((820, 350), "Accel Saathi", font=font("Bold", 110), fill=WHITE)
    block(d, 820, 500, wrap(d, "A small business gets online in one conversation: on the phone, in its own language.", font("Regular", 40), 960),
          font("Regular", 40), GREY, 56)
    chips = ["GenAI advisor", "Instant quote", "Smart KYC", "Tracker on WhatsApp", "10 languages"]
    cx = 820
    for c in chips:
        tw = d.textlength(c, font=font("SemiBold", 28))
        d.rounded_rectangle((cx, 680, cx + tw + 44, 736), 28, outline=RED, width=2)
        d.text((cx + 22, 708), c, font=font("SemiBold", 28), fill=WHITE, anchor="lm")
        cx += tw + 64
        if cx > 1700:
            break
    p = os.path.join(TMP, "s02_intro_bg.png")
    im.save(p)
    return p


def frame_partner():
    im = base()
    d = ImageDraw.Draw(im)
    d.text((120, 120), "PARTNERS AND FIELD FORCE", font=font("Bold", 26), fill=RED)
    d.text((120, 160), "Partners sell more, not less.", font=font("Bold", 64), fill=WHITE)
    y = 290
    for f in ("con_assist.png", "con_sales.png"):
        shot = Image.open(os.path.join(IMG, f)).convert("RGB")
        sw = 1080
        shot = shot.resize((sw, int(shot.height * sw / shot.width)), Image.LANCZOS)
        d.rounded_rectangle((116, y - 4, 120 + sw + 4, y + shot.height + 4), 14, fill=(60, 60, 70))
        im.paste(shot, (120, y))
        y += shot.height + 30
    pts = [("Assisted mode", "A partner starts the chat; a QR hands it to the owner's phone."),
           ("Owner consents herself", "A code to her own phone. A partner can never consent for her."),
           ("Sale protected 30 days", "Commission: half when live, half after 6 months, if she stays.")]
    for i, (h, t) in enumerate(pts):
        yy = 300 + i * 200
        d.rounded_rectangle((1270, yy, 1800, yy + 170), 22, fill=(32, 32, 40))
        d.text((1300, yy + 28), h, font=font("Bold", 34), fill=WHITE)
        block(d, 1300, yy + 78, wrap(d, t, font("Regular", 27), 470), font("Regular", 27), GREY, 36)
    p = os.path.join(TMP, "s10_partner_bg.png")
    im.save(p)
    return p


def frame_tech():
    im = base()
    d = ImageDraw.Draw(im)
    d.text((160, 150), "UNDER THE HOOD", font=font("Bold", 26), fill=RED)
    d.text((160, 190), "The AI understands. The rules decide.", font=font("Bold", 64), fill=WHITE)
    flow = ["Understand", "Check", "Rank", "Level"]
    subs = ["her words → facts", "25 services, catalogue rules", "368 real customers", "Basic · Recommended · Complete"]
    for i, (f, s) in enumerate(zip(flow, subs)):
        x = 160 + i * 410
        d.rounded_rectangle((x, 320, x + 370, 470), 22, fill=(40, 20, 24) if i == 2 else (32, 32, 40), outline=RED if i == 2 else (64, 64, 76), width=2)
        d.text((x + 30, 350), f"{i + 1}  {f}", font=font("Bold", 38), fill=WHITE)
        d.text((x + 30, 412), s, font=font("Regular", 26), fill=GREY)
        if i:
            d.text((x - 32, 395), "→", font=font("Bold", 40), fill=DIM, anchor="mm")
    tiles = [("63%", "of pre-ticked services were bought, in a back-test (one bundle for all: 37%)"),
             ("0", "invented prices: any ₹ not in the quote is dropped"),
             ("AES-256", "every record encrypted at source; the AI sees tokens, not names"),
             ("91/91", "advisor checks pass, with the AI on and off; 106 more for KYC, WhatsApp, partners")]
    for i, (n, t) in enumerate(tiles):
        x = 160 + i * 410
        d.rounded_rectangle((x, 540, x + 370, 860), 22, fill=(32, 32, 40))
        d.text((x + 30, 570), n, font=font("Bold", 72), fill=RED)
        block(d, x + 30, 690, wrap(d, t, font("Regular", 28), 310), font("Regular", 28), GREY, 38)
    p = os.path.join(TMP, "s11_tech_bg.png")
    im.save(p)
    return p


def frame_close():
    im = base()
    d = ImageDraw.Draw(im)
    d.text((160, 170), "SAME LEADS, EVERY QUARTER (MODELLED)", font=font("Bold", 26), fill=RED)
    for i, (n, t) in enumerate([("368 → 764", "activations"), ("₹15,053 → ₹7,251", "cost per activation"), ("17.6 → ≤ 7", "days to go live")]):
        x = 160 + i * 560
        d.text((x, 220), n, font=font("Bold", 62), fill=WHITE)
        d.text((x, 300), t, font=font("Regular", 32), fill=GREY)
    d.line((160, 400, 1760, 400), fill=(64, 64, 76), width=2)
    d.text((160, 470), "Accel Saathi", font=font("Bold", 120), fill=WHITE)
    d.text((166, 630), "Try it live:  udyam.openforge.online", font=font("SemiBold", 48), fill=RED)
    d.text((166, 720), "Team TouristGuide · NIT Jamshedpur · Airtel Sync 2026", font=font("Regular", 34), fill=GREY)
    qr = Image.open(os.path.join(IMG, "qr_app.png")).convert("RGB").resize((300, 300), Image.NEAREST)
    d.rounded_rectangle((1440, 450, 1780, 790), 24, fill=WHITE)
    im.paste(qr, (1460, 470))
    p = os.path.join(TMP, "s12_close_bg.png")
    im.save(p)
    return p


# ---------- clips ----------
def clip(sid, kind, src, label, head, sub, D):
    out = os.path.join(TMP, sid + ".mp4")
    fade = f"fade=t=in:st=0:d=0.35,fade=t=out:st={D - 0.35:.2f}:d=0.35"
    enc = ["-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-an", out]
    if kind == "app":
        name, a, b = src
        start, end = MARKS[f"{name}:{a}"], MARKS[f"{name}:{b}"]
        L = end - start
        speed = max(1.0, min(2.2, L / (D - 0.4)))
        hold = max(0.0, D - L / speed) + 0.5
        bg = app_frame(sid, label, head, sub)
        x, y, w, h = PHONE
        fc = (f"[1:v]trim=start={start:.2f}:end={end:.2f},setpts=(PTS-STARTPTS)/{speed:.3f},fps={FPS},crop=390:844:0:0,"
              f"scale={w}:{h}:flags=lanczos,tpad=stop_mode=clone:stop_duration={hold:.2f},format=rgba[ph];"
              f"[ph][2:v]alphamerge[phm];[0:v][phm]overlay={x}:{y}:shortest=0,trim=duration={D:.2f},{fade}[v]")
        sh(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", bg, "-i", os.path.join(REC, name + ".webm"),
            "-loop", "1", "-i", mask(), "-filter_complex", fc, "-map", "[v]", "-t", f"{D:.2f}", *enc])
        return out, speed
    bg = {"hook": frame_hook, "partner": frame_partner, "tech": frame_tech, "close": frame_close}.get(kind)
    bg = bg() if bg else frame_intro(os.path.join(TMP, "welcome.png"))
    zoom = f"scale=2112:1188,zoompan=z='1+0.04*on/({D * FPS:.0f})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(D * FPS)}:s={W}x{H}:fps={FPS}"
    sh(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", bg, "-vf", f"{zoom},{fade}", "-t", f"{D:.2f}", *enc])
    return out, 1.0


SPOKEN = [(" dot ", "."), ("three hundred and sixty-eight", "368"), ("Ninety-one", "91"), ("twenty-four", "24"), ("five thousand", "5,000"),
          ("seven in a hundred", "7 in 100"), ("seventeen days", "17 days"), ("about two minutes", "about 2 minutes"), ("about five days", "about 5 days")]


def written(text):
    """Captions show numbers and the web address as they are written, not as they are spoken."""
    for a, b in SPOKEN:
        text = text.replace(a, b)
    return text


def ass_time(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def captions(plan):
    """Short caption lines timed across each scene's narration, in the right panel for app scenes."""
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV\n"
            "Style: Side,Inter,34,&H00FFFFFF,&H00000000,&H90000000,0,3,14,0,1,820,140,90\n"
            "Style: Wide,Inter,34,&H00FFFFFF,&H00000000,&H90000000,0,3,14,0,2,200,200,48\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Text\n")
    ev = []
    for sid, kind, t0, D, n in plan:
        words = written(SCRIPT[sid]).split()
        chunks, cur = [], []
        for w_ in words:
            cur.append(w_)
            if len(" ".join(cur)) > 48 or w_.endswith((".", "?", ":")) and len(cur) > 3:
                chunks.append(" ".join(cur))
                cur = []
        if cur:
            chunks.append(" ".join(cur))
        total = sum(len(c) for c in chunks)
        t = t0 + 0.2
        for c in chunks:
            dt = n * len(c) / total
            ev.append(f"Dialogue: 0,{ass_time(t)},{ass_time(t + dt)},{'Side' if kind == 'app' else 'Wide'},{c}")
            t += dt
    p = os.path.join(TMP, "captions.ass")
    open(p, "w", encoding="utf-8").write(head + "\n".join(ev) + "\n")
    return p


def main():
    sh(["ffmpeg", "-y", "-v", "error", "-ss", "0.8", "-i", os.path.join(REC, "priya.webm"), "-frames:v", "1", os.path.join(TMP, "welcome.png")])
    plan, files, t = [], [], 0.0
    for sid, kind, src, label, head, sub in SCENES:
        D, n = scene_len(sid)
        f, speed = clip(sid, kind, src, label, head, sub, D)
        plan.append((sid, kind, t, D, n))
        files.append(f)
        print(f"{sid:14s} {t:6.1f}s  +{D:4.1f}s  speed {speed:.2f}")
        t += D
    lst = os.path.join(TMP, "list.txt")
    open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
    silent = os.path.join(TMP, "silent.mp4")
    sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent])
    ass = captions(plan)
    capt = os.path.join(TMP, "captioned.mp4")
    sh(["ffmpeg", "-y", "-v", "error", "-i", silent, "-vf", f"ass={ass}:fontsdir=/usr/share/fonts/opentype/inter", "-c:v", "libx264",
        "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", capt])
    total = t
    # captions only (for Sujal's own voice), with a silent audio track so every player accepts it
    sh(["ffmpeg", "-y", "-v", "error", "-i", capt, "-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=r=48000:cl=stereo",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", os.path.join(OUT, "captions_only.mp4")])
    for v in VOICES:
        ins, fl = [], []
        for i, (sid, kind, t0, D, n) in enumerate(plan):
            mp3 = os.path.join(VOICE, v, sid + ".mp3")
            if not os.path.exists(mp3):
                continue
            ins += ["-i", mp3]
            fl.append(f"[{len(fl) + 1}:a]adelay={int((t0 + 0.2) * 1000)}|{int((t0 + 0.2) * 1000)},aresample=48000[a{len(fl)}]")
        mix = ";".join(fl) + ";" + "".join(f"[a{i}]" for i in range(len(fl))) + f"amix=inputs={len(fl)}:normalize=0,loudnorm=I=-16:TP=-1.5[a]"
        sh(["ffmpeg", "-y", "-v", "error", "-i", capt, *ins, "-filter_complex", mix, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", "-movflags", "+faststart", os.path.join(OUT, f"ai_voice_{v}.mp4")])
    # teleprompter
    md = ["# Voice-over script, timed to the video", "",
          f"Total {int(total // 60)}:{int(total % 60):02d}. Start speaking at each time shown; the captions in captions_only.mp4 show the same words.",
          "", "| Starts at | Seconds | Say |", "|---|---|---|"]
    for sid, kind, t0, D, n in plan:
        md.append(f"| {int(t0 // 60)}:{t0 % 60:04.1f} | {n:.0f} | {SCRIPT[sid]} |")
    open(os.path.join(OUT, "voiceover_script.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("total", round(total, 1), "s")


main()
