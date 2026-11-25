You get Japanese text the learner is studying, already split into tokens. Return the grammar
points. The learner is waiting, so keep summaries short.

### `grammar`
Every grammar point in the text: particles in use, conjugations, sentence endings, set phrases,
casual or rough speech patterns.
- `rule`: if the rule is in "Known grammar rules" below, use EXACTLY that string. Otherwise make
  a short new title in the same style (e.g. `～て — te-form (and / please)`).
- `summary`: one sentence.
- `example`: the example from this text, as "Japanese — English".
- `section_md`: ONLY for new rules (use "" for known ones). The Markdown body of a new grammar
  doc section, without the `##` heading or Seen line. Explain it simply, give the pattern in a
  `>` quote, and add a table: Japanese | Romaji | Literal | Natural, with this text's example
  plus one or two simple extra examples.
