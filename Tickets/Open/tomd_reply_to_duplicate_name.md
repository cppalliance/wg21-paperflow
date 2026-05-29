# Bug: reply-to enthaelt doppelten Eintrag (Name ohne und mit E-Mail)

## Beobachtung

Bei P3970R0 erscheint `David Vandevoorde` zweimal im `reply-to`-Feld: einmal als reiner Name, einmal mit E-Mail-Adresse. Gleichzeitig fehlen alle anderen Autoren komplett.

## Konkretes Beispiel

**P3970R0** -- PDF-Quelldokument zeigt:

```
Author: David Vandevoorde
        Jeff Garland
        Paul E. McKenney
        Roger Orr
        Bjarne Stroustrup
        Michael Wong
Reply to: daveed@vandevoorde.com
```

Extrahiertes YAML:

```yaml
reply-to:
  - "David Vandevoorde"
  - "David Vandevoorde <daveed@vandevoorde.com>"
```

Erwartet (laut CLAUDE.md: alle Author-like Felder werden in reply-to gemerged):

```yaml
reply-to:
  - "David Vandevoorde <daveed@vandevoorde.com>"
  - "Jeff Garland"
  - "Paul E. McKenney"
  - "Roger Orr"
  - "Bjarne Stroustrup"
  - "Michael Wong"
```

## Zwei separate Probleme

### 1. Duplikat: Name wird doppelt erfasst

Die Extraktion erzeugt zwei Eintraege fuer dieselbe Person:
- `"David Vandevoorde"` -- aus dem Author-Feld
- `"David Vandevoorde <daveed@vandevoorde.com>"` -- aus dem Reply-to-Feld + Name-Zuordnung

Die Merge-Logik in `_enrich_reply_to` oder `_merge_author_fields` erkennt nicht, dass beide Eintraege dieselbe Person sind, und dedupliziert nicht.

### 2. Fehlende Autoren

Die restlichen 5 Autoren (Jeff Garland, Paul E. McKenney, Roger Orr, Bjarne Stroustrup, Michael Wong) fehlen komplett im reply-to. Sie tauchen stattdessen als Body-Text auf:

```markdown
Jeff Garland Paul E. McKenney

Roger Orr Bjarne Stroustrup

Michael Wong Reply to: daveed@vandevoorde.com
```

Die Extraktion hat die mehrzeilige Author-Liste nicht als zusammengehoeriges Metadaten-Feld erkannt.

## Ursache ermitteln

Es muss geklaert werden, WOHER die zwei Eintraege kommen:
- Kommt `"David Vandevoorde"` aus der Author-Zeile und `"David Vandevoorde <daveed@vandevoorde.com>"` aus der Reply-to + Name-Pairing?
- Oder erzeugt die Extraktion beide aus derselben Quelle?
- Wird `_enrich_reply_to` (zip von bare_names und bare_emails) hier falsch angewendet?

## Betroffene Dateien

- `packages/tomd/src/tomd/extract.py` -- `_enrich_reply_to`, `_merge_author_fields`, mehrzeilige Author-Erkennung
- `packages/tomd/src/tomd/api.py` -- YAML-Emission (Deduplizierung vor Ausgabe?)

## Betroffene Paper-ID

- P3970R0
