"""Document OCR that runs offline on CPU (RapidOCR / PaddleOCR models, ONNX runtime).

Two passes, tuned on the specimen KYC pack:
1. Find text boxes on a cleaned copy (the red "SPECIMEN" watermark and background removed).
2. Re-read boxes that hold numbers from the original greyscale image at 2x scale. Binarising thins
   digits enough to turn 9 into 3 or 8 into 3, so both readings are kept ("text" and "alt") and the
   field parsers pick the one that passes the identifier's own format and checksum.
Box centres are de-rotated using the median text angle, so tilted phone photos still pair labels
with values.
"""
import math

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = RapidOCR()
    return _engine


def clean_image(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    b, g, r = cv2.split(img.astype(int))
    out = np.full(gray.shape, 255, np.uint8)
    out[(gray < 140) & ((r - (g + b) / 2) < 40)] = 0
    return out


def sharpness(img: np.ndarray) -> float:
    """Variance of the Laplacian: low values mean a blurred photo."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    scale = 1000 / max(h, w)
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


MAX_SIDE = 2000  # a phone photo is ~4000 px; text on an A4 page stays readable at 2000, and detection is 4x faster


def decode(image_bytes: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not an image")
    h, w = img.shape[:2]
    if max(h, w) > MAX_SIDE:
        f = MAX_SIDE / max(h, w)
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    return img


def _recognise(engine, crop: np.ndarray) -> str:
    """Read one cropped line. Calls the recogniser alone (no text detection on the crop) when this RapidOCR
    version exposes it, which makes the second pass about 3x cheaper."""
    rec = getattr(engine, "text_recognizer", None) or getattr(engine, "text_rec", None)  # 1.2 / 1.3+ naming
    if rec is not None:
        try:
            res = rec([cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)])
            res = res[0] if isinstance(res, tuple) else res
            return " ".join(r[0] for r in res if r and r[0]).strip()
        except Exception:  # noqa: BLE001 - an API change falls back to the full pipeline below
            pass
    out, _ = engine(cv2.copyMakeBorder(crop, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=255))
    return " ".join(r[1] for r in sorted(out, key=lambda r: min(p[0] for p in r[0]))).strip() if out else ""


def read_boxes(img: np.ndarray) -> list[dict]:
    """Return [{text, conf, x, y, h}] with x/y the de-rotated box centre, in reading order."""
    engine = _get_engine()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    det, _ = engine(clean_image(img))
    if not det:
        return []
    boxes, angles = [], []
    for box, text, conf in det:
        pts = np.array(box, dtype=np.float32)
        (x0, y0), (x1, y1) = pts.min(0), pts.max(0)
        width = np.linalg.norm(pts[1] - pts[0])
        if width > 80:
            angles.append(math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0]))
        crop = gray[max(0, int(y0) - 6):int(y1) + 6, max(0, int(x0) - 6):int(x1) + 6]
        alt = ""
        if crop.size and sum(ch.isdigit() for ch in text) >= 4:  # identifiers and dates only
            alt = _recognise(engine, cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC))
        boxes.append({"text": text.strip(), "alt": alt, "conf": float(conf), "cx": float(pts[:, 0].mean()),
                      "cy": float(pts[:, 1].mean()), "h": float(y1 - y0)})
    theta = float(np.median(angles)) if angles else 0.0
    cos, sin = math.cos(-theta), math.sin(-theta)
    for b in boxes:
        b["x"] = b["cx"] * cos - b["cy"] * sin
        b["y"] = b["cx"] * sin + b["cy"] * cos
    boxes.sort(key=lambda b: (round(b["y"] / 12), b["x"]))
    return boxes
