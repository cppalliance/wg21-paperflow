# Markdown-Regenerierung: Was lief und was nicht

## Problem

Nach Code-Aenderungen in `table.py` (Spec-Table-Erkennung fuer Cross-Page-Tabellen) musste die Markdown-Datei `p4003r1.md` neu generiert werden, damit die Fixes wirksam werden.

## Was NICHT funktioniert hat

### 1. `paperflow convert P4003R1 --force` ohne DB-Reset

```powershell
$env:WG21_DATA_DIR = "C:\Users\sabog\Desktop\cppalliance\cppalliance\data\paperstore"
uv run paperflow convert P4003R1 --force
```

**Ergebnis**: Laeuft in ~6 Sekunden durch (Pipeline braucht normalerweise 12+s), schreibt die Datei NICHT neu. Der `--force`-Flag ueberspringt nur den Check `not p.markdown_path` in `jobs.py` Zeile 309-313, fuehrt aber die Pipeline trotzdem nicht aus wenn der Worker entscheidet dass nichts zu tun ist.

### 2. `paperflow convert P4003R1` (ohne --force)

```powershell
uv run paperflow convert P4003R1
```

**Ergebnis**: "No papers need processing." -- weil `markdown_path` in der DB bereits gesetzt ist.

### 3. Direktes Schreiben in den falschen Pfad

```python
from tomd.lib.pdf.pipeline import _run_pipeline
r = _run_pipeline(Path(r'data\paperstore\p4003r1.pdf'))
Path(r'data\paperstore\p4003r1.md').write_text(r.md, encoding='utf-8')
```

**Ergebnis**: Schreibt korrekte Markdown, aber an den FALSCHEN Ort. Die DB zeigt auf `data\paperstore\paperstore\p4003r1.md` (verschachtelter Pfad), nicht `data\paperstore\p4003r1.md`. Der Preview-Server liest aus dem DB-Pfad und sieht die alte Datei.

## Was FUNKTIONIERT hat

### DB-Reset + `--force`

```powershell
# 1. markdown_path in der DB zuruecksetzen
uv run python -c "
import sqlite3
from pathlib import Path
db = Path(r'data\paperstore\paperstore.db')
con = sqlite3.connect(str(db))
con.execute('UPDATE papers SET markdown_path = NULL WHERE paper_id = ?', ('P4003R1',))
con.commit()
con.close()
"

# 2. Dann convert mit --force
$env:WG21_DATA_DIR = "C:\Users\sabog\Desktop\cppalliance\cppalliance\data\paperstore"
uv run paperflow convert P4003R1 --force
```

**Ergebnis**: Pipeline laeuft vollstaendig, schreibt die neue Markdown nach `data\paperstore\paperstore\p4003r1.md`, Preview-Server zeigt korrekte Daten.

## Wichtige Erkenntnis: Doppelter paperstore-Pfad

Die Dateistruktur hat zwei Ebenen:

```
data/paperstore/           <-- WG21_DATA_DIR zeigt hierhin
  paperstore.db
  p4003r1.pdf              <-- Source-PDFs liegen hier
  paperstore/              <-- Markdowns liegen hier (verschachtelt!)
    p4003r1.md
```

Die DB speichert `markdown_path` als absoluten Pfad nach `data/paperstore/paperstore/p4003r1.md`. Wenn man Markdowns manuell generiert, muss man sie an diesen verschachtelten Ort schreiben, nicht ins Root.

## Fuer kuenftige Regenerierung: Einzelnes Paper

```powershell
# Schritt 1: DB-Eintrag zuruecksetzen
uv run python -c "
import sqlite3; con = sqlite3.connect(r'data\paperstore\paperstore.db')
con.execute('UPDATE papers SET markdown_path = NULL WHERE paper_id = ?', ('P4003R1',))
con.commit(); con.close()
"

# Schritt 2: Convert
$env:WG21_DATA_DIR = 'C:\Users\sabog\Desktop\cppalliance\cppalliance\data\paperstore'
uv run paperflow convert P4003R1 --force
```

## Fuer kuenftige Regenerierung: ALLE Papers

```powershell
# Schritt 1: Alle markdown_paths zuruecksetzen
uv run python -c "
import sqlite3; con = sqlite3.connect(r'data\paperstore\paperstore.db')
con.execute('UPDATE papers SET markdown_path = NULL')
con.commit(); con.close()
"

# Schritt 2: Alle konvertieren (dauert lange!)
$env:WG21_DATA_DIR = 'C:\Users\sabog\Desktop\cppalliance\cppalliance\data\paperstore'
uv run paperflow convert --force
```

## __pycache__ nicht vergessen

Nach Code-Aenderungen in `table.py` oder anderen `.py`-Dateien immer den Python-Cache loeschen:

```powershell
Get-ChildItem -Recurse -Directory -Filter "__pycache__" "packages" | Remove-Item -Recurse -Force
```

Sonst laeuft moeglicherweise die alte kompilierte Version.
