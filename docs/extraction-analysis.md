# Extraction Analysis — Purananuru HTML Source

> **Scope note:** This document analyzes the HTML structure of one Project Madurai source file (`pmuni0494_01`, originally extracted as `Purananuru_Part1_Verses_1_60.html`, now archived under `data/processed/_intermediates/`). It informed the design of `scripts/extract_all_purananuru.py`. Other Project Madurai sources have similar but not identical structures; per-text extractor design is captured in the corresponding `scripts/extract_*.py` file.

Based on examining the Project Madurai HTML edition `pmuni0494_01` of Purananuru, verses 1–60.

## Encoding
- HTML 4.01 Transitional, UTF-8 (confirmed — clean Unicode Tamil, no Bamini)
- No OCR needed for this source

## HTML Structure

### CSS Classes
```
p.verse    → indented verse text (margin: 0cm 0.5cm 0cm 1cm)
p.section  → blue centered section headers (color: rgb(0,0,255))
p.header1  → red centered headers (color: rgb(255,0,0))
p.header2  → centered secondary headers
```
Body text: `bgcolor="white" text="#800000"` (maroon)

### Content Layout Per Verse

Each verse follows this pattern:

1. **Verse heading** — `<center><h3>` tag containing verse number and title
   - Example: `<center><h3> 2. சேரமான் பெருஞ்சோற் றுதியஞ்சேரலாதன். </h3></center>`

2. **Prose introduction** — Plain text (no special tag), gives context about the poet and the poem's subject

3. **Verse text (classical Tamil)** — Wrapped in `<ul>...</ul>` tags with `<br>` line breaks
   - Line numbers appear as plain text with `&nbsp;` spacing (e.g. `5`, `10`, `15`, `20`)
   - Verse ends with verse number in parentheses: `(2)`, `(3)`, `(4)`

4. **Tinai/Turai classification** — Plain text immediately after `</ul>`
   - Example: `திணை- பாடாண்டிணை; துறை- செவியறிவுறூஉ`
   - Also names poet and subject

5. **Commentary (உரை)** — Starts with `<strong>உரை</strong>:` 
   - Detailed word-by-word explanation in prose

6. **Explanation (விளக்கம்)** — Starts with `<strong> விளக்கம்</strong>:`
   - Further scholarly commentary

7. **Separator** — Dashes (`----------`) followed by next verse heading

### Parsing Signals for Extraction Pipeline

| What to extract | How to identify |
|---|---|
| Verse number + title | `<center><h3>` content |
| Classical Tamil verse | Content inside `<ul>...</ul>` blocks |
| Tinai classification | Text containing `திணை-` immediately after `</ul>` |
| Turai classification | Text containing `துறை-` in the same line |
| Poet name | Text containing `பாடியது` in the tinai/turai line |
| Commentary | Text after `<strong>உரை</strong>:` |
| Explanation | Text after `<strong> விளக்கம்</strong>:` |
| Verse separator | Lines of dashes `----------` |

### Key Observations

1. The `<ul>` tag is used uniquely for verse text — this is the cleanest extraction signal
2. Line numbers within verses (5, 10, 15...) are embedded as plain text with `&nbsp;` spacing — need to strip these
3. The parenthesized number at the end of each verse `(2)`, `(3)` etc. is the Purananuru verse number
4. Tinai and Turai are explicitly stated in the text — can be extracted programmatically
5. Poet and subject are named in the same tinai/turai line
6. The introductory prose before each verse contains valuable cultural context
7. Commentary (உரை) and explanation (விளக்கம்) are clearly marked with `<strong>` tags

### What This Means for the Schema

From this single HTML source, we can automatically populate:
- `verse_id` → from verse number
- `source_text` → "Purananuru"
- `layer` → "Sangam"
- `period` → "300 BCE – 300 CE"
- `verse_number` → from parenthesized number at end of verse
- `classical_tamil` → content inside `<ul>` blocks
- `akam_or_puram` → "Puram" (all Purananuru is Puram)
- `cultural_context` → from introductory prose + tinai/turai line
- `source_url` → the PM URL

The commentary and explanation text can inform later annotation but don't map directly to schema fields.
