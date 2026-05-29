# tomd: Abstract im Body -- Verifizierte Fix-Tickets

## Status

**Ticket A:** IMPLEMENTIERT (2026-05-12). Fix in `structure.py`, `KNOWN_SECTIONS`-Guard.
**Ticket B:** IMPLEMENTIERT (2026-05-12). Fix in `pipeline.py`, TOC Protection.
  Ergaenzung: Abstract-Body-Protection (erster Paragraph nach KNOWN_SECTIONS Heading).
  Update (2026-05-12): Protection jetzt nur fuer real-headings, nicht TOC-Eintraege
  (dot-leader check). `_dedup_abstract` entfernt doppelte Abstract-Headings.
**Ticket C:** OFFEN.
**Ticket D (NEU):** OFFEN. TOC-Erkennung unvollstaendig (Dot-Leader + Full-Text).
  Simulation abgeschlossen (124 PDFs, 0 Regressionen). Siehe Ticket D unten.
**Ticket E:** IMPLEMENTIERT (2026-05-12). HTML-Pipeline: Bikeshed `strip_boilerplate`
  entfernte `div[data-fill-with="abstract"]`. Fix in `extract.py`. 27 Papers betroffen.
**Ticket F:** IMPLEMENTIERT (2026-05-13). Page-gated promotion in `wording.py`.
  Promotion nur auf Seiten ab der ersten Seite mit ins-Spans. Praembel-Seiten
  (Abstract, TOC, Revision History) werden nicht mehr falsch promoted. p2583r3:
  137 -> 98 wording-remove (Praembel sauber, Rest auf Wording-Seiten).

Urspruenglich drei Root Causes verifiziert per Pipeline-Trace (2026-05-12).
Ticket A+B implementiert, dabei Ticket D als Folgeproblem entdeckt und verifiziert.
Ticket E separat entdeckt bei P4197R0-Debugging (HTML-Pipeline, nicht PDF).

---

## Arbeitsanweisung fuer den implementierenden Agent

Dieses Ticket enthaelt drei unabhaengige Bugs (A, B, C). Jeder Bug hat einen
eigenen Abschnitt mit: Symptom, exakter Root Cause im Code, verifiziertem
Trace-Output, praezisem Fix mit Code-Diff, Verifikations-IDs, und Vorher/Nachher-
Erwartung.

**Reihenfolge:** A, dann B, dann C. Jeder Fix einzeln testen, bevor der naechste
beginnt.

**Verifikationsprotokoll pro Ticket:**

1. Lies die betroffene Funktion vollstaendig (Read before Write).
2. Grep fuer die Funktion: liste Caller und Callees.
3. Implementiere den Fix (eine Aenderung, kein Rewrite).
4. Schreibe einen pytest fuer den Fix (parametrize mit den Verifikations-IDs).
5. Laufe `uv run pytest packages/tomd/` -- alles muss gruen sein.
6. Laufe das Verifikationsskript (siehe Appendix C) gegen die Verifikations-IDs.
7. Vergleiche Output mit der Vorher/Nachher-Tabelle im Ticket.
8. Erst wenn alles passt: naechstes Ticket.

**Referenzdateien die gelesen werden MUESSEN:**
- `packages/tomd/src/tomd/CLAUDE.md` (Architektur, Regeln)
- `CLAUDE.md` (Root, Frontmatter-Contract, "Body headings start at H2")
- `.cursor/rules/development-discipline.mdc` (Arbeitsprotokoll)

**Paperstore-Pfad:** `data/paperstore/` (relativ zum Repo-Root).
Die PDFs dort sind die Testdaten. Nicht herunterladen, sie sind bereits vorhanden.

### Markdown-Strukturregeln (aus CLAUDE.md und tomd/CLAUDE.md)

Die folgenden Regeln definieren, wie der Markdown-Output aufgebaut sein muss.
Jeder Fix muss diese Regeln einhalten, nicht verletzen:

**Dokumentstruktur:**
```
---
title: "Paper Title"
document: P2583R3
revision: 3
date: 2024-01-15
intent: info
audience: SG1, LEWG
reply-to:
  - "Author Name <email@example.com>"
---

## Abstract

Abstract-Text als eigener Paragraph.

## 1 Erste nummerierte Section

Body-Text...
```

**Verbindliche Regeln:**

1. **H1 ist reserviert fuer den Titel.** Der Titel steht im YAML `title:`-Feld.
   Es gibt KEIN `# H1` im Body. (Root `CLAUDE.md`: "Body headings start at H2.
   The front-matter title renders as H1; no `# H1` in body.")

2. **Bekannte unnummerierte Sections sind `##` (H2).** Das betrifft: `Abstract`,
   `Revision History`, `References`, `Acknowledgements`, `Motivation`, `Wording`,
   `Proposed Wording`, `Design Decisions`. (tomd `CLAUDE.md`: "Known unnumbered
   sections are top-level (`##`)")

3. **Eine Leerzeile zwischen allen Block-Elementen.** Paragraphen, Headings,
   Listen, Code-Bloecke -- immer eine Leerzeile dazwischen.
   (tomd `CLAUDE.md`: "One blank line between all block elements")

4. **Headings im ATX-Style.** `##` statt Unterstriche. (tomd `CLAUDE.md`:
   "Headings use ATX style")

5. **Nesting darf nicht springen.** Kein Heading darf mehr als eine Ebene tiefer
   sein als sein Vorgaenger. (tomd `CLAUDE.md`: "no heading may skip more than
   one level deeper than its predecessor")

6. **Abstract ist KEIN YAML-Schluessel.** Abstract gehoert in den Body als
   `## Abstract`-Heading, nicht ins YAML Front Matter.
   (Root `CLAUDE.md`: `FRONT_MATTER_ORDER` enthaelt nur:
   `title, document, revision, date, intent, audience, reply-to`)

7. **Category labels werden konsumiert.** Kurze all-uppercase Texte wie
   "WG21 PROPOSAL" werden verworfen, nicht als Headings behandelt.
   ABER: Bekannte Section-Namen (Abstract, Contents etc.) sind KEINE category
   labels, auch wenn sie uppercase sind. (tomd `CLAUDE.md`: "Category labels
   (short all-uppercase text) are consumed, not treated as titles")

**Reihenfolge im Output nach dem YAML-Block:**

Das YAML Front Matter endet mit `---`. Danach kommt der Body. Die erste
Section nach dem YAML ist typischerweise `## Abstract` (wenn vorhanden),
gefolgt von den nummerierten Sections (`## 1 ...`, `### 1.1 ...` etc.).
Es darf KEIN Titel-Heading (`# Title`) zwischen YAML und Abstract stehen
(es sei denn `strip_leading_h1` hat versagt -- das ist ein separater Bug).

**Wichtig fuer Ticket C:** Wenn "Abstract:" gefolgt von Fliesstext auf
derselben Zeile steht (z.B. "Abstract: This document outlines..."), muss
der Fix das in ZWEI Sections splitten: `## Abstract` (Heading) + den
Fliesstext als separater Paragraph. Der Fliesstext darf NICHT Teil des
Heading-Texts werden (kein `## Abstract: This document outlines...`).

---

## Ticket A: _extract_metadata frisst ABSTRACT als "category label"

### Verifikations-IDs

| PID | Erwartung BEFORE | Erwartung AFTER |
|-----|-----------------|-----------------|
| p3844r3 | Kein Abstract im Output | `## ABSTRACT` als Heading |
| p4012r0 | Kein Abstract im Output | `## ABSTRACT` als Heading |
| p3978r0 | Kein Abstract im Output | `## ABSTRACT` als Heading |
| p2583r3 | `## Abstract` vorhanden | `## Abstract` unveraendert (positive Kontrolle) |

Weitere betroffene IDs (gleicher Bug, nicht einzeln getracet):
p3844r4, p4012r1, p3978r1, p3978r2, p3978r3.

### Symptom

"abstract" taucht im Markdown-Output ueberhaupt nicht auf. Kein Heading,
kein Paragraph, kein Text. Komplett verschluckt.

### Root Cause

Datei: `packages/tomd/src/tomd/lib/pdf/structure.py`
Funktion: `_extract_metadata` (Zeile ~405)

```python
alpha = [c for c in text if c.isalpha()]
if alpha and all(c.isupper() for c in alpha) and len(text.split()) <= 3:
    _log.debug("Consumed category label in metadata zone: %r", text)
    continue
```

Diese Heuristik verwirft jede Section in der `metadata_zone` (= vor der ersten
nummerierten Section), die all-uppercase ist und <= 3 Woerter hat. Das trifft
"ABSTRACT" und "CONTENTS". Der Code unterscheidet nicht zwischen echten
category labels (z.B. "ISO/IEC JTC1/SC22/WG21") und bekannten Section-Headings.

### Verifizierter Trace

```
[compare] Section 6: 'ABSTRACT' (kind=PARAGRAPH)
Consumed category label in metadata zone: 'ABSTRACT'
[_extract_metadata] ABSTRACT CONSUMED by _extract_metadata!
[structure] No section with 'abstract' after structure_sections!
```

### Exakter Fix

In `_extract_metadata`, Zeile ~405-408, VOR dem `continue` pruefen ob der Text
ein bekannter Section-Name ist:

```python
# AKTUELL (buggy):
alpha = [c for c in text if c.isalpha()]
if alpha and all(c.isupper() for c in alpha) and len(text.split()) <= 3:
    _log.debug("Consumed category label in metadata zone: %r", text)
    continue

# NEU (fix):
alpha = [c for c in text if c.isalpha()]
if alpha and all(c.isupper() for c in alpha) and len(text.split()) <= 3:
    if text.lower().rstrip(":") not in KNOWN_SECTIONS:
        _log.debug("Consumed category label in metadata zone: %r", text)
        continue
```

`KNOWN_SECTIONS` ist bereits importiert in `structure.py` (aus `types.py`).
Keine neuen Imports noetig.

### Caller/Callee-Kontext

- `_extract_metadata` wird aufgerufen von: `structure_sections` (gleiche Datei, Zeile ~428).
- `structure_sections` wird aufgerufen von: `pipeline._run_pipeline` (Zeile ~389).
- `_extract_metadata` ruft auf: `replace` (dataclasses), Regex-Matches.
- Keine Seiteneffekte auf andere Module.

---

## Ticket B: TOC-Filter entfernt Abstract-Heading

### Verifikations-IDs

| PID | Erwartung BEFORE | Erwartung AFTER |
|-----|-----------------|-----------------|
| p3865r1 | Kein Abstract im Output | Abstract-Heading vorhanden |
| p3373r2 | Kein Abstract im Output | `## Abstract` als Heading |
| p4004r0 | Kein Abstract im Output | Abstract-Heading vorhanden |
| p2583r3 | `## Abstract` vorhanden | `## Abstract` unveraendert (positive Kontrolle) |

Weitere betroffene IDs: p3865r2, p3865r3, p3373r3, p3373r4, p4004r1.

### Symptom

Abstract wird korrekt als `HEADING level=2` erkannt durch `structure_sections`,
aber danach vom TOC-Filter entfernt. Im Markdown-Output fehlt das Abstract.

### Root Cause

Datei: `packages/tomd/src/tomd/lib/pdf/pipeline.py` (Zeile ~446-452)

```python
texts = [sec.text.split("\n")[0].strip() for sec in sections]
heading_texts = {sec.text.split("\n")[0].strip()
                 for sec in sections if sec.kind == SectionKind.HEADING}
structural_hints = _toc_structural_hints(sections) if not heading_texts else None
toc_indices = find_toc_indices(texts, heading_texts, structural_hints)
if toc_indices:
    sections = [s for i, s in enumerate(sections) if i not in toc_indices]
```

`find_toc_indices` (in `lib/toc.py`) bekommt nur Strings (`texts` und `headings`).
Es weiss nichts ueber `SectionKind`. "Abstract" ist sowohl ein Heading als auch
ein TOC-Eintrag (weil das Paper ein Inhaltsverzeichnis hat, in dem "Abstract"
vorkommt). `find_toc_indices` markiert "Abstract" als TOC-Eintrag, und die
Filterzeile entfernt es.

### Verifizierter Trace

```
[structure] Section 2: HEADING level=2: 'Abstract'
[TOC] Abstract section at index 2 REMOVED by TOC filter!
SUMMARY: Lost in _extract_metadata: False, Heading after structure: True,
         In final (after TOC filter): False
```

### Architektonische Einschraenkung

`find_toc_indices` in `lib/toc.py` ist format-agnostisch (nur Strings, kein
Import von `Section` oder `SectionKind`). Die Signatur darf NICHT geaendert
werden, um `Section`-Objekte zu akzeptieren.

### Exakter Fix

Der Fix gehoert in `pipeline.py`, NACH dem `find_toc_indices`-Aufruf, BEVOR
die Sections gefiltert werden. Schuetze Indices, deren Section ein HEADING mit
einem `KNOWN_SECTIONS`-Namen ist:

```python
# AKTUELL (buggy):
toc_indices = find_toc_indices(texts, heading_texts, structural_hints)
if toc_indices:
    sections = [s for i, s in enumerate(sections) if i not in toc_indices]

# NEU (fix):
toc_indices = find_toc_indices(texts, heading_texts, structural_hints)
if toc_indices:
    protected = set()
    for idx in toc_indices:
        sec = sections[idx]
        if sec.kind == SectionKind.HEADING:
            fl = sec.text.split("\n")[0].strip().lower().rstrip(":")
            if fl in KNOWN_SECTIONS:
                protected.add(idx)
    if protected:
        _log.debug("Protecting %d known-section headings from TOC removal: %s",
                    len(protected),
                    [sections[i].text.split("\\n")[0].strip() for i in sorted(protected)])
        toc_indices -= protected
    if toc_indices:
        sections = [s for i, s in enumerate(sections) if i not in toc_indices]
```

`KNOWN_SECTIONS` ist bereits importiert in `pipeline.py` (Zeile ~19).
`SectionKind` ist bereits importiert (gleiche Zeile).

### Caller/Callee-Kontext

- `find_toc_indices` wird aufgerufen von: `pipeline._run_pipeline` (Zeile ~450).
- Keine Aenderung an `toc.py` noetig. Fix liegt ausschliesslich in `pipeline.py`.
- `KNOWN_SECTIONS` enthaelt: `abstract`, `revision history`, `references`,
  `acknowledgements`, `motivation`, `wording`, `proposed wording`, `design decisions`,
  und weitere (siehe `types.py`).

---

## Ticket C: Inline-Abstract wird nicht als Heading erkannt

### Verifikations-IDs

| PID | Erwartung BEFORE | Erwartung AFTER |
|-----|-----------------|-----------------|
| p4029r0 | `**Abstract:** text...` (bold inline, kein Heading) | `## Abstract` als Heading + separater Paragraph |
| p2583r3 | `## Abstract` vorhanden | `## Abstract` unveraendert (positive Kontrolle) |

Weitere betroffene IDs: p4029r1.

### Symptom

Abstract-Text ist im Markdown vorhanden, aber als Fliesstext-Paragraph statt
als `## Abstract`-Heading + separater Paragraph. Output:
`**Abstract:** This document outlines...`

### Root Cause

Datei: `packages/tomd/src/tomd/lib/pdf/structure.py`
Funktion: `structure_sections` (Zeile ~508)

```python
is_known = first_line.lower().rstrip(":") in KNOWN_SECTIONS
```

Bei `"Abstract: This document outlines the strategic priorities..."` ergibt
`.lower().rstrip(":")` den Wert
`"abstract: this document outlines the strategic priorities..."` -- das ist
nicht in `KNOWN_SECTIONS`. Die ganze Zeile wird geprueft, nicht nur das
fuehrende Wort.

### Verifizierter Trace

```
first_line:        'Abstract: This document outlines the strategic priorities...'
first_line_lower:  'abstract: this document outlines the strategic priorities...'
is_known:          False
font_level:        None
is_bold:           False
heading_confidence: level=0, conf=UNCERTAIN
WOULD BE HEADING:  False
```

### Exakter Fix

In `structure_sections`, VOR der bestehenden `is_known`-Zeile (~508), pruefen
ob `first_line` mit einem bekannten Section-Namen gefolgt von `:` und Fliesstext
beginnt. Wenn ja: die Section in zwei Teile splitten (Heading + Paragraph)
und beide in `structured` anhaengen.

```python
# AKTUELL (Zeile ~501-522):
m = SECTION_NUM_RE.match(first_line)
has_number = m is not None
section_num = m.group(1) if m else ""

line_fs = sec.font_size
font_level = font_ranks.get(line_fs)
is_bold = bool(sec.lines) and sec.lines[0].is_bold
is_known = first_line.lower().rstrip(":") in KNOWN_SECTIONS
# ...

# NEU (einfuegen VOR der m = SECTION_NUM_RE Zeile):
colon_pos = first_line.find(":")
if colon_pos > 0:
    prefix = first_line[:colon_pos].strip().lower()
    after_colon = first_line[colon_pos + 1:].strip()
    if prefix in KNOWN_SECTIONS and after_colon:
        heading_sec = replace(sec,
                              text=first_line[:colon_pos].strip(),
                              kind=SectionKind.HEADING,
                              heading_level=2,
                              confidence=Confidence.MEDIUM)
        rest_lines = sec.text.split("\n")[1:]
        para_text = after_colon
        if rest_lines:
            para_text += "\n" + "\n".join(rest_lines)
        para_sec = replace(sec, text=para_text)
        structured.append(heading_sec)
        structured.append(para_sec)
        continue

m = SECTION_NUM_RE.match(first_line)
# ... (Rest unveraendert)
```

**Wichtig:** `replace` (aus `dataclasses`) ist bereits importiert in der Datei.
`Confidence` ist bereits importiert. Das neue Heading bekommt `level=2` weil
`CLAUDE.md` sagt: "Known unnumbered sections are top-level (`##`)".

### Einschraenkung

Die `lines`/`spans`-Listen der gesplitteten Section spiegeln nicht exakt die
Textaufteilung wider (die Section-Lines enthalten beide Teile). Das ist
akzeptabel, weil `emit_markdown` primaer auf `sec.text` operiert, nicht auf
`sec.lines` fuer Paragraphen.

### Caller/Callee-Kontext

- `structure_sections` wird aufgerufen von: `pipeline._run_pipeline` (Zeile ~389).
- Die `replace()`-Aufrufe erzeugen neue Section-Objekte; die Original-Section
  wird nicht mutiert.
- Downstream: `_detect_lists_by_position`, `_merge_paragraphs`, `_detect_code_blocks`
  operieren auf dem `structured`-Array. Der eingefuegte Heading + Paragraph
  durchlaufen diese Passes normal.

---

## Ticket D: TOC-Erkennung unvollstaendig (Dot-Leader + Full-Text)

### Status

OFFEN. Simulation abgeschlossen (2026-05-12), 124 PDFs getestet, 0 Regressionen.
Bereit zur Implementierung.

### Verifikations-IDs

| PID | Erwartung BEFORE | Erwartung AFTER |
|-----|-----------------|-----------------|
| p4012r0 | 11 TOC-Dot-Leader-Zeilen + "Contents" im Output | 0 Dots, kein "Contents", Abstract erhalten |
| p3844r3 | 17 TOC-Dot-Leader-Zeilen + "Contents" im Output | 0 Dots, kein "Contents", Abstract erhalten |
| p3978r0 | 5 TOC-Dot-Leader-Zeilen im Output | 0 Dots, Abstract erhalten |
| p2583r3 | TOC korrekt (63 entries) | Unveraendert (positive Kontrolle) |

Weitere betroffene IDs (gleicher Bug, simulationsverifiziert):
p3844r4, p4012r1, p3978r1, p3978r2, p3978r3, p3692r4, p3842r2,
p3865r1, p3865r2, p3865r3, p3950r0, p4004r0, p4004r1.

### Symptom

TOC-Eintraege mit Dot-Leadern (z.B. `6.1 potentially-convertible-to . . . . . 5`)
bleiben im Markdown-Output. "Contents"-Label ebenfalls sichtbar. Der TOC-Run
bricht nach ~10 statt ~30 Eintraegen ab.

### Root Cause (2 Bugs)

**Bug 1:** `_DOT_LEADER_RE` in `toc.py` (Zeile 16) erkennt nur kompakte Punkte.

Datei: `packages/tomd/src/tomd/lib/toc.py`
Regex: `re.compile(r"\s*[.·]{2,}[\s.·]*")`

Dieses Pattern matched `....` (konsekutive Punkte) aber NICHT das haeufige
Muster `. . . .` (Punkte mit Leerzeichen). WG21-PDFs verwenden ueberwiegend
die Leerzeichen-Variante.

**Bug 2:** `find_toc_indices` bekommt nur First-Lines, nicht den vollen Section-Text.

Datei: `packages/tomd/src/tomd/lib/pdf/pipeline.py` (Zeile 447)

```python
texts = [sec.text.split("\n")[0].strip() for sec in sections]
```

Bei Multi-Line-Sections (z.B. Section-Text = `"6.1\npotentially-convertible-to . . . 5"`)
ist die First-Line `"6.1"` ohne Dot-Leader. Die Dots sind auf Zeile 2+.
`find_toc_indices` sieht sie nie.

### Verifizierter Trace (p4012r0)

```
--- ALL SECTIONS (first 35, full text) ---
  [  6] PARAGRAPH  fl_dot=False full_dot=True FL='2.1'
         FULL: '2.1 | LEWG @ Kona 2025 . . . . . . . . . . . . 1'
  [ 12] PARAGRAPH  fl_dot=False full_dot=True FL='6.1'
         FULL: '6.1 | potentially-convertible-to . . . . . . . . 5'
  [ 19] PARAGRAPH  fl_dot=False full_dot=False FL='Contents'
  [ 24] PARAGRAPH  fl_dot=True  full_dot=True FL='10.4 Modify [simd.overview] . . .'

CURRENT: TOC indices: 10 entries (nur 2-11, Run bricht ab)
FIXED:   TOC indices: 31 entries (2-32, vollstaendiger TOC-Block)
```

### Exakter Fix

**Aenderung A** - Neue Regex-Konstante in `toc.py` (nach Zeile 16):

```python
_SPACED_DOT_LEADER_RE = re.compile(r"(?:\. ){2,}\.")
```

**Aenderung B** - Neue Hilfsfunktion in `toc.py` (nach `_first_line`):

```python
def _has_dot_leader(text: str) -> bool:
    """Check for dot leaders in any form (compact or spaced)."""
    return bool(_DOT_LEADER_RE.search(text) or _SPACED_DOT_LEADER_RE.search(text))
```

**Aenderung C** - `find_toc_indices` Signatur erweitern:

```python
def find_toc_indices(
    texts: list[str],
    headings: set[str],
    structural_hints: list[bool] | None = None,
    full_texts: list[str] | None = None,  # NEU
) -> set[int]:
```

**Aenderung D** - Match-Loop in `find_toc_indices` (Zeilen 100-109):

```python
# AKTUELL:
matches = []
for i, text in enumerate(texts):
    if norm_headings:
        matches.append(_matches_heading(_first_line(text)))
    else:
        matches.append(
            bool(structural_hints and i < len(structural_hints)
                 and structural_hints[i])
        )

# NEU:
matches = []
for i, text in enumerate(texts):
    ft = full_texts[i] if full_texts else text
    has_dot = _has_dot_leader(ft)
    if norm_headings:
        matches.append(has_dot or _matches_heading(_first_line(text)))
    else:
        matches.append(
            has_dot
            or bool(structural_hints and i < len(structural_hints)
                    and structural_hints[i])
        )
```

**Aenderung E** - `_normalize_toc_entry` erweitern (Zeile 42):

```python
text = _DOT_LEADER_RE.sub(" ", text)
text = _SPACED_DOT_LEADER_RE.sub(" ", text)  # NEU
```

**Aenderung F** - `pipeline.py` (Zeilen 447-451):

```python
# AKTUELL:
texts = [sec.text.split("\n")[0].strip() for sec in sections]
...
toc_indices = find_toc_indices(texts, heading_texts, structural_hints)

# NEU:
texts = [sec.text.split("\n")[0].strip() for sec in sections]
full_texts = [sec.text for sec in sections]
...
toc_indices = find_toc_indices(texts, heading_texts, structural_hints,
                               full_texts=full_texts)
```

### Simulationsergebnisse (2026-05-12)

124 PDFs simuliert. Ergebnis:

| Metrik | Wert |
|--------|------|
| Total PDFs | 124 |
| Geaendert | 16 |
| Unveraendert | 108 |
| Fehler | 0 |
| Verlorene Abstracts | 0 |
| Gewonnene Abstracts | 0 |
| Entfernte Dot-Leader-Papers | 8 |
| Neue Dot-Leader-Papers | 0 |

Geaenderte Papers im Detail:

| PID | TOC vorher | TOC nachher | Dots | Effekt |
|-----|-----------|-------------|------|--------|
| p3692r4 | 6 | 12 | - | TOC erweitert |
| p3842r2 | 0 | 6 | - | TOC neu erkannt |
| p3844r3 | 10 | 39 | 17->0 | Contents entfernt |
| p3844r4 | 0 | 22 | 13->0 | TOC neu erkannt |
| p3865r1 | 7 | 17 | - | TOC erweitert |
| p3865r2 | 8 | 18 | - | TOC erweitert |
| p3865r3 | 9 | 20 | - | TOC erweitert |
| p3950r0 | 4 | 6 | - | TOC erweitert |
| p3978r0 | 0 | 14 | 5->0 | TOC neu erkannt |
| p3978r1 | 0 | 17 | 8->0 | TOC neu erkannt |
| p3978r2 | 0 | 19 | 10->0 | TOC neu erkannt |
| p3978r3 | 0 | 21 | 11->0 | TOC neu erkannt |
| p4004r0 | 9 | 10 | - | TOC erweitert |
| p4004r1 | 11 | 12 | - | TOC erweitert |
| p4012r0 | 10 | 31 | 11->0 | Contents entfernt |
| p4012r1 | 0 | 23 | 9->0 | TOC neu erkannt |

### Caller/Callee-Kontext

- `find_toc_indices` wird aufgerufen von: `_run_pipeline` in `pipeline.py` (einziger Caller)
- `_normalize_toc_entry` wird aufgerufen von: `find_toc_indices` intern
- `_has_dot_leader` ist NEU, nur vom Match-Loop gerufen
- HTML-Pipeline: NICHT betroffen (ruft `find_toc_indices` nicht auf)

### Architektur-Regeln

- `find_toc_indices` in `lib/toc.py` ist format-agnostisch (nur Strings, kein
  Import von `Section` oder `SectionKind`). Die Signatur wird um `full_texts`
  erweitert (optional, String-only, keine Typen-Abhaengigkeit).
- "Contents" ist KEIN `KNOWN_SECTIONS`-Eintrag (korrekt per CLAUDE.md).
  Es wird als TOC-Label entfernt, nicht als Heading geschuetzt.
- TOC-Block wird vollstaendig gestripped inkl. "Contents"-Label
  (PDF_ARCH.md: "include preceding Contents label").

---

## Ticket E: HTML Bikeshed strip_boilerplate entfernt Abstract

### Status

IMPLEMENTIERT (2026-05-12). Fix verifiziert, 27 Papers regeneriert.

### Verifikations-IDs

| PID | Pipeline | Erwartung BEFORE | Erwartung AFTER |
|-----|----------|-----------------|-----------------|
| p4197r0 | HTML | Kein Abstract im Output | `## Abstract` mit Text |
| p3039r1 | HTML | Kein Abstract im Output | `## Abstract` mit Text |
| p3181r1 | HTML | Kein Abstract im Output | `## Abstract` mit Text |

Alle 27 betroffenen Papers: p0876r22, p1000r7, p1000r8, p2034r6, p3039r1,
p3181r1, p3427r3, p3605r1, p3725r2, p3725r3, p3828r1, p3839r0, p3856r4,
p3856r5, p3856r6, p3856r7, p3856r8, p3874r1, p3962r0, p3967r0, p3968r0,
p3970r0, p3977r0, p4007r0, p4007r1, p4007r2, p4197r0.

### Symptom

HTML papers generated by Bikeshed had no Abstract in Markdown output, even though
the HTML source contained `<div data-fill-with="abstract">` with the full abstract text.

### Root Cause

Datei: `packages/tomd/src/tomd/lib/html/extract.py`
Funktion: `strip_boilerplate`

```python
if generator == "bikeshed":
    for div in soup.find_all("div", {"data-fill-with": True}):
        div.decompose()
```

This removed ALL `div[data-fill-with]` elements, including `div[data-fill-with="abstract"]`
which Bikeshed uses to wrap the abstract heading and body text.

### Fix (implementiert)

```python
if generator == "bikeshed":
    for div in soup.find_all("div", {"data-fill-with": True}):
        if div["data-fill-with"] != "abstract":
            div.decompose()
```

One-line guard: skip decomposition when `data-fill-with="abstract"`.

### Verifikation

- Baseline tests: 738 passed, 7 skipped, 0 failed (unchanged).
- Simulation: 27 GAINs (abstract restored), 0 regressions across 147 HTML papers.
- Logic check (ce-adversarial-reviewer): PASS, 0 issues.
- Runtime: `uv run paperflow convert <27 IDs> --force` completed successfully.
- `HTML_ARCH.md` updated to document the exception.

### Separate Ticket-Datei

Detaillierte Root-Cause-Analyse und vollstaendige Paper-Liste:
`Tickets/Open/P4197R0 is missing the Abstract`

---

## Zusammenfassung

| Ticket | Bug | Datei | Funktion | Status | Verifikations-IDs | Positive Kontrolle |
|--------|-----|-------|----------|--------|-------------------|--------------------|
| A | category-label frisst ABSTRACT | `structure.py` | `_extract_metadata` | DONE | p3844r3, p4012r0, p3978r0 | p2583r3 |
| B | TOC-Filter loescht Abstract | `pipeline.py` | `_run_pipeline` | DONE | p3865r1, p3373r2, p4004r0 | p2583r3 |
| C | Inline-Abstract kein Heading | `structure.py` | `structure_sections` | OFFEN | p4029r0 | p2583r3 |
| D | TOC Dot-Leader + Full-Text | `toc.py` + `pipeline.py` | `find_toc_indices` | OFFEN | p4012r0, p3844r3, p3978r0 | p2583r3 |
| E | HTML Bikeshed Abstract entfernt | `extract.py` | `strip_boilerplate` | DONE | p4197r0, p3039r1, p3181r1 | - |

### Simulationsergebnisse (2026-05-12)

Alle drei Fixes wurden per Monkey-Patch simuliert und gegen echte PDFs gelaufen:

| PID | Ticket | BEFORE | AFTER | Status |
|-----|--------|--------|-------|--------|
| p4029r0 | C | `**Abstract:** text...` (bold inline) | `## Abstract` + Paragraph | FIXED |
| p3844r3 | A | Abstract komplett weg | `## ABSTRACT` | FIXED |
| p3865r1 | B | Abstract komplett weg | `## *Abstract*` (heading) | FIXED |
| p3373r2 | B | Abstract komplett weg | `## Abstract` | FIXED |
| p4004r0 | B | Abstract komplett weg | `## *Abstract*` (heading) | FIXED |
| p4012r0 | A | Abstract komplett weg | `## ABSTRACT` | FIXED |
| p3978r0 | A | Abstract komplett weg | `## ABSTRACT` | FIXED |
| p2583r3 | - | `## Abstract` | `## Abstract` | OK (keine Regression) |
| p4003r2 | - | `## Abstract` | `## Abstract` | OK (keine Regression) |

Test-Suite (ungepatcht): 738 passed, 7 skipped, 0 failed.
Keine betroffenen Golden Files vorhanden -- keine Golden-File-Updates noetig.

### Restliche 44er-Liste

Nach Fix von A+B+C muessen die verbleibenden ~26 Papers der 44er-Liste
(siehe Appendix B) erneut geprueft werden. Sie koennten durch dieselben Bugs
betroffen sein (andere Revisionen) oder weitere Root Causes haben.

---

## Bekannte weitere Luecken (nicht in Scope, niedrigere Prioritaet)

- **HTML `abstract-block`**: Custom-Element wird von `html/render.py` nicht
  explizit gehandelt (betrifft nur HTML-Pipeline, z.B. p3642r4).
- **`strip_leading_h1`**: Koennte bei Papers mit `---` (HR) vor dem H1 versagen.
- **`italic` als Signal**: `heading_confidence` nutzt `is_bold` aber nicht
  `is_italic`. Bei Papers wie p3865r1 funktioniert es ueber `is_known + font_level`,
  aber rein-kursive Headings ohne font_level koennten durchfallen.
- **`## *Abstract*` statt `## Abstract`**: Bei p3865r1 und p4004r0 wird Kursivschrift
  aus dem PDF-Span in die Heading-Emission uebernommen. Kosmetik, kein Funktionsfehler.

---

---

# Appendix A: Verifikationsskript

Das folgende Skript kann als `_debug_verify_fixes.py` im Repo-Root angelegt werden.
Es prueft ob die Fixes funktionieren, indem es `convert_pdf` auf die Verifikations-IDs
ausfuehrt und den Output auf `## Abstract` oder Abstract-Headings prueft.
Nach Verifikation loeschen.

```python
"""Verify abstract fixes against real PDFs. Run after implementing fixes A/B/C.
Usage: uv run python _debug_verify_fixes.py
Delete after verification."""

import sys, os
from pathlib import Path
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent / "packages" / "tomd" / "src"))

from tomd.lib.pdf import convert_pdf

PAPERSTORE = Path("data/paperstore")

CASES = {
    # Ticket A
    "p3844r3": {"expect_heading": True, "ticket": "A"},
    "p4012r0": {"expect_heading": True, "ticket": "A"},
    "p3978r0": {"expect_heading": True, "ticket": "A"},
    # Ticket B
    "p3865r1": {"expect_heading": True, "ticket": "B"},
    "p3373r2": {"expect_heading": True, "ticket": "B"},
    "p4004r0": {"expect_heading": True, "ticket": "B"},
    # Ticket C
    "p4029r0": {"expect_heading": True, "ticket": "C"},
    # Positive controls
    "p2583r3": {"expect_heading": True, "ticket": "ctrl"},
    "p4003r2": {"expect_heading": True, "ticket": "ctrl"},
}


def has_abstract_heading(md: str) -> bool:
    for line in md.split("\n"):
        s = line.strip().lower()
        if s.startswith("#") and "abstract" in s:
            return True
    return False


def main():
    passed = 0
    failed = 0
    for pid, spec in CASES.items():
        pdf = PAPERSTORE / f"{pid}.pdf"
        if not pdf.exists():
            print(f"  SKIP {pid}: PDF not found")
            continue
        md, _ = convert_pdf(pdf)
        got = has_abstract_heading(md)
        ok = got == spec["expect_heading"]
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  {status} {pid} (ticket {spec['ticket']}): "
              f"expect_heading={spec['expect_heading']}, got={got}")

    print(f"\n  {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

---

# Appendix B: 44er-PM-Mismatch-Liste

Vollstaendige Liste der Papers mit `pdf_span_hits > 0` UND
`md has_structured_abstract_section == false`:

```
p3373r2, p3373r3, p3373r4, p3596r0, p3596r1, p3598r0, p3625r1, p3692r4,
p3786r2, p3844r3, p3844r4, p3846r1, p3865r1, p3865r2, p3865r3, p3932r0,
p3936r1, p3948r1, p3950r0, p3955r0, p3978r0, p3978r1, p3978r2, p3978r3,
p3984r0, p3986r0, p3986r1, p4004r0, p4004r1, p4011r0, p4012r0, p4012r1,
p4029r0, p4029r1, p4042r0, p4136r0, p4136r1, p4151r0, p4151r1, p4161r0,
p4174r0, p4188r0, p4191r0, p5000r0
```

Davon durch Tickets A/B/C abgedeckt (verifiziert + vermutete gleiche Revisionen):

- Ticket A: p3844r3, p3844r4, p3978r0-r3, p4012r0, p4012r1 (8 IDs)
- Ticket B: p3865r1-r3, p3373r2-r4, p4004r0, p4004r1 (8 IDs)
- Ticket C: p4029r0, p4029r1 (2 IDs)
- Verbleibend (unklar): ~26 IDs, nach A+B+C erneut pruefen

---

# Appendix C: Simulationsmethode

Die Simulation wurde durchgefuehrt, indem die drei Fixes als Python-Monkey-Patches
auf die Originalfunktionen angewandt wurden, ohne den Quellcode zu aendern.
Pro PDF wurde die Pipeline zweimal gelaufen (BEFORE = Original, AFTER = gepatcht)
und der Markdown-Output auf Abstract-Headings geprueft.

**Ablauf:**

1. Originale Funktionen gesichert (`_orig_extract_metadata`, etc.)
2. Gepatchtete Versionen definiert (identisch zum Originalcode + Fix-Zeilen)
3. Patches aktiviert via `module.function = patched_function`
4. `convert_pdf(pdf_path)` gelaufen
5. Output analysiert: `has_h2_abstract`, `has_any_abstract_heading`, `abstract_as_bold_inline`
6. Patches deaktiviert, Original-Pipeline gelaufen
7. BEFORE vs AFTER verglichen

Die Simulation bewies:
- Alle 7 betroffenen PDFs produzieren nach dem Patch ein Abstract-Heading
- Beide positiven Kontrollen bleiben unveraendert
- Die Patches sind minimal und aendern nur die exakten Stellen aus den Tickets

---

# Appendix D: Empirische Rohdaten

(Aus der urspruenglichen Datensammlung, Stand 2026-05-11.)

## Artefakte im Repo-Root

| Artefakt | Beschreibung |
|----------|-------------|
| `abstract_inventory_report.csv` | 271 Paper-IDs, PDF/MD/HTML-Signale |
| `abstract_inventory_report.summary.json` | Aggregat (271 IDs, 124 PDF, 270 MD, 147 HTML) |
| `markdown_abstract_audit.csv` | 270 MD-Dateien, Abstract-Patterns |
| `_abstract_audit_rows.csv` | 156 PDF-Span-Treffer |
| `_abstract_audit_aggregate.json` | Font/Size-Histogramme |

## Reproduktion

```
uv run --directory packages/tomd python scripts/abstract_section_inventory.py \
  --paperstore data/paperstore -o abstract_inventory_report.csv --json-summary
uv run --directory packages/tomd python scripts/markdown_abstract_audit.py \
  --paperstore data/paperstore -o markdown_abstract_audit.csv
```

## Typografie-Referenz

| Font | Count | | size | Count |
|------|------:|-|------|------:|
| Body | 32 | | 9.0 | 29 |
| Body-Bold | 26 | | 13.0 | 25 |
| ArialMT | 13 | | 11.645 | 12 |
| Times-Italic | 5 | | 18.0 | 11 |

| line_kind | Count |
|-----------|------:|
| standalone_label | 117 |
| short_line_mentions_abstract | 32 |
| inline_with_text | 4 |
| numbered_heading | 3 |

---

## Ticket: p3692r4 -- 4 Bugs (TOC Protection + Dedup + Wording)

**Status:** Open (Bugs 1/2/4 fix in progress, Bug 3 separate ticket)
**Severity:** High (multiple visible defects)
**Found during:** TOC-Fix manual QA (2026-05-12)

### Bug 1: First Abstract heading is empty

**Symptom:** The first `## Abstract` heading in the Markdown has no body text.

**Root cause:** The TOC protection mechanism (`pipeline.py` lines 454-475) protects
ALL `KNOWN_SECTIONS` headings found in the TOC range. A TOC entry for "Abstract"
classified as `SectionKind.HEADING` gets protected and survives TOC stripping as an
empty heading. The real Abstract heading (from the metadata zone) with its body may
also survive, but appears later.

**Fix:** Deduplication step after TOC stripping (`_dedup_abstract`): removes empty
Abstract headings when a content-bearing Abstract heading exists.

### Bug 2: Acknowledgements + References appear near the top (wrong position)

**Symptom:** "Revision History", "Acknowledgements", and "References" headings appear
between the empty Abstract and the real content, despite belonging at the end of the
paper. They appear twice: once at the top (empty, from TOC) and once at the bottom
(correct, with content).

**Root cause:** Same over-broad protection. `fl in KNOWN_SECTIONS` protects ALL
known section headings in the TOC range, including back-matter entries that are just
TOC lines, not real sections.

**Fix:** Narrow protection to `fl == "abstract"` only. Back-matter TOC entries are
stripped with the rest of the TOC.

### Bug 3: Abstract body has false wording markup (del/strikethrough)

**Symptom:** The Abstract body text appears with `<del>` strikethrough and red
background in the Markdown, even though the PDF source shows normal black text.

**Root cause (suspected):** `classify_wording` in `wording.py` operates document-wide.
p3692r4 is a revision paper with genuine wording sections (proposed wording changes)
later in the document. When the document has >=5 `ins` spans, ALL `del_unconfirmed`
spans are promoted to `del` (line 261-265). If the Abstract body contains spans that
`is_red_del()` matches (possibly due to subtle PDF color encoding), they get promoted.

**Fix:** Separate ticket (Ticket F). Requires runtime verification to confirm whether
the Abstract spans are genuinely red or if `is_red_del()` false-positives on them.

### Bug 4: Duplicate Abstract headings

**Symptom:** Two `## Abstract` headings appear in the output: one from the
TOC-protected entry (empty) and one from the paper body (with wording content).

**Root cause:** Combination of Bugs 1 and 2. The protection preserves the TOC
"Abstract" entry, and the real Abstract section in the paper body also survives
(it is outside the TOC range).

**Fix:** Same deduplication step as Bug 1.

**Verification:** `uv run paperflow convert p3692r4 --force` then compare with PDF.

**Affected file:** `data/paperstore/p3692r4.md`

---

## Ticket F: classify_wording false-positive in non-wording sections

**Status:** Implemented (2026-05-13)
**Severity:** Medium
**Found during:** p3692r4 QA (2026-05-12)

**Problem:** `classify_wording` in `wording.py` was document-wide. When a paper has
enough genuine wording spans (>=5 ins), ALL red spans in the entire document got
promoted to `del`, including spans in non-wording sections like the Abstract.

**Root cause:** The promotion logic did not scope promotion to wording-adjacent
regions. Any `del_unconfirmed` span in the document became `del` once the global
ins threshold was met.

**Fix:** Page-gated promotion. Candidates now carry `(span, role, page_num)`.
Promotion only applies on pages at or after the first page containing an `ins` span.
Preamble pages (Abstract, TOC, Revision History) precede wording sections and are
not promoted. Red code-styling on those pages stays `del_unconfirmed` and is dropped.

**Results:** p2583r3: 137 -> 98 `:::wording-remove` blocks. All false positives in
Abstract and Revision History eliminated. Remaining 98 are on pages with genuine
green `ins` spans (Sections 8-15). 738 golden tests pass, 0 regressions.

**Affected file:** `packages/tomd/src/tomd/lib/pdf/wording.py`

---

## Ticket G: p3692r4 -- "History" body bleeds into Abstract

**Status:** Open
**Severity:** Medium
**Found during:** Post-fix QA (2026-05-12)

**Problem:** In `p3692r4.md`, the Abstract (L12) contains the correct abstract text
(L14) followed by the History section body (L16-L39: "P3692R4 updates...",
"P3692R3 fixes...", etc.). The "History" heading is stripped but its body text
is absorbed into the Abstract section. In the PDF, "History" is a separate section
between Abstract and "1 Introduction".

**Root cause (suspected):** `structure_sections` does not recognize "History" as a
section-terminating heading for the Abstract. "History" is not in `KNOWN_SECTIONS`.
The heading might be classified as PARAGRAPH instead of HEADING, or the Abstract
body paragraph and History body get merged by `_merge_paragraphs`.

**Verification:** `uv run paperflow convert p3692r4 --force` then compare
L12-L40 with PDF. The History content (bullet list: "P3692R4 updates...",
"P3692R3 fixes...", etc.) should appear under its own `## History` heading,
not inside Abstract.

**Affected file:** `data/paperstore/p3692r4.md`

---

## Ticket H: p2583r3 -- TOC back-matter sections at top + missing normal Abstract

**Status:** Open
**Severity:** High
**Found during:** Post-fix QA (2026-05-12)

**Problem:** Three issues in `p2583r3.md`:

1. `## Revision History` (L13), `## Acknowledgements` (L17), `## References` (L19)
   appear near the top of the document, before the Abstract. These are TOC entries
   or metadata-zone sections that should have been stripped. They appear again
   correctly at the bottom of the document (L37, L1430, L1434).

2. `## Abstract` (L23) exists but contains only `:::wording-remove` blocks with
   `<del>` markup. The normal-formatted abstract text is missing entirely.

3. The correct `## Revision History` at L37 has body content, confirming the L13
   version is a duplicate from the TOC/metadata zone.

**Root cause (suspected):**
- Back-matter headings: The TOC entries for "Revision History", "Acknowledgements",
  "References" in this PDF do NOT have dot-leaders (the PDF uses tab-based or
  space-aligned TOC formatting). Our protection dot-leader check (`has_dot_leader`)
  does not catch them, so they remain protected as KNOWN_SECTIONS headings.
- Missing normal Abstract: The Abstract section has wording markup (Ticket F
  false-positive), and the original un-marked-up abstract text was never extracted
  or was overwritten by the wording-classified version.

**Potential fix approaches:**
1. Add a positional check: if a protected KNOWN_SECTIONS heading appears BEFORE the
   first numbered section heading (e.g. "1 Introduction"), it is likely a TOC entry
   or metadata artifact, not a real body section. Do not protect it.
2. Detect duplicate KNOWN_SECTIONS headings (same name appears twice) and remove the
   earlier (likely TOC) occurrence regardless of dot-leader presence.
3. For the missing normal Abstract: requires fixing Ticket F (wording false-positive)
   first, since the Abstract body is being classified as wording when it should not be.

**Verification:** `uv run paperflow convert p2583r3 --force` then check:
- L13-L22 should not exist (TOC artifacts)
- L23+ should have normal Abstract text, not wording markup

**Affected file:** `data/paperstore/p2583r3.md`
