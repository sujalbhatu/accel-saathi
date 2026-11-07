"""Music bed and sound effects for the demo video, synthesised here so there is nothing to license.

make_music(sections, total) -> float32 stereo array at SR. sections: times (s) for "groove" (the story starts),
"tension" (the funnel: drums drop), "lift" (the impact numbers), "close" (the end card: one last chord).
tap(), whoosh(), ding(), riser() -> short stereo clips for the mixer.
"""
import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
BPM = 96
BEAT = 60 / BPM
BAR = 4 * BEAT
RNG = np.random.default_rng(7)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


# I - V/3 - vi - IV in C, one chord a bar: warm and forward-moving, never sad
CHORDS = [
    (48, [64, 67, 72, 74]),  # C add9
    (47, [62, 67, 71, 74]),  # G/B
    (45, [64, 69, 72, 76]),  # Am
    (41, [65, 69, 72, 79]),  # F add9
]
ARP = [0, 1, 2, 3, 2, 1, 3, 2]  # chord tones, an octave up, in eighth notes


def lowpass(x, hz, order=2):
    return sosfilt(butter(order, hz, "low", fs=SR, output="sos"), x, axis=0)


def highpass(x, hz, order=2):
    return sosfilt(butter(order, hz, "high", fs=SR, output="sos"), x, axis=0)


def env_adsr(n, a, r, sustain_n):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    e[:na] = np.linspace(0, 1, na) ** 1.6
    rel_start = min(n, sustain_n)
    if rel_start < n:
        tail = np.exp(-np.arange(n - rel_start) / (nr / 4.0))
        e[rel_start:] *= tail
    return e


def pad_note(f, dur, rel=1.6):
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for cents, pan in ((-7, 0.25), (0, 0.5), (7, 0.75)):
        ff = f * 2 ** (cents / 1200)
        ph = RNG.uniform(0, 2 * np.pi)
        w = sum(np.sin(2 * np.pi * ff * k * t + ph * k) / k ** 1.9 for k in range(1, 7))
        out[:, 0] += w * (1 - pan)
        out[:, 1] += w * pan
    return out * env_adsr(n, 0.9, rel, int(dur * SR))[:, None] / 3


def pluck(f, dur=0.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    w = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.08 * np.sin(6 * np.pi * f * t)
    e = np.minimum(1, t / 0.004) * np.exp(-t / 0.17)
    return w * e


def kick():
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    f = 44 + 80 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t / 0.16) * np.minimum(1, t / 0.002)


def hat():
    n = int(0.08 * SR)
    t = np.arange(n) / SR
    return highpass(RNG.normal(0, 1, n), 7500) * np.exp(-t / 0.018)


def bass_note(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    w = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)
    return w * np.minimum(1, t / 0.01) * np.exp(-t / 0.55)


def place(buf, clip, t, gain=1.0, pan=0.5):
    i = int(t * SR)
    if i >= len(buf):
        return
    clip = clip[: len(buf) - i]
    if clip.ndim == 1:
        buf[i:i + len(clip), 0] += clip * gain * (1 - pan) * 2 ** 0.5
        buf[i:i + len(clip), 1] += clip * gain * pan * 2 ** 0.5
    else:
        buf[i:i + len(clip)] += clip * gain


def reverb(x, seconds=2.2, wet=0.3):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = RNG.normal(0, 1, (n, 2)) * np.exp(-t / (seconds / 6.9))[:, None]
    ir = lowpass(ir, 5000)
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    w = np.stack([fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in (0, 1)], axis=1)
    return x * (1 - wet) + w * wet


def ramp(total, points):
    """Piecewise-linear automation over the timeline: points = [(t, value), ...]."""
    t = np.arange(int(total * SR)) / SR
    xs, ys = zip(*points)
    return np.interp(t, xs, ys)


def make_music(sections, total):
    groove, tension, lift, close = (sections[k] for k in ("groove", "tension", "lift", "close"))
    n = int((total + 3) * SR)
    pad, arp, bass, drums = (np.zeros((n, 2)) for _ in range(4))
    bars = int(close / BAR) + 1
    for b in range(bars):
        t0 = b * BAR
        root, tones = CHORDS[b % 4]
        for m in tones:
            place(pad, pad_note(midi(m), BAR), t0, 0.16)
        if t0 >= groove - BAR:
            for i, step in enumerate(ARP):
                ti = t0 + i * BEAT / 2
                if groove - 0.05 <= ti < close:
                    place(arp, pluck(midi(tones[step] + 12)), ti, 0.11, 0.3 if i % 2 else 0.7)
            for ti, d in ((t0, 1.5 * BEAT), (t0 + 1.5 * BEAT, BEAT), (t0 + 2.5 * BEAT, 1.5 * BEAT)):
                if groove <= ti < close:
                    place(bass, bass_note(midi(root - 12), d + 0.3), ti, 0.42)
            for beat in range(4):
                ti = t0 + beat * BEAT
                if groove <= ti < close and not tension <= ti < lift:
                    if beat in (0, 2):
                        place(drums, kick(), ti, 0.5)
                    place(drums, hat(), ti + BEAT / 2, 0.06, 0.62)
    # the end: one long C add9, ringing out
    hold = max(2.4, total - close - 2.2)  # the last chord rings under the end card until the fade
    for m in (36, 48, 55, 64, 67, 74, 76):
        place(pad, pad_note(midi(m), hold, rel=2.5), close, 0.15)
    place(arp, pluck(midi(84), 1.5), close, 0.14, 0.5)
    place(arp, pluck(midi(91), 1.5), close + BEAT / 2, 0.08, 0.6)

    pad = lowpass(pad, 2400)
    # the pad opens up as the story gets going, and darkens for the funnel
    bright = ramp(n / SR, [(0, 0.55), (groove, 0.8), (tension, 0.8), (tension + 1, 0.6), (lift, 0.85), (n / SR, 0.85)])
    pad *= bright[:, None]
    bass = lowpass(bass, 380)
    # a ping-pong delay keeps the arpeggio airy
    d = int(0.75 * BEAT * SR)
    echo = np.zeros_like(arp)
    echo[d:, 0] = arp[:-d, 1] * 0.32
    echo[2 * d:, 1] = arp[:-2 * d, 0] * 0.18
    arp = arp + echo
    bus = reverb(pad + arp, wet=0.32) + bass + drums
    level = ramp(n / SR, [(0, 0.25), (0.4, 0.7), (groove, 0.75), (tension, 0.75), (tension + 0.8, 0.6),
                          (lift, 0.9), (close, 1.0), (n / SR - 1.5, 0.9), (n / SR, 0.0)])
    bus *= level[:, None]
    bus = np.tanh(bus * 1.2) / 1.2
    bus /= max(1e-9, np.abs(bus).max()) / 0.9
    return bus[: int(total * SR)].astype(np.float32)


# ---------- effects ----------
def tap():
    n = int(0.05 * SR)
    t = np.arange(n) / SR
    click = highpass(RNG.normal(0, 1, n), 2500) * np.exp(-t / 0.004) * 0.5
    tone = np.sin(2 * np.pi * 1900 * t) * np.exp(-t / 0.012) * 0.35
    return (click + tone).astype(np.float32)


def whoosh(dur=0.7, up=True):
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = RNG.normal(0, 1, n)
    cut = np.geomspace(300, 4500, n) if up else np.geomspace(4500, 300, n)
    out, y = np.zeros(n), 0.0
    a = 1 - np.exp(-2 * np.pi * cut / SR)
    for i in range(n):  # a one-pole filter whose cutoff sweeps
        y += a[i] * (noise[i] - y)
        out[i] = y
    e = np.sin(np.pi * np.minimum(1, t / dur)) ** 2
    st = np.stack([out * e * np.linspace(0.7, 0.3, n), out * e * np.linspace(0.3, 0.7, n)], axis=1)
    return (st / np.abs(st).max() * 0.5).astype(np.float32)


def ding():
    out = np.zeros(int(0.9 * SR))
    for f, at in ((1318.5, 0.0), (1975.5, 0.11)):
        n = len(out) - int(at * SR)
        t = np.arange(n) / SR
        w = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2.76 * f * t) * np.exp(-t / 0.05)) * np.exp(-t / 0.22)
        out[int(at * SR):] += w * np.minimum(1, t / 0.002)
    return (out / np.abs(out).max() * 0.6).astype(np.float32)


def riser(dur=1.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = highpass(RNG.normal(0, 1, (n, 2)), 1800)
    x *= ((t / dur) ** 2.2)[:, None]
    x[-int(0.03 * SR):] *= np.linspace(1, 0, int(0.03 * SR))[:, None]
    return (x / np.abs(x).max() * 0.35).astype(np.float32)
