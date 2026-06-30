Optional static HTML inputs for tests. Prefer inline strings in `test_html_*.py` unless a snippet is large or shared across files; then add a `.html` here and load with `Path(__file__).resolve().parent / "fixtures/html/name.html"`.

Byte-exact snapshot outputs live in sibling directory [`../golden/`](../golden/): `*.snapshot.md` and optional `*.snapshot.prompts.json` (JSON array of self-contained LLM reconcile prompts), produced from the `{stem}.html` sources in that same folder via `convert_html`. See [`test_html_golden.py`](../../test_html_golden.py).
