"""Engines turn a clicked image crop into a breakdown, in stages, so the learner sees results fast:

  1. words   (needs the image)  -> lines with word-by-word tokens + translations   ~10 s
  then, all in parallel (text only):
  2. kanji   (3 kanji per call) -> kanji decomposition + memory tricks, group by group
  3. grammar                    -> grammar points
     sheet                      -> word list for the spreadsheet (not shown)

Engines never touch the study files; the brain saves the result through Store, so engines are
easy to swap:
- ClaudeCodeEngine: runs the local `claude` CLI on the user's subscription (now).
- ClaudeAPIEngine: calls the Anthropic API (later, for sharing with other people). Same prompts
  and schemas, so it only has to implement `run()`.
"""
import asyncio
import base64
import json
import os
import shutil
import tempfile
from pathlib import Path

PROMPTS = Path(__file__).with_name("prompts")


def _prompt(name):
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


_str = {"type": "string"}


def _obj(fields, extra=None):
    props = {k: _str for k in fields}
    props.update(extra or {})
    return {"type": "object", "required": list(props), "properties": props}


TOKEN = _obj(["surface", "reading", "romaji", "gloss", "dict_form", "form_note", "kind"])
LINE = _obj(["jp", "romaji", "hiragana", "literal", "natural"], {"tokens": {"type": "array", "items": TOKEN}})
KANJI = _obj(["kanji", "meaning", "onyomi", "kunyomi", "components", "radical"], {"direct": {"type": "boolean"}})
WORD = _obj(["dict_form", "hiragana", "romaji", "meaning", "pos", "seen_form", "form_note"])
RULE = _obj(["rule", "summary", "example", "section_md"])

SCHEMAS = {
    "words": {"type": "object", "required": ["lines"],
              "properties": {"lines": {"type": "array", "items": LINE}}},
    "kanji": {"type": "object", "required": ["kanji", "explanation_md"],
              "properties": {"kanji": {"type": "array", "items": KANJI}, "explanation_md": _str}},
    "grammar": {"type": "object", "required": ["grammar"],
                "properties": {"grammar": {"type": "array", "items": RULE}}},
    "sheet": {"type": "object", "required": ["words"],
              "properties": {"words": {"type": "array", "items": WORD}}},
}


class StagedEngine:
    """Shared stage logic. Subclasses implement run(stage, text, image_png=None) -> dict."""

    async def words(self, image_png, ocr_text):
        return await self.run("words", f"OCR guess: {ocr_text or '(none — read the image)'}", image_png)

    async def kanji(self, lines, chars):
        text = "\n".join(l["jp"] for l in lines)
        return await self.run("kanji", f"Text:\n{text}\n\nKanji to break down: {' '.join(chars)}")

    async def grammar(self, lines, known):
        return await self.run("grammar", f"Text with tokens:\n{_compact(lines)}\n\n"
                                         f"Known grammar rules (reuse these exact strings): "
                                         f"{json.dumps(known['grammar'], ensure_ascii=False)}\n")

    async def sheet(self, lines, known):
        return await self.run("sheet", f"Text with tokens:\n{_compact(lines)}\n\n"
                                       f"Known words (reuse these exact dict_form strings): "
                                       f"{json.dumps(known['words'], ensure_ascii=False)}\n")


def _compact(lines):
    return json.dumps([{"jp": l["jp"], "natural": l["natural"],
                        "tokens": [{k: t[k] for k in ("surface", "reading", "gloss", "dict_form", "form_note", "kind")}
                                   for t in l["tokens"]]} for l in lines], ensure_ascii=False)


class ClaudeCodeEngine(StagedEngine):
    name = "claude-code"

    def __init__(self, claude_bin=None, model=None, timeout=300):
        self.claude = claude_bin or shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
        self.model = model
        self.timeout = timeout

    async def run(self, stage, text, image_png=None):
        content = []
        if image_png:
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                        "data": base64.b64encode(image_png).decode()}})
        content.append({"type": "text", "text": text})
        msg = {"type": "user", "message": {"role": "user", "content": content}}
        cmd = [self.claude, "-p",
               "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
               "--system-prompt", _prompt("base") + "\n" + _prompt(stage),
               "--json-schema", json.dumps(SCHEMAS[stage]),
               "--tools", "", "--no-session-persistence", "--strict-mcp-config"]
        if self.model:
            cmd += ["--model", self.model]
        # Run in an empty temp folder so no project files or memory leak in.
        with tempfile.TemporaryDirectory(prefix="jp-brain-") as tmp:
            p = await asyncio.create_subprocess_exec(*cmd, cwd=tmp, stdin=asyncio.subprocess.PIPE,
                                                     stdout=asyncio.subprocess.PIPE,
                                                     stderr=asyncio.subprocess.PIPE)
            try:
                out, err = await asyncio.wait_for(p.communicate((json.dumps(msg) + "\n").encode()),
                                                  self.timeout)
            except asyncio.TimeoutError:
                p.kill()
                raise RuntimeError(f"{stage}: claude timed out")
        result = None
        for line in out.decode().splitlines():
            if line.startswith("{") and '"type":"result"' in line:
                result = json.loads(line)
        if p.returncode != 0 or not result or result.get("is_error") or not result.get("structured_output"):
            detail = (result or {}).get("result") or err.decode()[-1500:] or out.decode()[-1500:]
            raise RuntimeError(f"{stage}: claude failed: {detail}")
        return result["structured_output"]


class ClaudeAPIEngine(StagedEngine):
    """Placeholder for the shareable version: same prompts + schemas, via the Anthropic API."""
    name = "claude-api"

    async def run(self, stage, text, image_png=None):
        raise NotImplementedError("API engine comes later, when the app is shared")
