# Bug: Komma im YAML-Title wird bei Extraktion verschluckt

## Beobachtung

Bei der Metadaten-Extraktion (tomd) gehen Kommata im `title`-Feld des YAML-Front-Matter verloren oder der Text nach dem Komma wird abgeschnitten.

## Konkretes Beispiel

**P3725R2** -- PDF-Titel laut Quelldokument:

```
Filter View Extensions for Safer Use, Rev 2
```

Extrahierter YAML-Title in `p3725r2.md`:

```yaml
title: "Filter View Extensions for Safer Use"
```

Das `, Rev 2` fehlt komplett. Das Komma und der nachfolgende Text wurden bei der Extraktion nicht registriert.

Zum Vergleich: `p3725r3.md` hat den Titel korrekt MIT Komma:

```yaml
title: "Filter View Extensions for Safer Use, Rev3"
```

Das deutet auf ein inkonsistentes Verhalten hin -- manchmal wird das Komma korrekt erfasst, manchmal nicht.

## Vermutete Ursache

Die Metadaten-Extraktion in `extract.py` oder die YAML-Emission in `api.py` behandelt Kommata im Titelstring als Trennzeichen (z.B. als YAML-Liste) oder schneidet am ersten Komma ab, statt den gesamten String als einen gequoteten Skalar zu erhalten.

Moeglich auch: die Extraktion aus HTML/PDF-Tabellen bricht bei Komma-Zellen ab (Verwechslung mit dem `audience`-Feld-Format, das kommaseparierte Listen verwendet).

## Erwartetes Verhalten

Das `title`-Feld muss den vollstaendigen Titel inklusive aller Kommata enthalten, korrekt in doppelte Anfuehrungszeichen eingeschlossen:

```yaml
title: "Filter View Extensions for Safer Use, Rev 2"
```

## Betroffene Dateien

- `packages/tomd/src/tomd/extract.py` -- Metadaten-Extraktion
- `packages/tomd/src/tomd/api.py` -- YAML-Emission / Front-Matter-Generierung

## Scope

- Alle Papers pruefen, bei denen der Originaltitel ein Komma enthaelt
- Sicherstellen, dass der Title als vollstaendiger gequoteter YAML-String behandelt wird
- Regressionstest: Title mit Komma, Doppelpunkt, Anfuehrungszeichen
