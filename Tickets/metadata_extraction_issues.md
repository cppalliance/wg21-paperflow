# Metadata Extraction Issues (Batch)

Chat-Referenz: [Metadata-Audit Manuell](d29e79ce-dfe1-4764-9e80-6c6f6e2f1eb1)

---

## Kontext

Manuelle Prüfung von 14 Papers gegen ihre HTML/PDF-Quellen. Geprüft wurde ob die YAML Front-Matter korrekt aus den Quellen extrahiert wurde, gemessen am kanonischen Format aus `CLAUDE.md` und `tomd/CLAUDE.md`.

### Kanonisches Front-Matter Format (Referenz)

```yaml
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
```

**Regeln:**
- Key-Order: title → document → revision → date → intent → audience → reply-to
- title: double-quoted
- document: unquoted paper number
- revision: integer aus PID (omit für N-papers)
- date: unquoted ISO 8601
- audience: unquoted, comma-separated mit Leerzeichen
- reply-to: YAML list von `"Name <email>"` strings
- Fehlende Keys werden übersprungen

---

## Ergebnisse pro Paper

### N5034 (HTML source) - PASS

| Field | Markdown | Source HTML | Verdict |
|-------|----------|-------------|---------|
| title | `"WG21 agenda: 23-28 March 2026, Croydon, UK"` | `<h1>WG21 agenda: 23-28 March 2026, Croydon, UK</h1>` | OK |
| document | `N5034` | HTML sagt `N5022` (alter Draft-Nummer) | OK (Mailing-Index Override, File heisst n5034) |
| date | `2025-11-01` | `2025-11-01` | OK |
| audience | `All of WG21` | nicht im HTML | OK (Mailing-Index) |
| reply-to | `"Nina Dinka Ranns <dinka.ranns@gmail.com>"` | `mailto:dinka.ranns@gmail.com` + `Nina Dinka Ranns` | OK |

---

### N5035 (PDF source) - PASS

| Field | Value | Check |
|-------|-------|-------|
| title | `"2026-03 WG21 admin telecon"` | OK |
| document | `N5035` | OK |
| date | `2026-03-09` | OK |
| audience | `All of WG21` | OK |
| reply-to | `"Guy Davidson <standard.guy@hatcat.com>"` | OK |

---

### N5036 (PDF source) - ISSUES

| Field | Value | Issue |
|-------|-------|-------|
| title | `"ISO/IEC JTC1/SC22/WG21 White Paper N5036, Extensions to C++ for Transactional Memory Version 2"` | PROBLEM: Titel enthält Dokumentnummer redundant |
| document | `N5036` | OK |
| date | `2026-02-22` | OK |
| audience | `All of WG21` | OK |
| reply-to | `"Michael Wong <fraggamuffin@gmail.com>"` | OK |

Zusätzlich: Body Zeile 10 enthält un-gestrippten Metadata-Block:
```
**Document** **Number:** `5036` **Date:** 2026-02-22 **Reply** **to:** Michael Wong fraggamuffin@gmail.com
```

---

### N5037 (PDF source) - SUSPICIOUS

| Field | Value | Issue |
|-------|-------|-------|
| title | `"2026-03 WG21 admin telecon"` | Identisch zu N5035 |
| document | `N5037` | OK |
| date | `2026-03-09` | Identisch zu N5035 |
| reply-to | `"Guy Davidson <standard.guy@hatcat.com>"` | Identisch zu N5035 |

Vermutlich zwei separate Agendas (vorläufig/final) für denselben Telecon. Kein Bug, aber auffällig.

---

### N5038 (PDF source) - PASS

| Field | Value | Check |
|-------|-------|-------|
| title | `"WG21 2026-03 Croydon admin telecon minutes"` | OK |
| document | `N5038` | OK |
| date | `2026-03-09` | OK |
| audience | `All of WG21` | OK |
| reply-to | `"Braden Ganetsky <braden.ganetsky@gmail.com>"` | OK |

---

### N5040 (PDF source) - PASS

| Field | Value | Check |
|-------|-------|-------|
| title | `"WG21 2026-03 Croydon Hybrid Meeting Minutes"` | OK |
| document | `N5040` | OK |
| date | `2026-04-07` | OK |
| audience | `All of WG21` | OK |
| reply-to | `"Braden Ganetsky <braden.ganetsky@gmail.com>"` | OK |

---

### N5043 (PDF source) - PASS

| Field | Value | Check |
|-------|-------|-------|
| title | `"2026-06 WG21 admin telecon"` | OK |
| document | `N5043` | OK |
| date | `2026-05-25` | OK |
| audience | `All of WG21` | OK |
| reply-to | `"Guy Davidson <standard.guy@hatcat.com>"` | OK |

---

### P0876R22 (PDF source) - ISSUES

| Field | Value | Check |
|-------|-------|-------|
| title | `"fiber_context - fibers without scheduler"` | OK |
| document | `P0876R22` | OK |
| revision | `22` | OK |
| date | `2026-02-22` | OK |
| audience | `LEWG, LWG, CWG` | OK |
| reply-to | 2 Einträge | OK |

Body-Issue: Zeile 12 ist ein massiver un-gestrippter TOC (alle Einträge auf einer Zeile mit Dotted Leaders):
```
abstract . . . . . . . 1 Recent WG21 History . . . . . . . 2 Revision History . . . . . . . 2 ...
```

---

### P1000R7 (PDF source) - PASS

| Field | Value | Check |
|-------|-------|-------|
| title | `"Proposed C++ IS schedule"` | OK |
| document | `P1000R7` | OK |
| revision | `7` | OK |
| date | `2026-01-13` | OK |
| audience | `WG21` | OK |
| reply-to | `"Herb Sutter <herb.sutter@gmail.com>"` | OK |

---

### P1000R8 (PDF source) - PASS

| Field | Value | Check |
|-------|-------|-------|
| title | `"Proposed C++ IS schedule"` | OK |
| document | `P1000R8` | OK |
| revision | `8` | OK |
| date | `2026-04-13` | OK |
| audience | `WG21` | OK |
| reply-to | `"Guy Davidson <standard.guy@hatcat.com>"` | OK |

---

### P1040R9 (HTML/bikeshed source) - ISSUES

| Field | Markdown | Source HTML | Issue |
|-------|----------|-------------|-------|
| title | `"std::embed"` | `<h1>P1040R9<br>std::embed</h1>` | OK (Paper-Nr korrekt gestripped) |
| document | `P1040R9` | in `<h1>` | OK |
| revision | `9` | R9 | OK |
| date | `2026-03-27` | `datetime="2026-03-27"` | OK |
| audience | `EWG Evolution,LEWG Library Evolution,CWG Core` | `EWG, CWG, LEWG` | PROBLEM: Kein Space nach Komma |
| reply-to | `"JeanHeyd Meneide (https://thephd.dev) <phdofthehouse@gmail.com>"` | Author + Reply To | OK |

---

### P1130R2 (HTML/bikeshed source) - ISSUES

| Field | Markdown | Source HTML | Issue |
|-------|----------|-------------|-------|
| title | `"Module Resource Dependency Propagation"` | `<h1>P1130R2<br>Module Resource Dependency Propagation</h1>` | OK |
| document | `P1130R2` | OK | OK |
| revision | `2` | R2 | OK |
| date | `2026-03-27` | `datetime="2026-03-27"` | OK |
| audience | `SG15 Tooling,EWG Evolution` | `EWG, SG15` | PROBLEM: Kein Space nach Komma |
| reply-to | `"JeanHeyd Meneide <phdofthehouse@gmail.com>"` | Author field | OK |

---

### P2000R5 (PDF source) - ISSUES

| Field | Value | Issue |
|-------|-------|-------|
| title | `"Directions for ISO C++"` | OK |
| document | `P2000R5` | OK |
| revision | `5` | OK |
| date | `2026-02-23` | OK |
| audience | `All WG21` | OK |
| reply-to | `"Daveed Vandevoorde <daveed@vandevoorde.com>"` | OK |
| reply-to | `"Directions Group"` | PROBLEM: Kein `<email>` |

---

### P2034R6 (PDF source) - ISSUES

| Field | Value | Issue |
|-------|-------|-------|
| title | `"P2034: Partially Mutable Lambda Captures"` | PROBLEM: Paper-Nummer im Titel |
| document | `P2034R6` | OK |
| revision | `6` | OK |
| date | `2026-03-23` | OK |
| audience | `EWG Evolution` | OK |
| reply-to | 2 Einträge mit Emails | OK |

---

## Root-Cause-Analyse: PDF vs. tomd Konvertierung

Es ist **beides**, aber die meisten Issues sind **tomd-seitig fixbar**.

### Issue 1: Titel mit Dokumentnummer (N5036, P2034R6) → tomd Bug

Die PDFs haben die Paper-Nummer als Teil ihres visuellen Titels auf Seite 1. Das ist normal für WG21-Papers. Aber die Titel-Extraktion in `lib/pdf/structure.py` sollte das erkennen und strippen.

- N5036: `"ISO/IEC JTC1/SC22/WG21 White Paper N5036, Extensions to..."` - der `N5036` Teil ist redundant
- P2034R6: `"P2034: Partially Mutable Lambda Captures"` - der `P2034:` Prefix ist redundant

**Ursache:** `structure.py` Heading Intelligence erkennt category labels wie "WG21 PROPOSAL" (laut tomd CLAUDE.md), aber strippt keine embedded Paper-Nummern aus dem Titel.

**Lösungsansatz:**
- In `structure.py` oder als Post-Processing in `api.py`: Regex-Strip von Paper-Number-Prefixen am Anfang des Titels (`P\d{3,5}R\d+:?\s*` oder `N\d{4,5}[,:]?\s*`)
- Nur strippen wenn die Nummer dem eigenen `document`-Feld entspricht (nicht fremde Paper-Referenzen im Titel)
- Edge case: N5036 hat die Nummer mitten im String, nicht am Anfang

---

### Issue 2: TOC nicht gestripped (P0876R22) → tomd Bug

Der TOC mit Dotted-Leaders (`. . . . . . . 1`) wurde als ein einziger langer Paragraph extrahiert. `lib/toc.py` hat zwei Pfade:
1. Exact-match gegen bekannte Headings
2. Fuzzy-match Fallback

Beides versagt wenn der TOC als eine einzelne zusammengefasste Zeile im Markdown landet.

**Ursache:** PDF-Extraktion hat den multi-line TOC in eine Zeile kollapiert (cross-page join oder fehlende Paragraph-Breaks). Dann erkennt `toc.py` ihn nicht.

**Lösungsansatz:**
- Option A: In `lib/toc.py` Pattern-Match für Dotted-Leader-Sequenzen (`r"\.(\s*\.){3,}\s*\d+"`)
- Option B: In `lib/pdf/cleanup.py` Paragraph-Merge verhindern für Zeilen die mit `. . . N` enden
- Option C: Beides (defensive Tiefe)

---

### Issue 3: Audience ohne Leerzeichen nach Komma (P1040R9, P1130R2) → Mailing Scraper Bug

`packages/mailing/src/mailing/scrape.py` Zeile ~91:
```python
subgroup = cells[6].text.strip()
```

Übernimmt den raw-Text aus der open-std.org Tabelle ohne Normalisierung. Wird dann via `_FALLBACK_KEY_MAP["subgroup"] -> "audience"` direkt in den YAML-Output geschrieben.

**Lösungsansatz:**
- In `scrape.py`: `subgroup = ", ".join(s.strip() for s in subgroup.split(","))`
- Oder defensiver in `api.py` `_format_yaml_value`: Wenn Key == `audience`, normalisiere Komma+Space

---

### Issue 4: Metadata im Body nicht gestripped (N5036) → tomd Bug

`api.py` `_strip_body_metadata_text()` erkennt Metadata-Blöcke anhand von Label-Patterns. Hier hat das PDF die Labels mit Bold-Formatting auf jedem Wort (`**Document** **Number:**`), was das Pattern-Matching unterbricht.

**Lösungsansatz:**
- Vor dem Pattern-Match alle Inline-Formatting-Markers (`**`, `*`, `` ` ``) strippen für den Vergleich
- Oder Regex das `\*{0,2}` zwischen Wörtern toleriert

---

### Issue 5: reply-to ohne Email (P2000R5) → Edge Case, akzeptabel

"Directions Group" ist eine legitime Autorengruppe ohne individuelle Email. Kein Bug.

**Optional:** Warnung im QA-Report wenn ein reply-to Eintrag kein `<...>` Email-Pattern hat.

---

## Zusammenfassung

| # | Issue | Betroffene Papers | Schuld | Priorität |
|---|-------|-------------------|--------|-----------|
| 1 | Titel enthält Paper-Nummer | N5036, P2034R6 | tomd `structure.py` | Medium |
| 2 | TOC nicht gestripped | P0876R22 | tomd `toc.py` / `cleanup.py` | Medium |
| 3 | Audience Komma-Spacing | P1040R9, P1130R2 | `mailing/scrape.py` | Low |
| 4 | Metadata im Body | N5036 | tomd `api.py` | Medium |
| 5 | reply-to ohne Email | P2000R5 | Edge case | Low |

**7 von 14 Papers haben saubere Metadata. 5 von 6 Issues sind auf unserer Seite fixbar. Kein einziges Problem ist "das PDF ist kaputt".**

---

## Relevante Source-Files

| Datei | Rolle |
|-------|-------|
| `packages/tomd/src/tomd/api.py` | `_apply_metadata_fallback`, `_strip_body_metadata_text`, `_canonicalize_front_matter` |
| `packages/tomd/src/tomd/lib/pdf/structure.py` | Titel-Extraktion, Heading Intelligence |
| `packages/tomd/src/tomd/lib/toc.py` | TOC Detection und Stripping |
| `packages/tomd/src/tomd/lib/pdf/cleanup.py` | Paragraph-Merging, Cross-Page Join |
| `packages/mailing/src/mailing/scrape.py` | Audience/Subgroup Scraping |
| `packages/tomd/src/tomd/CLAUDE.md` | Front-Matter-Contract, Heading Rules |
| `CLAUDE.md` (root) | Canonical Front-Matter Spec |
