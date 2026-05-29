# Bug: reply-to akkumuliert vorherige Autoren kaskadierend

## Beobachtung

Bei P3911R1 enthaelt jeder Eintrag im `reply-to`-Feld alle vorherigen Autoren als Praefix. Statt 5 separater Eintraege entsteht eine kaskadierende Liste, in der jeder Eintrag laenger wird. Zusaetzlich fehlen bei dem jeweils letzten Autor die spitzen Klammern um die E-Mail.

## Konkretes Beispiel

**P3911R1** -- PDF-Quelldokument zeigt:

```
Authors: Darius Neațu <dariusn@adobe.com>,
Andrei Alexandrescu <andrei@nvidia.com>, Lucian Radu Teodorescu <lucteo@lucteo.ro>, Radu Nichita <radunichita99@gmail.com>, Herb Sutter <herb.sutter@gmail.com>
```

Extrahiertes reply-to (Markdown-Ausgabe):

```
Darius Neațu dariusn@adobe.com
Andrei Alexandrescu andrei@nvidia.com
Andrei Alexandrescu <andrei@nvidia.com>, Lucian Radu Teodorescu lucteo@lucteo.ro
Andrei Alexandrescu <andrei@nvidia.com>, Lucian Radu Teodorescu <lucteo@lucteo.ro>, Radu Nichita radunichita99@gmail.com
Andrei Alexandrescu <andrei@nvidia.com>, Lucian Radu Teodorescu <lucteo@lucteo.ro>, Radu Nichita <radunichita99@gmail.com>, Herb Sutter herb.sutter@gmail.com
```

Erwartet:

```yaml
reply-to:
  - "Darius Neațu <dariusn@adobe.com>"
  - "Andrei Alexandrescu <andrei@nvidia.com>"
  - "Lucian Radu Teodorescu <lucteo@lucteo.ro>"
  - "Radu Nichita <radunichita99@gmail.com>"
  - "Herb Sutter <herb.sutter@gmail.com>"
```

## Zwei separate Probleme

### 1. Kaskadierende Akkumulation

Jeder Eintrag enthaelt den vollstaendigen Text aller vorherigen Autoren als Praefix. Das Muster:

- Eintrag 1: `Autor1 email1`
- Eintrag 2: `Autor2 email2`
- Eintrag 3: `Autor2 <email2>, Autor3 email3`
- Eintrag 4: `Autor2 <email2>, Autor3 <email3>, Autor4 email4`
- Eintrag 5: `Autor2 <email2>, Autor3 <email3>, Autor4 <email4>, Autor5 email5`

Vermutung: Der Parser iteriert ueber die komma-separierte Autorenliste und nimmt bei jedem Schritt den Rest-String ab der aktuellen Position, statt nur den einzelnen Autor zu extrahieren.

### 2. Fehlende spitze Klammern beim letzten Autor

In jedem Eintrag fehlen die `< >` um die E-Mail-Adresse des jeweils letzten Autors. Erst im naechsten Eintrag, wenn er als Praefix auftaucht, hat er seine Klammern. Das deutet darauf hin, dass die Klammern-Erkennung am Zeilenende scheitert oder der Regex den letzten Match anders behandelt.

## Ursache ermitteln

- Wie wird die komma-separierte Autorenliste geparst? Wird bei jedem Match der Rest-String statt des einzelnen Treffers uebernommen?
- Wo werden die spitzen Klammern um E-Mails hinzugefuegt/erhalten? Warum nur fuer vorangehende, nicht fuer den letzten?

## Betroffene Dateien

- `packages/tomd/src/tomd/extract.py` -- Author/Reply-to-Parsing, komma-separierte Listen
- `packages/tomd/src/tomd/api.py` -- YAML-Emission

## Betroffene Paper-IDs

- P3911R1
- P3911R2
