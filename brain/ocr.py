"""Find Japanese text in an image.

Every detector returns the same thing: a list of
  {"text": str, "box": [x, y, w, h]}   # pixels, origin top-left; text may be "" (Claude reads the crop)

Detectors:
- AppleVisionOCR: built into macOS, free, offline. Reads horizontal text well, can't read vertical.
- MangaBlockDetector: comic-text-detector model (brain/models/comictextdetector.pt.onnx) via OpenCV.
  Finds whole text blocks / speech bubbles in any direction, but doesn't read them.
- HybridOCR (default): manga blocks + Apple Vision lines. Blocks where Apple Vision reads only
  non-Japanese text (browser bars, English UI) are dropped; Japanese lines outside any block are kept.
Add others (Windows.Media.Ocr, RapidOCR …) by implementing detect().
"""
import io
import re
import threading
from pathlib import Path

# real kana / kanji (not ・ ー ゛ ゜ or halfwidth voicing marks)
JAPANESE = re.compile(r"[ぁ-ゖァ-ヺ㐀-䶿一-鿿ｦ-ﾝ]")
LETTERS = re.compile(r"[A-Za-zЀ-ӿ]")
MODEL = Path(__file__).with_name("models") / "comictextdetector.pt.onnx"


class AppleVisionOCR:
    name = "apple-vision"

    def detect(self, image_bytes, japanese_only=True):
        import Vision
        from Foundation import NSData
        from Quartz import CGImageGetHeight, CGImageGetWidth, CGImageSourceCreateImageAtIndex, \
            CGImageSourceCreateWithData

        data = NSData.dataWithBytes_length_(image_bytes, len(image_bytes))
        cg = CGImageSourceCreateImageAtIndex(CGImageSourceCreateWithData(data, None), 0, None)
        if cg is None:
            raise ValueError("not an image")
        W, H = CGImageGetWidth(cg), CGImageGetHeight(cg)

        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        req.setRecognitionLanguages_(["ja-JP", "en-US"])
        req.setUsesLanguageCorrection_(True)
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None)
        ok, err = handler.performRequests_error_([req], None)
        if not ok:
            raise RuntimeError(str(err))

        lines = []
        for obs in req.results() or []:
            cands = obs.topCandidates_(1)
            if not cands:
                continue
            text, conf = str(cands[0].string()), float(cands[0].confidence())
            n = len(JAPANESE.findall(text))
            ja = n >= 2 or (n == 1 and conf >= 0.5)  # Vision scores real Japanese low (~0.3)
            if japanese_only and not ja:
                continue
            b = obs.boundingBox()  # normalized, origin bottom-left
            x, y = b.origin.x * W, (1 - b.origin.y - b.size.height) * H
            lines.append({"text": text, "ja": ja, "conf": conf,
                          "box": [round(x), round(y), round(b.size.width * W), round(b.size.height * H)]})
        lines.sort(key=lambda l: (l["box"][1], l["box"][0]))
        return lines


class MangaBlockDetector:
    name = "comic-text-detector"
    SIZE = 1024

    def __init__(self, model=MODEL, conf=0.4, nms=0.35):
        self.model, self.conf, self.nms = model, conf, nms
        self._net = None
        self._lock = threading.Lock()  # OpenCV nets aren't thread-safe

    def detect(self, image_bytes):
        import cv2
        import numpy as np
        from PIL import Image

        img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
        H, W = img.shape[:2]
        r = self.SIZE / max(H, W)
        canvas = np.zeros((self.SIZE, self.SIZE, 3), np.uint8)
        canvas[:round(H * r), :round(W * r)] = cv2.resize(img, (round(W * r), round(H * r)),
                                                          interpolation=cv2.INTER_AREA)
        with self._lock:
            if self._net is None:
                self._net = cv2.dnn.readNetFromONNX(str(self.model))
            self._net.setInput(cv2.dnn.blobFromImage(canvas, 1 / 255.0))
            (blk,) = self._net.forward(["blk"])
        b = blk[0]
        score = b[:, 4] * b[:, 5:].max(1)
        keep = score > self.conf
        boxes = [[float(cx - w / 2), float(cy - h / 2), float(w), float(h)] for cx, cy, w, h in b[keep, :4]]
        idx = cv2.dnn.NMSBoxes(boxes, score[keep].tolist(), self.conf, self.nms)
        out = []
        for i in np.array(idx).flatten():
            x, y, w, h = (v / r for v in boxes[i])
            x, y = max(0, x), max(0, y)
            out.append({"text": "", "box": [round(x), round(y), round(min(w, W - x)), round(min(h, H - y))]})
        return out


class HybridOCR:
    name = "manga-blocks + apple-vision"

    def __init__(self):
        self.vision = AppleVisionOCR()
        self.blocks = MangaBlockDetector()

    def detect(self, image_bytes):
        vlines = self.vision.detect(image_bytes, japanese_only=False)
        result = []
        for blk in self.blocks.detect(image_bytes):
            inside = [l for l in vlines if _overlap(l["box"], blk["box"]) > 0.5]
            if inside and not any(l["ja"] for l in inside) and any(LETTERS.search(l["text"]) for l in inside):
                continue  # Latin/Cyrillic only: browser bar, English UI
            blk["text"] = " ".join(l["text"] for l in inside if l["ja"])
            result.append(blk)
        for l in vlines:
            if l["ja"] and not any(_overlap(l["box"], b["box"]) > 0.5 for b in result):
                result.append({"text": l["text"], "box": l["box"]})
        result.sort(key=lambda l: (l["box"][1], l["box"][0]))
        return result


def _overlap(a, b):
    """Share of box a that lies inside box b."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    iw = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    ih = max(0, min(ay + ah, by + bh) - max(ay, by))
    return iw * ih / max(1, aw * ah)


def default_ocr():
    return HybridOCR() if MODEL.exists() else AppleVisionOCR()
