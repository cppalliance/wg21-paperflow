# Models, VRAM & Deployment Survey (LangExtract + PDF→Markdown Repos)

Stand: 2026-06-29. Recherche durch 20 parallele Composer-2.5-Subagents + Web-Recherche
gegen offizielle READMEs/Model-Cards. Quellen sind pro Zeile/Tabelle verlinkt.

**Zweck:** Beantwortet die Frage "Wie viel GB VRAM brauche ich und wie nutze ich diese
LLMs (API vs. lokal)?" für (a) google/langextract und (b) alle Converter unter
`packages/whisker/research/repos/`. Dieses Wissen ist verifiziert und soll nicht verloren gehen.

> **Warnung zur lokalen Repo-Kopie:** Die Verzeichnisse unter
> `packages/whisker/research/repos/` sind **leere/shallow Git-Clones** (nur `.git`, kein
> nutzbarer Source). Alle Modell-/VRAM-Angaben hier stammen aus offiziellen GitHub-READMEs,
> Hugging-Face-Model-Cards, PyPI und den Redteam-Reports unter `research/redteam/`, **nicht**
> aus lokalem Code. Vor Code-Inspektion: `git -C <repo> fetch --depth 1` / neu clonen.

---

## 0. Die zentrale Erkenntnis: 3 Betriebsarten

Die VRAM-Frage ist **nur** relevant, wenn ein Modell **lokal auf deiner GPU** läuft.
Viele Tools nutzen LLMs **per Cloud-API** → dann **0 GB VRAM** fürs LLM, dafür API-Key +
Internet + Pay-per-Token.

| Betriebsart | GPU/VRAM nötig? | Auth | Beispiel |
|-------------|-----------------|------|----------|
| **Cloud-API** | **Nein** (0 GB fürs LLM) | API-Key | LangExtract + Gemini; marker `--use_llm`; markitdown + GPT-4o |
| **Lokal (Ollama / vLLM / llama.cpp)** | **Ja** (2–24+ GB) | keiner | LangExtract + `gemma2:2b`; olmOCR; MinerU VLM |
| **Lokal ohne LLM** (CV/OCR/Regeln) | gering (0–5 GB) oder CPU | keiner | marker solo; MinerU pipeline; pymupdf4llm; markitdown Basis |

**Whisker selbst:** **0 GB VRAM, kein LLM, kein Netz.** Deterministische QA über drei Lanes
(`00-EVIDENCE-BASELINE.md`: "Deterministic, no-LLM QA for tomd's PDF/HTML → Markdown").
Whisker *bewertet* Markdown, es *konvertiert* nichts und *ruft kein LLM auf* (außer der
einmaligen, manuellen, nicht-CI Read-Back-Validierung in `comprehension-poc-report.md`).

---

## 1. google/langextract

LangExtract ist **reine LLM-Extraktion** aus Text (kein PDF-Parser). Es gibt **kein
eingebautes Hybrid** (Rules+LLM); "Rules" = Prompt-Anweisungen, kein Regex-Engine.
Hybrid ist ein nutzerseitiges Orchestrierungsmuster.

Quellen: [README](https://github.com/google/langextract),
[Ollama-Provider-Docs](https://github.com/google/langextract/tree/main/examples/ollama),
[llmrun Gemma-2-2B](https://llmrun.dev/model/google-gemma-2-2b).

### 1.1 Wie nutzt man es? (Code, verifiziert aus README)

**Cloud (empfohlener Default) — API-Key, 0 GB VRAM:**
```python
import langextract as lx
result = lx.extract(
    text_or_documents=input_text,
    prompt_description=prompt,
    examples=examples,
    model_id="gemini-3.5-flash",   # wählt automatisch Gemini-Provider
)
```
API-Key via `LANGEXTRACT_API_KEY` (Env oder `.env`), oder `api_key=...`, oder Vertex AI
Service-Account (`language_model_params={"vertexai": True, ...}`).
API-Key-Quellen: AI Studio (Gemini), Vertex AI (Enterprise), OpenAI Platform.

**OpenAI — API-Key, 0 GB VRAM:**
```python
result = lx.extract(..., model_id="gpt-4o")   # pip install langextract[openai]
```

**Lokal via Ollama — kein API-Key, GPU/VRAM nötig:**
```python
result = lx.extract(
    ...,
    model_id="gemma2:2b",                # wählt automatisch Ollama-Provider
    model_url="http://localhost:11434",
)
```
Setup: Ollama installieren → `ollama pull gemma2:2b` → `ollama serve`.
Bei Ollama: `fence_output` und `use_schema_constraints` ungesetzt lassen (Auto-Config).
Schema-Constraints (Controlled Generation) gibt es **nur bei Gemini**, nicht bei Ollama/OpenAI.

### 1.2 Empfohlene Modelle

| Tier | Modell | Betrieb | VRAM lokal | Notiz |
|------|--------|---------|-----------|-------|
| **Cloud Default** | `gemini-3.5-flash` | API | **0 GB** | Schema-constrained; bester Default |
| **Cloud günstig** | `gemini-3.1-flash-lite` | API | **0 GB** | High-Volume / kostensensitiv |
| **Cloud komplex** | Gemini Pro (aktuell) | API | **0 GB** | Tiefes Reasoning |
| **Cloud OpenAI** | `gpt-4o` / `gpt-4o-mini` | API | **0 GB** | Batch-API unterstützt |
| **Lokal Default** | `gemma2:2b` | Ollama | **~2–3 GB** (Q4_K_M) | CI-Integrationstest-Modell |
| **Lokal light** | `llama3.2:1b` | Ollama | **~2 GB** | |
| **Lokal mid** | `llama3.2:3b`, `gemma3:4b` | Ollama | **~3–3.5 GB** | gute 8-GB-GPU-Passung |
| **Lokal stark** | `qwen2.5:7b`, `mistral:7b` | Ollama | **~5.5–6 GB** | |
| **Lokal groß** | `gemma3:27b` | Ollama | **~17 GB** | 24-GB-GPU |
| **Lokal XXL** | `llama3.1:70b` | Ollama | **~42 GB** | 48 GB+ |

VRAM = abgeleitet aus Ollama-Q4_K_M-Defaults (Gewichte + ~1–1.5 GB KV/Overhead).
LangExtract publiziert **keine** eigene VRAM-Tabelle.

**Gemma-2-2B Quantisierungs-Detail** ([llmrun](https://llmrun.dev/model/google-gemma-2-2b)):
Q4_K_M 1.7 GB Gewichte (komfortabel **3+ GB**), Q2_K 1.2 GB, BF16 5.8 GB.

### 1.3 GB-Antwort für LangExtract

> **API (Gemini/OpenAI): 0 GB GPU.** Lokal via Ollama: **mind. 4 GB**, empfohlen **8 GB**
> Headroom; Startmodell `gemma2:2b` (~2–3 GB). Für 7B-Modelle lokal: **8–12 GB**.

---

## 2. PDF→Markdown Converter: Modelle + VRAM + Deployment

### 2.1 ML/VLM-basiert (VRAM-relevant)

| Repo | Modelle | Deployment | Min VRAM | Komfortabel | Hybrid? |
|------|---------|-----------|----------|-------------|---------|
| **MinerU** | `MinerU2.5-Pro-2605-1.2B` (VLM) + PP-DocLayoutV2, PP-OCRv6, UniMERNet, SLANet/UNet (tables) | Lokal: vLLM (Linux), LMDeploy (Win), MLX (macOS); auch HTTP-Client zu Remote-VLM | pipeline **4 GB**, VLM **8 GB**, hybrid **8 GB** | hybrid **16 GB+** | **Ja** (default `hybrid-engine`) |
| **marker** | Surya layout/OCR (lokal) + optional **Gemini** (`--use_llm`) | Lokal PyTorch (GPU/CPU/MPS) + optional Cloud-LLM | **3.5 GB avg / 5 GB peak** pro Worker | 1 Worker auf 8 GB; parallel × VRAM | **Ja** (CV lokal + LLM cloud) |
| **docling** | Standard: Heron (RT-DETR) layout + TableFormer + OCR; VLM: **Granite-Docling-258M** | Lokal Transformers/MLX/vLLM; oder Ollama/LM-Studio-API | Standard **2–4 GB**; VLM inline **~1–2 GB** | VLM vLLM **12–32 GB** | **Ja** (Pipeline ODER Single-VLM) |
| **olmOCR** | `allenai/olmOCR-2-7B-1025-FP8` (Fine-tune von Qwen2.5-VL-7B) | Lokal vLLM (auto-spawn) oder externer vLLM-Server | **12 GB** (eng; Code-Check teils 15 GB) | **16 GB** (FP8) / **24 GB** (BF16) | Nein (reiner VLM) |
| **Surya 2** | **650M VLM** (layout+OCR+table) + kleiner torch-Detector | vLLM (NVIDIA) / llama.cpp (CPU/Apple) | **16 GB** (T4) | **24 GB** (4090 default) | Nein (Single-VLM + Detector) |
| **Dolphin-v2** | **Qwen2.5-VL-3B** | HF Transformers / vLLM / TensorRT-LLM | **8 GB** | **12 GB** | **Ja** (2-Stage: analyze→parse, doc-type-routing) |
| **Dolphin v1/1.5** | Swin + mBart **~0.3B** | HF Transformers | **2–4 GB** | 4 GB | Ja (gleiche Arch, kleiner) |
| **nougat** | `facebook/nougat-base` ~350M (auch `nougat-small`) | HF Transformers (GPU) | **~4 GB**/task | 4–4.2 GB peak (A6000-Bench) | Nein |
| **PDF-Extract-Kit** | DocLayout-YOLO, UniMERNet, PaddleOCR, LayoutLMv3 | Lokal PyTorch/Paddle | **8 GB** (alt 6 GB) | **16 GB** (OCR-Accel via paddlepaddle-gpu) | Ja (Multi-Model-Kit; E2E → MinerU) |
| **pymupdf4llm** | ONNX OCR (klein) + layout-Heuristik | CPU/ONNX-Runtime | **0 GB GPU** | RAM only | **Ja** (layout + ONNX-OCR-Cascade, Thresholds) |
| **img2table** | OpenCV + kleine CV-Modelle (kein LLM) | CPU (optional CUDA für OCR) | **0–2 GB** | CPU reicht | Nein |
| **unstructured** | hi_res: detectron2/YOLOX layout + OCR (Tesseract/Paddle) | CPU oder optional GPU | GPU **optional** | 4–8 GB wenn GPU | **Ja** (Regeln + ML layout) |

**MinerU Detail** ([README](https://github.com/opendatalab/MinerU), v3.4.0 — `hybrid-auto-engine`
und `vlm-auto-engine` sind Legacy-Aliase für `hybrid-engine`/`vlm-engine`):

| Backend | Min VRAM | CPU-only | OmniDocBench v1.6 E2E Overall | Lädt |
|---------|----------|----------|-------------------------------|------|
| `pipeline` | **4 GB** (GPU optional) | ✅ | **86.47** | CV-Stack (DocLayout+OCR+Formula+Table) |
| `hybrid-engine` (default) | **8 GB** (16 GB+ empf.) | ❌ | **95.26** medium / **95.39** high | VLM **+** Pipeline gleichzeitig |
| `vlm-engine` | **8 GB** (~4–5 GB real) | ❌ | **95.30** | nur MinerU2.5-1.2B |
| `*-http-client` | **2 GB** (Client) | ✅ Client | wie Server | Server hält VLM |

VRAM-Tuning: `MINERU_VIRTUAL_VRAM_SIZE`, `MINERU_HYBRID_BATCH_RATIO`,
vLLM `--gpu-memory-utilization`. Hybrid lädt VLM + mehrere Pipeline-Modelle → daher 16 GB+
trotz offiziell 8 GB Minimum.

**olmOCR Detail** ([README](https://github.com/allenai/olmocr),
[Model-Card](https://huggingface.co/allenai/olmOCR-2-7B-1025)):
- Default-Checkpoint: `allenai/olmOCR-2-7B-1025-FP8` (vLLM nötig für echtes FP8).
- README: ≥12 GB (getestet RTX 4090, L40S, A100, H100). `olmocr/check.py` blockt teils <15 GB.
- Praxis: 12 GB nur mit `--max-model-len 4096 --gpu-memory-utilization 0.75 --max-num-seqs 1`.
  16 GB komfortabel FP8, 24 GB für BF16.
- Externer Server: `vllm serve allenai/olmOCR-2-7B-1025-FP8 --max-model-len 16384`.

**Surya 2 Detail** ([Release v0.20.0](https://github.com/datalab-to/surya/releases/tag/v0.20.0)):
- Auto-Backend: NVIDIA → vLLM, sonst llama.cpp. GGUF-Variante für Apple/CPU.
- Throughput: 5.35 pages/s auf RTX 5090 @ concurrency 128; Apple M1 ~0.108 pages/s.
- `DETECTOR_BATCH_SIZE` (torch-Detector, separat) Default CUDA 36 → bei OOM senken.
- vLLM auto-tuned per `VLLM_GPU_TYPE` (Baseline 24 GB = 4090).

**Granite-Docling Detail** ([HF](https://huggingface.co/ibm-granite/granite-docling-258M),
[IBM Docker](https://hub.docker.com/r/ai/granite-docling)):
- 258M VLM (SigLIP2 + Granite 165M), Gewichte FP16 ~0.86 GiB, Q8 ~0.72 GiB.
- Standard-Pipeline VRAM ist **batch-getrieben** (~1 GB → ~21 GB bei batch 256 auf 24 GB L4).
- VLM via vLLM nutzt `--gpu-memory-utilization 0.9` → 12–32 GB je nach Concurrency.

### 2.2 Kein / minimaler GPU-Bedarf

| Repo | VRAM | Modell / Methode | LLM? |
|------|------|------------------|------|
| **markitdown** | **0 GB** (Basis) | pdfplumber/pdfminer; OCR-Plugin nutzt **GPT-4o** (API) oder Tesseract/GLM-OCR | optional, API |
| **PyMuPDF / pymupdf4llm** | **0 GB** | Regelbasiert + ONNX-OCR | nein |
| **tabula-java** | **0 GB** | Tabellen-Heuristik (Java) | nein |
| **camelot** | **0 GB** | Tabellen-Heuristik (Lattice/Stream) | nein |
| **pdfplumber** | **0 GB** | Text/Table-Extraktion | nein |
| **pandoc** | **0 GB** | Format-Konvertierung | nein |
| **html2text / turndown / node-html-markdown / markdownify / mdream / html-to-markdown (go/py)** | **0 GB** | HTML→MD Parser | nein |
| **grobid** | **0 GB GPU** | CRF/DeepLearning (Java), ~4–8 GB **RAM**, GPU optional | nein (eigene ML) |
| **firecrawl** | **0 GB lokal** | Cloud-Crawler + optional LLM-Extraktion | optional, API |
| **opendataloader-pdf** | **0 GB** (heuristisch) | Pipeline, Triage | nein |

---

## 3. Hybrid-Repos im Detail (welche Modelle empfohlen werden)

"Hybrid" hat zwei Bedeutungen, die in den Repos vorkommen:

1. **Hybrid-Konvertierung** = CV/Pipeline **+** LLM/VLM kombiniert (mehr Genauigkeit).
2. **Hybrid-QA** (Whisker-relevant) = exakte Goldens **+** fuzzy Metriken (siehe redteam/pandoc.md, html2text.md, node-html-markdown.md).

### 3.1 Hybrid-Konvertierung

| Repo | Architektur | Modelle | Accuracy (OmniDocBench) |
|------|-------------|---------|-------------------------|
| **MinerU `hybrid-engine`** (default) | VLM + Pipeline-Sidecars parallel | MinerU2.5-1.2B + PP-DocLayoutV2 + PP-OCRv6 + UniMERNet | **95.26** (medium) / **95.39** (high) |
| **MinerU `pipeline`** | Reiner CV-Stack ohne VLM | Layout + OCR + Formula + Table | **86.47** |
| **MinerU `vlm-engine`** | Nur VLM | MinerU2.5-1.2B | **95.30** |
| **marker + `--use_llm`** | Surya lokal + **Gemini Flash** für Tabellen/Math/Forms | CV lokal + Cloud-LLM | marker+LLM > marker solo > Gemini solo (marker-Benchmarks) |
| **docling standard** | Heron + TableFormer + OCR (Multi-Specialist) | spezialisierte Modelle | ~88% F1 |
| **docling VLM** | Single Granite-Docling-258M end-to-end | 258M VLM | VLM-Pfad |
| **Dolphin-v2** | 1 VLM, 2 Stages (analyze→parse), doc-type-routing | Qwen2.5-VL-3B | **89.78** overall |
| **PDF-Extract-Kit** | Modell-Toolbox (Layout+Formula+OCR+Table) | DocLayout-YOLO, UniMERNet, PaddleOCR, LayoutLMv3 | — (E2E via MinerU) |

Dolphin-Routing-Detail: digital-born → element-weise parallele Anchor-Prompts
("Parse the table…", "Read formula…"); fotografiert/verzerrt → holistischer Full-Page-Pass
(`check_bbox_overlap` IoU 0.1 / overlap 0.25). Danach **deterministisches** Post-Processing
(LaTeX-Canon, Repeat-Truncation, Table-HTML-Strip) — kein zweites Modell.

### 3.2 Hybrid-QA (das Muster, das Whisker bereits empfiehlt)

Aus `research/redteam/`: pandoc, html2text, node-html-markdown zeigen alle dasselbe
Muster — **exakte Goldens auf Micro-Corpus + fuzzy Metriken auf großem Corpus**.
Whisker setzt das in drei Lanes um (Stability/Fidelity/Comprehension).

---

## 4. Whisker-Test-Plan: Welche Modelle gegen den WG21-Corpus benchen?

Whisker misst pro Paper: **nid** (Text-Fidelity, reflow-tolerant), **teds** (Tabellen),
**mhs** (Heading-Hierarchie), **content_recall** (fehlende Sektionen), advisory
**grits_con**/**reading_order** — plus Lane-3 **Facts** (`table`/`math`, human-verified).
Workflow: Converter-Output als `<pid>.md` in paperstore stagen → `whisker bench` +
`whisker facts` gegen `<pid>.gt.md` / `<pid>.facts.jsonl` im Corpus.

### 4.1 Fünf empfohlene Configs (mit VRAM)

| # | Config | Stack | VRAM | API? | Primäre Whisker-Achsen |
|---|--------|-------|------|------|------------------------|
| **A** | MinerU pipeline | `opendatalab/MinerU` `-b pipeline` | **4 GB** | Nein | nid, content_recall |
| **B** | MinerU VLM | MinerU2.5-1.2B via `vlm-engine` | **8 GB** (16 komfortabel) | Nein | teds, math facts |
| **C** | marker solo | Surya layout+OCR, `--use_llm` off | **3–5 GB**/Worker | Nein | teds, mhs |
| **D** | marker + Gemini | marker lokal + `gemini-2.0-flash` (`--use_llm`) | **3–5 GB** lokal + Cloud | **Ja** | teds, table facts, cross-page tables |
| **E** | markitdown + Qwen3-32B | markitdown extract → vLLM-Cleanup-Pass | **0 + ~18–24 GB** (AWQ 4-bit ~18 GB) | Nein (self-hosted) | nid vs GT, mhs-repair, heading fixes |

Optional: **Docling** (tabellenstark), **olmOCR** (Comprehension-Anchor wie Whisker facts,
einmal laufen lassen zur Validierung).

**Modell-Souveränität** (CLAUDE.md): Config E mit lokalem Qwen3-32B / Gemma-3-27B @ temp 0
ist die souveränitäts-konforme Variante. Cloud-Gemini (D) ist Vergleichs-Ceiling, nicht Produktionsziel.

### 4.2 Bench-Kommando-Form (PowerShell, aus repo root)

```powershell
$env:WG21_DATA_DIR = "C:\Users\sabog\Desktop\cppalliance\cppalliance\data"
# Nachdem jeder Converter-Output als paperstore/<pid>.md gestaged wurde:
uv run --package whisker whisker bench  --corpus packages/whisker/corpus --out whisker/bench-mineru-vlm.json
uv run --package whisker whisker facts  --corpus packages/whisker/corpus
uv run --package whisker whisker guard  --corpus packages/whisker/corpus --baseline whisker/bench-mineru-vlm.json
```

Im Baseline-JSON `backend`, Modellname und Parse-Flags mit-speichern (Redteam-Lücke:
guard-Baselines speichern aktuell nur Metriken, nicht die Scorer-Config).

### 4.3 Corpus-Stratifizierung (min. 25 Papers, aus persona/26-corpus-data-strategist)

| Stratum | n | Beispiele |
|---------|---|-----------|
| Table-heavy | 8 | P4182R0 (im Corpus), Feature-Test-Tabellen, Straw-Polls |
| Math/Code-heavy | 4 | P4185R0 (`math` facts), Grammar-Papers |
| Wording/ins-del | 5 | P3941R2-Klasse |
| Multi-column reflow | 4 | hoher `unigram−coverage`-Gap |
| Prose-only admin | 4 | Minutes, Telecon-Notes |

Facts **aus dem SOURCE-PDF/HTML** authoren, nicht aus Converter-Output (Provenance-Regel).

### 4.4 Auswertungsregeln

- **Nicht** auf `overall` ranken (Nougat/Unstructured-Lektion). Strata getrennt reporten.
- Gate: `content_recall`-Floor (0.90 provisorisch), per-paper `teds`/`mhs` wo GT Tabellen/Headings hat, Lane-3 Facts-Pass-Rate.
- Sanity-Floors (opendataloader-Präzedenz): NID ≥ 0.88, TEDS ≥ 0.47, MHS ≥ 0.72 (Corpus-Mittel als Backstop).
- Erwartetes WG21-Muster: hoher nid + hoher content_recall, aber **table facts FAIL** (Reflow sieht gut aus, Zelle falsch) — genau der Grund, warum Lane-3 Facts existieren.

---

## 5. Hardware-Entscheidungsbaum (Antwort auf "Wie viele GB?")

### Frage 1: API oder lokale GPU?

| Ziel | Antwort |
|------|---------|
| LangExtract schnell testen | **0 GB** — Gemini API (`gemini-3.5-flash`) |
| LangExtract lokal/offline | **8 GB** GPU (gemma2:2b ~3 GB); **16 GB** für 7B |
| PDF→MD-Bench mit Whisker | Whisker **0 GB**; Converter separat budgetieren |
| Günstigster PDF-Bench lokal | **8 GB**: MinerU pipeline / marker (1 Worker) |
| Beste PDF-Qualität lokal | **16–24 GB**: MinerU VLM / olmOCR FP8 |
| Hybrid Top-Qualität (MinerU default) | **16 GB+** |
| Keine GPU | MinerU `-b pipeline`, markitdown, pymupdf4llm — CPU, langsamer |

### Frage 2: Budget-Profile

**Profil A — keine GPU (CPU + Cloud):**
LangExtract → Gemini API · markitdown → PDF text · Whisker → QA. Alles **0 GB**.

**Profil B — 8 GB GPU (RTX 4060/4070):**
LangExtract Ollama `gemma2:2b` (~3 GB) · MinerU `-b pipeline` (~4 GB) · marker solo 1 Worker (~5 GB) · Whisker 0 GB.
**Ein Converter zur Zeit**, nicht alles parallel.

**Profil C — 24 GB GPU (RTX 4090):**
MinerU VLM/hybrid · olmOCR FP8 · marker multi-worker · Dolphin-v2 · LangExtract bis ~12B lokal · Whisker 0 GB.

**Profil D — 48 GB (A6000/L40S):**
Parallel-Bench aller Configs A–E.

---

## 6. Quellen (verifiziert 2026-06-29)

- LangExtract: https://github.com/google/langextract (README, Quick Start, Ollama-Sektion)
- Gemma-2-2B VRAM: https://llmrun.dev/model/google-gemma-2-2b
- marker: https://github.com/VikParuchuri/marker (README, "5GB peak / 3.5GB avg per worker"); PyPI marker-pdf
- MinerU: https://github.com/opendatalab/MinerU (README-Hardware-Tabelle, Quick Start); User-Guide-PDF
- docling / Granite-Docling: https://huggingface.co/ibm-granite/granite-docling-258M; https://hub.docker.com/r/ai/granite-docling; docling GPU-Docs
- olmOCR: https://github.com/allenai/olmocr (README); https://huggingface.co/allenai/olmOCR-2-7B-1025; Issues #201, #424
- Surya 2: https://github.com/datalab-to/surya/releases/tag/v0.20.0; PyPI surya-ocr; datalab.to/blog/surya-2
- PDF-Extract-Kit: https://github.com/opendatalab/PDF-Extract-Kit (Install-Docs, "8GB min / 16GB preferred")
- markitdown: https://github.com/microsoft/markitdown (README, markitdown-ocr README)
- Dolphin: https://github.com/bytedance/Dolphin; arXiv:2505.14059; https://huggingface.co/ByteDance/Dolphin-v2
- Whisker intern: `research/redteam/*.md`, `research/persona/00-EVIDENCE-BASELINE.md`, `research/comprehension-poc-report.md`

---

## 7. TL;DR für den Gesprächspartner

> Kommt drauf an, ob **API oder lokale GPU**. Mit Cloud-API (Gemini/OpenAI): **0 GB VRAM**.
> LangExtract lokal mit Ollama: ab **~4 GB**, empfohlen **8 GB**. PDF-Konverter lokal: **8 GB**
> für den Einstieg (MinerU pipeline / marker), **16–24 GB** für VLM-Qualität (MinerU VLM,
> olmOCR). **Whisker selbst braucht keine GPU** — es ist nur ein deterministisches QA-Tool
> auf fertigem Markdown.
