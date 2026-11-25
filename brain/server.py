"""The brain: a small local HTTP service every client (Mac overlay, PC, phone) talks to.

  GET  /                   test page: upload an image, click or drag over text
  GET  /panel              the results view every client shows
  GET  /health             status
  POST /detect             image -> Japanese text blocks with boxes
  POST /jobs               image (+ box to crop, OCR text) -> {"job": id}; the breakdown starts
  GET  /jobs/{id}/events   Server-Sent Events, one per stage as soon as it's ready:
                             words -> kanji (several, 3 kanji each) / grammar, in parallel -> saved -> done
                           (or "error" for a stage that failed)

Run:  ./run_brain.sh      (listens on http://127.0.0.1:8765)
Env:  JP_DATA_DIR (default: project folder), JP_PORT (8765), JP_MODEL (optional claude model)
"""
import asyncio
import io
import json
import os
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, StreamingResponse
from PIL import Image

from .engine import ClaudeCodeEngine
from .ocr import default_ocr
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).parent
store = Store(os.environ.get("JP_DATA_DIR", ROOT))
ocr = default_ocr()
engine = ClaudeCodeEngine(model=os.environ.get("JP_MODEL"))
app = FastAPI(title="Japanese study brain")

KANJI = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
PAD = 12  # pixels of margin around a clicked box, so Claude sees the whole text
jobs = {}  # id -> Job (kept in memory; fine for one learner)


class Job:
    def __init__(self):
        self.events = []
        self.changed = asyncio.Condition()

    async def emit(self, stage, data=None):
        async with self.changed:
            self.events.append({"stage": stage, "data": data or {}})
            self.changed.notify_all()

    @property
    def done(self):
        return bool(self.events) and self.events[-1]["stage"] == "done"


async def pipeline(job, image_png, ocr_text, save):
    try:
        known = await run_in_threadpool(store.known)
        words = await engine.words(image_png, ocr_text)                       # 1. words
        await job.emit("words", words)
        lines = words["lines"]

        chars = list(dict.fromkeys(KANJI.findall("".join(l["jp"] for l in lines))))
        groups = [chars[i:i + 3] for i in range(0, len(chars), 3)]
        found, left = [], [len(groups)]

        async def kanji(group):                                               # 2. kanji, 3 at a time
            r = await engine.kanji(lines, group)
            found.extend(r["kanji"])
            left[0] -= 1
            await job.emit("kanji", {**r, "remaining": left[0]})

        async def grammar():                                                  # 3. grammar
            r = await engine.grammar(lines, known)
            for g in r["grammar"]:
                g["known"] = g["rule"] in known["grammar"]   # the app shows "new" / "seen before"
            await job.emit("grammar", r)
            return r

        if not groups:
            await job.emit("kanji", {"kanji": [], "explanation_md": "", "remaining": 0})
        results = await asyncio.gather(grammar(), engine.sheet(lines, known), *map(kanji, groups),
                                       return_exceptions=True)
        g, sheet, ks = results[0], results[1], results[2:]
        failed = False
        for stage, r in [("grammar", g), ("sheet", sheet)] + [("kanji", k) for k in ks]:
            if isinstance(r, Exception):
                failed = True
                await job.emit("error", {"stage": stage, "message": str(r)})
        if save and not failed:                                               # 4. save
            unique = list({(k["kanji"], k["direct"]): k for k in found}.values())   # a part shared by two groups counts once
            await run_in_threadpool(store.add, {"words": sheet["words"], "kanji": unique, "grammar": g["grammar"]})
            await job.emit("saved", {"saved": True})
        else:
            await job.emit("saved", {"saved": False})
    except Exception as e:
        await job.emit("error", {"stage": "words", "message": str(e)})
    finally:
        await job.emit("done")


def crop(data, box):
    x, y, w, h = (int(float(v)) for v in box.split(","))
    img = Image.open(io.BytesIO(data))
    c = img.crop((max(0, x - PAD), max(0, y - PAD), min(img.width, x + w + PAD), min(img.height, y + h + PAD)))
    buf = io.BytesIO()
    c.convert("RGB").save(buf, "PNG")
    return buf.getvalue()


@app.get("/health")
def health():
    return {"ok": True, "ocr": ocr.name, "engine": engine.name, "data_dir": str(store.dir)}


@app.post("/detect")
async def detect(image: UploadFile = File(...)):
    data = await image.read()
    w, h = Image.open(io.BytesIO(data)).size
    lines = await run_in_threadpool(ocr.detect, data)
    return {"width": w, "height": h, "lines": lines}


@app.post("/jobs")
async def start_job(image: UploadFile = File(...), box: str = Form(""), text: str = Form(""),
                    save: bool = Form(True)):
    data = await image.read()
    if box:
        try:
            data = crop(data, box)
        except ValueError:
            raise HTTPException(400, "box must be x,y,w,h")
    job_id = uuid.uuid4().hex[:12]
    job = jobs[job_id] = Job()
    asyncio.create_task(pipeline(job, data, text, save))
    return {"job": job_id}


@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "no such job")

    async def stream():
        sent = 0
        while True:
            async with job.changed:
                await job.changed.wait_for(lambda: len(job.events) > sent)
                new = job.events[sent:]
            for ev in new:
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            sent += len(new)
            if job.done:
                return

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.get("/panel", response_class=HTMLResponse)
def panel():
    """The results view. Every client (Mac panel, test page, later PC/phone) shows this page."""
    return (HERE / "panel.html").read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
def page():
    return (HERE / "test_page.html").read_text(encoding="utf-8")
