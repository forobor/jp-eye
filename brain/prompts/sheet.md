You get Japanese text the learner is studying, already split into tokens. Return the word list
for the learner's spreadsheet.

### `words`
Every word, particle and expression in the text, once each:
- `dict_form`: the dictionary (normal) form. If the learner already has this word (see
  "Known words" below), use EXACTLY the same string.
- `hiragana`, `romaji`, `meaning`, `pos` (part of speech)
- `seen_form`: the form actually in the text, only if it differs from the dictionary form
  (conjugated, slurred, stretched). Otherwise "".
- `form_note`: what the change is (e.g. "plain past (た-form)"), or "".
Skip pure sound stretches (ォォォ, ーー) and punctuation.
