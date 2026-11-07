"""Cuts one continuous voice-over take (read along with the guide video) into the 17 script lines, so
make_video2.py can use it like the AI voices: <voice dir>/<name>/<line>.mp3 + <line>.json (word timings).

    python cut_take.py <take.mp3> <voice dir> <name> --cues cues.json [--offset S] [--words transcript.json]
                       [--line v15_impact=retake.mp3 ...] [--mark v15_impact:twice=7.84,8.22 ...]

--offset: seconds the take started after the guide video (found by matching each line's first word to its cue).
--words:  Whisper verbose_json with word timestamps, in take time. Without it the words of each line are spread
          over its voiced stretches by length, which is close enough for the impact counters and the zooms.
--line:   a re-recorded line, as its own file, replacing that line from the take.
--mark:   a measured word time in a re-recorded line, for the words the video cues on."""
import argparse
import json
import os
import re
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 24000


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def voiced(audio, gap=0.15, thr_over_floor=12.0):
    """Voiced stretches [(s, e)] by short-time energy above the noise floor."""
    hop = int(0.02 * SR)
    n = len(audio) // hop
    fr = audio[: n * hop].reshape(n, hop)
    db = 20 * np.log10(np.sqrt(np.mean(fr ** 2, axis=1)) + 1e-9)
    thr = np.percentile(db, 10) + thr_over_floor
    on = db > thr
    segs, i = [], 0
    while i < n:
        if on[i]:
            j = i
            while j < n and on[j]:
                j += 1
            segs.append([i * 0.02, j * 0.02])
            i = j
        else:
            i += 1
    out = []
    for s in segs:
        if out and s[0] - out[-1][1] < gap:
            out[-1][1] = s[1]
        else:
            out.append(s)
    return [s for s in out if s[1] - s[0] > 0.08]


def spread(words, segs):
    """Gives each script word a slice of the voiced time, by its length."""
    total = sum(e - s for s, e in segs)
    weights = [len(w) + 1 for w in words]
    per = total / sum(weights)
    out, k, used = [], 0, 0.0
    t_on = [(s, e) for s, e in segs]
    pos = 0.0  # voiced seconds consumed

    def at(v):
        acc = 0.0
        for s, e in t_on:
            if acc + (e - s) >= v:
                return s + (v - acc)
            acc += e - s
        return t_on[-1][1]
    for w, wt in zip(words, weights):
        a, b = at(pos), at(pos + wt * per - 0.02)
        out.append([round(a, 3), round(max(a + 0.05, b), 3), w])
        pos += wt * per
    return out


ap = argparse.ArgumentParser()
ap.add_argument("take")
ap.add_argument("voice")
ap.add_argument("name")
ap.add_argument("--cues", required=True, help="json [[line id, start s], ...] from the guide timings")
ap.add_argument("--offset", type=float, default=0.0)
ap.add_argument("--words", default=None)
ap.add_argument("--line", action="append", default=[])
ap.add_argument("--mark", action="append", default=[],
                help="line:word=start,end in that line's own file (word@last for the last one), e.g. v15_impact:half@last=9.46,9.68")
a = ap.parse_args()

script = {s["id"]: s["text"] for s in json.load(open(os.path.join(HERE, "script_v2.json"), encoding="utf-8"))}
cues = json.load(open(a.cues))
audio = decode(a.take)
segs = voiced(audio)
tw = None
if a.words:
    j = json.load(open(a.words, encoding="utf-8"))
    tw = [[w["start"], w["end"], w["word"].strip()] for w in j.get("words", [])]
retakes = dict(x.split("=", 1) for x in a.line)
out = os.path.join(a.voice, a.name)
os.makedirs(out, exist_ok=True)
report = []
for i, (lid, cue) in enumerate(cues):
    lo = cue - a.offset - 0.6
    hi = (cues[i + 1][1] - a.offset - 0.6) if i + 1 < len(cues) else len(audio) / SR
    src, base = audio, 0.0
    if lid in retakes:
        src = decode(retakes[lid])
        mine = voiced(src)
    else:
        mine = [s for s in segs if lo <= s[0] < hi]
    if not mine:
        report.append((lid, "no speech found"))
        continue
    s0, s1 = max(0.0, mine[0][0] - 0.15), min(len(src) / SR, mine[-1][1] + 0.25)
    clip = src[int(s0 * SR):int(s1 * SR)]
    # level-match lines from different takes: the voiced part of every line at the same loudness
    vo = np.concatenate([src[int(s * SR):int(e * SR)] for s, e in mine])
    gain = 10 ** ((-20.0 - 20 * np.log10(np.sqrt(np.mean(vo ** 2)) + 1e-9)) / 20)
    clip = clip * min(gain, 0.98 / max(1e-6, np.abs(clip).max()))
    words = re.findall(r"[\w'’₹,.-]+", script[lid])
    if tw is not None and lid not in retakes:
        ws = [[round(s - s0, 3), round(e - s0, 3), w] for s, e, w in tw if s0 <= s < s1]
    else:
        ws = spread(words, [(s - s0, e - s0) for s, e in mine])
    for m in a.mark:  # pin the words the video cues on (the impact counters) to measured times
        key, t = m.split("=", 1)
        ml, mw = key.split(":", 1)
        if ml != lid:
            continue
        last = mw.endswith("@last")
        mw = mw.replace("@last", "").lower()
        hits = [k for k, w in enumerate(ws) if w[2].lower().strip(".,:;") == mw]
        if hits:
            ts, te = (float(v) for v in t.split(","))
            ws[hits[-1] if last else hits[0]][:2] = [round(ts - s0, 3), round(te - s0, 3)]
    wav = os.path.join(out, lid + ".wav")
    import wave
    with wave.open(wav, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes((np.clip(clip, -1, 1) * 32767).astype(np.int16).tobytes())
    # a gentle clean-up: rumble off, light de-noise, even level
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-af",
                    "highpass=f=80,afftdn=nf=-45,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120",
                    "-b:a", "192k", os.path.join(out, lid + ".mp3")], check=True)
    os.remove(wav)
    json.dump(ws, open(os.path.join(out, lid + ".json"), "w"))
    report.append((lid, f"{s1 - s0:5.1f} s, {len(ws)} words"))
for r in report:
    print(*r)
