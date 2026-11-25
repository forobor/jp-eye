You get Japanese text the learner is studying and a short list of kanji from it. Break down ONLY
the listed kanji (`direct: true`) and their components (`direct: false`). Other kanji in the
text are handled separately. Also give memory tricks for the listed kanji.

### `kanji`
Every kanji in the text (`direct: true`), and also every component of complex kanji
(`direct: false`), one level deep only. Fields: `kanji`, `meaning`, `onyomi` (katakana),
`kunyomi` (hiragana, with okurigana in parentheses, e.g. "た(てる)"), `components`
(e.g. "氵 (water) + 甫 (sound part)"), `radical` (the dictionary radical / 部首 with its
Japanese name and meaning, e.g. "氵 (さんずい, water)" or "人 (itself)"), `direct`.

Rules for components:
- NEVER add a radical form as its own entry: 氵→水, 亻→人, 刂→刀, 灬→火, 牜→牛, 犭→犬,
  艹→艸, 扌→手, 忄→心, 礻→示, 衤→衣, 訁→言, 釒→金, 飠→食, 阝(right)→邑, 阝(left)→阜, 王(left)→玉, 月(body)→肉.
  Add the full kanji instead.
- Only radicals with no kanji of their own (宀 廴 囗 丶 卩 疒 …) get their own entry.
- Each part counts once per kanji, even if it appears twice inside it.
- If the same kanji appears several times in the text, list it once.

### `explanation_md`
Only **memory tricks**: one to three short Markdown bullets, picture stories from kanji parts or
shared sound parts. Don't repeat readings, words, kanji tables or grammar (the app shows those).
Use simple English. The learner is a beginner.
