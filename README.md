# jp-eye

Learn Japanese while playing games and reading manga. Press a hotkey, click Japanese text on
your screen, and Claude breaks it down word by word: symbols → reading → meaning → translation →
kanji decomposition → grammar. Every word, kanji and grammar rule is saved to a spreadsheet with
a counter, so over time you see what's most common.

## How it fits together

```
 Mac overlay app (mac-overlay/)          Brain service (brain/)
 ⌃⌥J freezes the screen, boxes the  ──►  finds text (manga detector + Apple Vision)
 Japanese, you click a box               staged breakdown with Claude:
                                           words → kanji + grammar (parallel) → save
 floating panel shows /panel        ◄──  serves the results page, streams each stage
                                         saves to japanese.xlsx + grammar.md
```

The brain holds all the logic, so other clients (Windows, phone) only need to capture the screen
and show the panel.

## Setup (macOS 14+, Apple Silicon)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
brain/models/download.sh          # manga text detector, ~95 MB
mac-overlay/build_app.sh          # builds "mac-overlay/Japanese Eyes.app"
```

Needs the [Claude Code](https://claude.com/claude-code) CLI (`claude`) logged in; the brain runs
it for each breakdown.

Open `mac-overlay/Japanese Eyes.app`. It starts the brain by itself (`run_brain.sh`,
http://127.0.0.1:8765). macOS asks for **Screen Recording** and **Documents** access the first time.

## Files

| Path | What it is |
|---|---|
| `japanese.xlsx` | Words, Kanji (with radicals and part counts), Grammar, sorted by count |
| `grammar.md` | One section per grammar rule, with a "Seen" counter |
| `brain/server.py` | HTTP API: `/detect`, `/jobs`, `/jobs/{id}/events`, `/panel` |
| `brain/engine.py` | Claude stages (swap `ClaudeCodeEngine` for an API engine later) |
| `brain/prompts/` | What Claude is asked at each stage |
| `brain/ocr.py` | Text detection |
| `brain/store.py` | Spreadsheet and grammar doc updates |
| `brain/panel.html` | The results view |
| `jp.py` | Add a hand-written batch: `.venv/bin/python jp.py add batch.json` |
