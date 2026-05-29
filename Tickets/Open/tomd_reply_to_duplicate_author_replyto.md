# Bug: reply-to enthaelt identischen Eintrag doppelt (Author + Reply-to werden separat gemerged)

## Beobachtung

Bei P3984R0 erscheint `Bjarne Stroustrup <bjarne@stroustrup.com>` exakt zweimal im `reply-to`-Feld. Beide Eintraege sind identisch.

## Konkretes Beispiel

**P3984R0** -- PDF-Quelldokument zeigt:

```
Author: Bjarne Stroustrup
Reply to: bjarne@stroustrup.com
```

Extrahiertes YAML:

```yaml
reply-to:
  - "Bjarne Stroustrup <bjarne@stroustrup.com>"
  - "Bjarne Stroustrup <bjarne@stroustrup.com>"
```

Erwartet:

```yaml
reply-to:
  - "Bjarne Stroustrup <bjarne@stroustrup.com>"
```

## Ursache

Die Extraktion erzeugt zwei separate Eintraege aus zwei Quellen:
1. `Author: Bjarne Stroustrup` -- wird mit der E-Mail gepairt zu `"Bjarne Stroustrup <bjarne@stroustrup.com>"`
2. `Reply to: bjarne@stroustrup.com` -- wird ebenfalls mit dem Namen gepairt zu `"Bjarne Stroustrup <bjarne@stroustrup.com>"`

Die Merge-Logik (`_merge_author_fields` / `_enrich_reply_to`) kombiniert Author- und Reply-to-Felder korrekt zu `"Name <email>"`, erkennt aber nicht, dass beide Quellen dieselbe Person ergeben. Es fehlt eine Deduplizierung nach dem Merge.

## Verwandt

Aehnliches Problem wie bei P3970R0 (siehe `tomd_reply_to_duplicate_name.md`), dort allerdings mit unterschiedlichen Eintraegen (einmal mit, einmal ohne E-Mail). Hier sind beide Eintraege zu 100% identisch -- einfachster Fall fuer eine Deduplizierung.

## Fix

Nach dem Merge aller Author-like Felder (Author, Reply-to, Co-Authors, Editors) muss eine Deduplizierung stattfinden, bevor die Liste ins YAML geschrieben wird. Mindestens: exakte String-Duplikate entfernen. Idealerweise auch: Eintraege mit gleichem Namen zusammenfuehren (Name-only + Name+Email -> nur Name+Email behalten).

## Betroffene Dateien

- `packages/tomd/src/tomd/extract.py` -- `_enrich_reply_to`, `_merge_author_fields`
- `packages/tomd/src/tomd/api.py` -- YAML-Emission (fehlende Deduplizierung)

## Betroffene Paper-ID

- P3984R0
