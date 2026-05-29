# Bug: Kursive Audience-Zeile wird nicht als Metadatum erkannt

## Beobachtung

Bei Papers, die ihre Metadaten nicht in einer Tabelle, sondern als kursive Einzelzeilen im Fliesstext darstellen, wird das `audience`-Feld nicht aus dem Dokument extrahiert. Stattdessen greift der Mailing-Fallback ein, was zu falschen oder unvollstaendigen Werten fuehrt.

## Konkretes Beispiel

**P4143R0** -- Im PDF-Quelldokument steht:

```
Audience: CWG
S. Davis Herring <herring@lanl.gov>
Los Alamos National Laboratory
March 27, 2026
```

Diese Zeilen sind kursiv gesetzt, nicht in einer HTML-Tabelle. Die Extraktion erkennt dieses Layout nicht und zieht den gesamten Block in eine einzige Zeile zusammen:

```markdown
*Audience*: CWG S. Davis Herring <herring@lanl.gov> Los Alamos National Laboratory March 27, 2026
```

Das extrahierte YAML-Front-Matter zeigt:

```yaml
audience: CWG Core
```

`CWG Core` stammt aus dem Mailing-Fallback, nicht aus der Dokumentenextraktion. Das Originaldokument sagt nur `CWG`.

## Problem

Die Metadaten-Extraktion (`extract.py`) sucht primaer nach tabellarischen Metadaten-Layouts (HTML `<table>`, `<dl>`, etc.). Papers, die ihre Metadaten als kursive Zeilen im Fliesstext formatieren (ein gaengiges Layout bei CWG-Papers), werden nicht als Metadaten-Quelle erkannt.

Zusaetzlich wird der kursive Audience-Block nicht korrekt in seine Bestandteile zerlegt:
- `Audience: CWG` (Zielgruppe)
- `S. Davis Herring <herring@lanl.gov>` (Reply-to)
- `Los Alamos National Laboratory` (Affiliation)
- `March 27, 2026` (Datum)

Stattdessen landet alles als ein zusammenhaengender Body-Text.

## Erwartetes Verhalten

Die Extraktion sollte auch kursive/inline Metadaten-Bloecke erkennen. Erwartetes YAML:

```yaml
audience: CWG
```

Nicht den Mailing-Fallback-Wert `CWG Core`.

## Betroffene Dateien

- `packages/tomd/src/tomd/extract.py` -- Metadaten-Extraktion (fehlende Heuristik fuer kursive Layouts)
- Betrifft vermutlich mehrere CWG-Papers mit aehnlichem Layout

## Betroffene Paper-ID

- P4143R0
