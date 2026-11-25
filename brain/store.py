"""Study data storage: japanese.xlsx (Words / Kanji / Grammar) + grammar.md.

A "batch" is what one click / screenshot produces:
{
  "words":   [{"dict_form", "hiragana", "romaji", "meaning", "pos", "seen_form", "form_note"}],
  "kanji":   [{"kanji", "meaning", "onyomi", "kunyomi", "components", "radical", "direct"}],
  "grammar": [{"rule", "summary", "example", "section_md"}]
}
- Each entry adds +1 to its count. Kanji with "direct": false count as a part of another kanji.
- Radical forms (氵 亻 刂 …) are never rows; the full kanji (水 人 刀 …) is counted instead.
- Grammar "rule" is the exact `## heading` in grammar.md. A new rule needs "section_md"
  (body of the section, without heading/Seen line); an existing one just gets Seen +1.
"""
import re
import threading
from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

SHEETS = {
    "Words": ["Dictionary form", "Seen forms", "Form notes", "Hiragana", "Romaji",
              "Meaning", "Part of speech", "Count", "First seen"],
    "Kanji": ["Kanji", "Meaning", "Onyomi (katakana)", "Kunyomi (hiragana)", "Components",
              "Radical", "Count", "Component count", "First seen"],
    "Grammar": ["Rule", "Summary", "Examples", "Count", "First seen"],
}
WIDTHS = {
    "Words": [16, 22, 30, 16, 16, 30, 14, 8, 11],
    "Kanji": [8, 26, 18, 22, 26, 20, 8, 10, 11],
    "Grammar": [24, 50, 40, 8, 11],
}
HEADER_FILL = PatternFill("solid", fgColor="2F3E5C")
HEADER_FONT = Font(bold=True, color="FFFFFF")
GRAMMAR_INTRO = """# Japanese Grammar Notes

Rules collected from game screenshots. Each rule has a **Seen** counter that goes up by one
every time it appears in a new screenshot. The same counts are in the `Grammar` sheet of
`japanese.xlsx`, sorted from most to least common.

<!-- New rules are added below, one `##` section per rule. -->
"""


class Store:
    """All study data for one learner, kept in one folder."""

    def __init__(self, data_dir):
        self.dir = Path(data_dir)
        self.book = self.dir / "japanese.xlsx"
        self.grammar = self.dir / "grammar.md"
        self.lock = threading.Lock()

    # ---------- reading ----------
    def known(self):
        """Keys already in the data, so the engine can reuse exact names."""
        wb = self._open()
        return {
            "words": [r[0] for r in wb["Words"].iter_rows(min_row=2, values_only=True) if r[0]],
            "kanji": [r[0] for r in wb["Kanji"].iter_rows(min_row=2, values_only=True) if r[0]],
            "grammar": [r[0] for r in wb["Grammar"].iter_rows(min_row=2, values_only=True) if r[0]],
        }

    # ---------- writing ----------
    def add(self, batch):
        with self.lock:
            wb = self._open()
            today = date.today().isoformat()
            self._add_words(wb["Words"], batch.get("words", []), today)
            self._add_kanji(wb["Kanji"], batch.get("kanji", []), today)
            self._add_grammar(wb["Grammar"], batch.get("grammar", []), today)
            wb.save(self.book)
            self._update_grammar_md(batch.get("grammar", []))

    def _add_words(self, ws, words, today):
        header, data = _rows(ws)
        idx = {d["Dictionary form"]: d for d in data}
        for w in words:
            d = idx.get(w["dict_form"])
            if d is None:
                d = {"Dictionary form": w["dict_form"], "Hiragana": w.get("hiragana"),
                     "Romaji": w.get("romaji"), "Meaning": w.get("meaning"),
                     "Part of speech": w.get("pos"), "Count": 0, "First seen": today}
                data.append(d)
                idx[w["dict_form"]] = d
            d["Count"] = (d["Count"] or 0) + 1
            seen = w.get("seen_form")
            if seen and seen != w["dict_form"]:
                d["Seen forms"] = _add_unique(d.get("Seen forms"), seen)
                if w.get("form_note"):
                    d["Form notes"] = _add_unique(d.get("Form notes"), f"{seen}: {w['form_note']}")
        _rewrite(ws, header, data, "Count")

    def _add_kanji(self, ws, kanji, today):
        header, data = _rows(ws)
        idx = {d["Kanji"]: d for d in data}
        for k in kanji:
            d = idx.get(k["kanji"])
            if d is None:
                d = {"Kanji": k["kanji"], "Meaning": k.get("meaning"),
                     "Onyomi (katakana)": k.get("onyomi"), "Kunyomi (hiragana)": k.get("kunyomi"),
                     "Components": k.get("components"), "Radical": k.get("radical"),
                     "Count": 0, "Component count": 0, "First seen": today}
                data.append(d)
                idx[k["kanji"]] = d
            if not d.get("Radical") and k.get("radical"):
                d["Radical"] = k["radical"]
            col = "Count" if k.get("direct", True) else "Component count"
            d[col] = (d[col] or 0) + 1
        _rewrite(ws, header, data, "Count")

    def _add_grammar(self, ws, rules, today):
        header, data = _rows(ws)
        idx = {d["Rule"]: d for d in data}
        for g in rules:
            d = idx.get(g["rule"])
            if d is None:
                d = {"Rule": g["rule"], "Summary": g.get("summary"), "Count": 0, "First seen": today}
                data.append(d)
                idx[g["rule"]] = d
            d["Count"] = (d["Count"] or 0) + 1
            d["Examples"] = _add_unique(d.get("Examples"), g.get("example"), sep="\n")
        _rewrite(ws, header, data, "Count")

    def _update_grammar_md(self, rules):
        if not rules:
            return
        text = self.grammar.read_text(encoding="utf-8") if self.grammar.exists() else GRAMMAR_INTRO
        for g in rules:
            pat = re.compile(r"(^## " + re.escape(g["rule"]) + r"\n\n\*\*Seen: )(\d+)(\*\*)", re.M)
            if pat.search(text):
                text = pat.sub(lambda m: f"{m[1]}{int(m[2]) + 1}{m[3]}", text, count=1)
            else:
                body = (g.get("section_md") or g.get("summary") or "").strip()
                text = text.rstrip() + f"\n\n---\n\n## {g['rule']}\n\n**Seen: 1**\n\n{body}\n"
        self.grammar.write_text(text, encoding="utf-8")

    # ---------- workbook ----------
    def _open(self):
        if self.book.exists():
            return load_workbook(self.book)
        self.dir.mkdir(parents=True, exist_ok=True)
        wb = Workbook()
        wb.remove(wb.active)
        for name, cols in SHEETS.items():
            ws = wb.create_sheet(name)
            ws.append(cols)
            for i, w in enumerate(WIDTHS[name], start=1):
                c = ws.cell(1, i)
                ws.column_dimensions[c.column_letter].width = w
                c.fill, c.font = HEADER_FILL, HEADER_FONT
            ws.freeze_panes = "A2"
        wb.save(self.book)
        return wb


def _rows(ws):
    header = [c.value for c in ws[1]]
    return header, [dict(zip(header, [c.value for c in r])) for r in ws.iter_rows(min_row=2)]


def _rewrite(ws, header, data, sort_col):
    data.sort(key=lambda d: -(d.get(sort_col) or 0))
    ws.delete_rows(2, ws.max_row)
    for d in data:
        ws.append([d.get(h) for h in header])
    for r in ws.iter_rows(min_row=2):
        for c in r:
            c.alignment = Alignment(wrap_text=True, vertical="top")


def _add_unique(existing, new, sep="; "):
    items = [x for x in (existing or "").split(sep) if x]
    if new and new not in items:
        items.append(new)
    return sep.join(items)
