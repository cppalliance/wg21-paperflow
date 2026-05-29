# Research: Open-Source PDF/Dokument-Extraktoren für Tabellen

**Datum:** 2026-05-21
**Kontext:** tomd Multi-Line-Cell-Problem; Evaluierung aller verfügbaren Open-Source-Alternativen
**Ergebnis:** Docling Cell Enrichment bleibt der richtige Fit (MIT, lokal, ~258M Modell). Phase 9 BBox-Fix entblockt die Integration.

---

## Verdict für tomd

Camelot, pdfplumber, Tabula — alle scheitern an Multi-Line-Zellen (gleiche Row-Boundary-Schwäche: jede y-Zeile = neue Tabellenzeile). Nur ML-Tools lösen das zuverlässig über visuelle Cell-Extent-Erkennung. Docling (MIT, lokal, CPU-fähig) passt zur tomd-Architektur: Rule-based Detection bleibt Master, Docling liefert nur das Zellgitter.

---

## 1. End-to-End PDF → Markdown Pipelines

| Tool | Stars | Lizenz | Ansatz | Multi-Line | GPU | Link |
|---|---|---|---|---|---|---|
| MinerU | 64k | Apache-basiert | Layout ML + VLM | Ja (HTML, cross-page) | Empfohlen | https://github.com/opendatalab/MinerU |
| Docling | 60k | MIT | TableFormer + Layout | Ja | Optional | https://github.com/docling-project/docling |
| Marker | 35k | GPL-3.0 | Surya + Heuristics + LLM | Ja | Optional | https://github.com/datalab-to/marker |
| DeepSeek-OCR | 23.2k | MIT | VLM "optical compression" | Ja | Ja | https://github.com/deepseek-ai/DeepSeek-OCR |
| OpenDataLoader PDF | 21k | Apache-2.0 | Java Hybrid + AI Backend | Ja (0.928 TEDS) | Optional | https://github.com/opendataloader-project/opendataloader-pdf |
| Surya | 19.8k | GPL-3.0 | Multi-task DL (OCR+Layout+Table) | Partial | Empfohlen | https://github.com/datalab-to/surya |
| olmOCR | 17.3k | Apache-2.0 | 7B VLM (Qwen2-VL) | Ja | Ja | https://github.com/allenai/olmocr |
| Unstructured | 14.8k | Apache-2.0 | YOLOX + Table Transformer | Partial | Optional | https://github.com/Unstructured-IO/unstructured |
| Zerox | 12.2k | MIT | Vision-LLM pro Seite | Partial | API-basiert | https://github.com/getomni-ai/zerox |
| PDF-Extract-Kit | 9.7k | AGPL-3.0 | Modular ML Toolkit | Partial | Optional | https://github.com/opendatalab/PDF-Extract-Kit |
| Dolphin (ByteDance) | 9k | Apache-2.0 | 2-stage VLM (analyze-then-parse) | Ja | Ja | https://github.com/bytedance/Dolphin |
| dots.ocr (Xiaohongshu) | 8.8k | MIT | 1.7B unified VLM | Ja | Ja | https://github.com/rednote-hilab/dots.ocr |
| Kreuzberg | 8.4k | Elastic-2.0 | Rust + OCR + optional VLM | Ja | Optional | https://github.com/kreuzberg-dev/Kreuzberg |
| GOT-OCR2 | 8.1k | Apache-2.0 | 580M unified OCR-2.0 | Partial | Ja | https://github.com/Ucas-HaoranWei/GOT-OCR2.0 |
| MegaParse | 7.4k | Apache-2.0 | Multi-format; Vision Variant | Ja | Optional | https://github.com/QuivrHQ/MegaParse |
| OmniParse | 6.8k | GPL-3.0 | Local multimodal ingest | Ja | Ja | https://github.com/adithya-s-k/omniparse |
| MonkeyOCR | 6.6k | Apache-2.0 | Structure-Recog-Relation LMM | Ja | Ja | https://github.com/Yuliang-Liu/MonkeyOCR |
| GLM-OCR | 6.6k | Apache-2.0 | 0.9B unified OCR | Ja | Ja | https://github.com/zai-org/GLM-OCR |
| DocTR (Mindee) | 6.1k | Apache-2.0 | 2-stage OCR (det+rec) | Nein | Optional | https://github.com/mindee/doctr |
| LayoutParser | 5.7k | Apache-2.0 | Detectron2 Layout Detection | Partial | Empfohlen | https://github.com/Layout-Parser/layout-parser |
| LiteParse | 5.2k | Apache-2.0 | pdf.js + Tesseract | Partial | Nein | https://github.com/run-llama/liteparse |
| GROBID | 4.9k | Apache-2.0 | ML (CRF/DL) → TEI XML | Partial | Optional | https://github.com/grobidOrg/grobid |
| DocETL | 3.8k | MIT | LLM YAML ETL Pipeline | Via Parser | Optional | https://github.com/ucbepic/docetl |
| DeepDocTection | 3.2k | Apache-2.0 | Detectron2 + Transformers | Ja | Optional | https://github.com/deepdoctection/deepdoctection |
| Open-Parse | 3.2k | MIT | Visual Layout + RAG Chunking | Partial | Nein | https://github.com/Filimoa/open-parse |
| text-extract-api | 3.1k | MIT | FastAPI + Marker/EasyOCR | Via Marker | Optional | https://github.com/CatchTheTornado/text-extract-api |
| Pix2Text | 3.1k | MIT | Small CV: Layout+Table+Formula | Partial | Optional | https://github.com/breezedeus/Pix2Text |
| NeMo Retriever (NVIDIA) | 2.9k | Apache-2.0 | Microservices + OCR | Ja | Ja | https://github.com/NVIDIA/NeMo-Retriever |
| Chunkr | 2.9k | AGPL-3.0 | Rust Layout+OCR | Ja | Optional | https://github.com/lumina-ai-inc/chunkr |
| mPLUG-DocOwl | 2.4k | Apache-2.0 | Modular Doc MLLM | Ja | Ja | https://github.com/X-PLUG/mPLUG-DocOwl |
| NanoNets docext | 2.0k | — | On-prem OCR-free | Ja | Optional | https://github.com/NanoNets/docext |
| Extractous | 1.8k | Apache-2.0 | Rust Core, schnell | Nein | Nein | https://github.com/yobix-ai/extractous |
| MarkPDFdown | 1.7k | Apache-2.0 | VLM multi-provider | Ja | API | https://github.com/MarkPDFdown/markpdfdown |
| pymupdf4llm | 1.7k | AGPL-3.0 | PyMuPDF → Markdown | Partial | Nein | https://github.com/pymupdf/PyMuPDF4LLM |
| DocStrange (NanoNets) | 1.5k | — | 7B VLM Hybrid | Ja | Optional | https://github.com/NanoNets/docstrange |
| HunyuanOCR (Tencent) | 1.6k | Tencent Open | 1B VLM, 100+ Sprachen | Ja | Ja | https://github.com/Tencent-Hunyuan/HunyuanOCR |
| OpenDoc-0.1B (Fudan) | 1.4k | Apache-2.0 | Ultra-light 0.1B Parser | Ja | Ja | https://github.com/Topdu/OpenOCR |
| HURIDOCS Layout | 1.1k | Apache-2.0 | VGT/LightGBM + OCR | Ja (HTML) | Optional | https://github.com/huridocs/pdf-document-layout-analysis |
| Kordoc | 955 | MIT | Korean HWP/PDF/DOCX→MD | Partial | Nein | https://github.com/chrisryugj/kordoc |
| img2table | 864 | MIT | OpenCV + OCR | Ja (merged cells) | Nein | https://github.com/xavctn/img2table |
| Dedoc (ISP RAS) | 701 | Apache-2.0 | Hybrid ML+Rules | Ja | Optional | https://github.com/ispras/dedoc |
| Vision Parse | 475 | MIT | VLM (OpenAI/Gemini/Ollama) | Partial | API/Local | https://github.com/iamarunbrahma/vision-parse |
| RapidDoc | 156 | Apache-2.0 | MinerU-fork; ONNX | Partial | Optional | https://github.com/RapidAI/RapidDoc |
| Markdrop | 204 | GPL-3.0 | Docling + Table Transformer | Ja | Optional | https://github.com/shoryasethia/markdrop |
| pdfmux | 64 | — | Multi-Backend Router | Partial | Nein | https://github.com/NameetP/pdfmux |

---

## 2. Vision Language Models (VLMs) für Dokumente

| Modell | Parameter | Lizenz | Tabellen | GPU | Link |
|---|---|---|---|---|---|
| PaddleOCR-VL-1.5 | 0.9B | Apache-2.0 | SOTA, cross-page merge | Ja | https://github.com/PaddlePaddle/PaddleOCR |
| Granite-Docling-258M | 258M | Apache-2.0 | DocTags nativ | 4-8 GB | https://huggingface.co/ibm-granite/granite-docling-258M |
| SmolDocling-256M | 256M | CDLA-Permissive | DocTags | 4-8 GB | https://huggingface.co/docling-project/SmolDocling-256M-preview |
| Nemotron Parse v1.2 | 936M | NVIDIA Open | BBox + MD Tables | 8-12 GB | https://huggingface.co/nvidia/NVIDIA-Nemotron-Parse-v1.2 |
| StructTable-InternVL2-1B | ~0.9B | Apache-2.0 | Table→LaTeX/HTML/MD | ~8 GB | https://huggingface.co/InternScience/StructTable-InternVL2-1B |
| GOT-OCR2_0 | 716M | Apache-2.0 | Format-Mode MD | 2-4 GB | https://huggingface.co/stepfun-ai/GOT-OCR2_0 |
| MinerU2.5/Pro | 1.2B | Apache-basiert | Pipeline VLM | 8-12 GB | https://github.com/opendatalab/MinerU |
| Dolphin-v2 | 3B | Apache-2.0 | Analyze-then-parse | 12-16 GB | https://github.com/bytedance/Dolphin |
| mPLUG-DocOwl2 | 8.6B | Apache-2.0 | Multi-page OCR-free | 16-24 GB | https://huggingface.co/mPLUG/DocOwl2 |
| Qwen2.5-VL | 3B-72B | Apache-2.0 | Prompt-basiert | 16-multi | https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct |
| InternVL2/3.5 | 1B-108B | MIT | Via StructTable | 8-24 GB+ | https://github.com/OpenGVLab/InternVL |
| Phi-3.5/4 Vision | 4-15B | MIT | Prompt-basiert | 10-32 GB | https://huggingface.co/microsoft/Phi-3.5-vision-instruct |
| Granite-Vision 4.0-3B | 3B | Apache-2.0 | Extended extraction | 10-12 GB | https://www.ibm.com/granite/docs/models/vision |
| Donut | 143M | MIT | Fine-tune nötig | 4-8 GB | https://github.com/clovaai/donut |
| Nougat | 350M | MIT | LaTeX (schwach bei Tabellen) | ~8 GB | https://github.com/facebookresearch/nougat |
| Pix2Struct | 282M-1.1B | Apache-2.0 | Via Fine-tune | ~8 GB | https://huggingface.co/google/pix2struct-base |
| LayoutLMv3 | 125M | CC-BY-NC-SA | Needs OCR + Head | ~4 GB | https://huggingface.co/microsoft/layoutlmv3-base |

---

## 3. Tabellen-spezifische ML-Modelle (atomare Bausteine)

| Modell | Architektur | TEDS | Spanning Cells | Gewichte | Link |
|---|---|---|---|---|---|
| TableFormer (Docling) | Transformer OTSL | 98.5/95 | Ja | HuggingFace | https://github.com/docling-project/docling-ibm-models |
| TableFormerV2 | Updated decoder | Verbessert | Ja | HuggingFace | https://huggingface.co/docling-project/TableFormerV2 |
| Table Transformer (TATR) | DETR R18 | GriTS 0.985 | Ja | HuggingFace | https://github.com/microsoft/table-transformer |
| UniTable | VQ-VAE + LM | SOTA 4 Bench | Ja | HuggingFace | https://github.com/poloclub/unitable |
| SLANet/SLANeXt (Paddle) | PP-LCNet + SLA | CPU-friendly | Ja | Paddle | https://github.com/PaddlePaddle/PaddleOCR |
| TableMASTER | MASTER+PSENet | 96.76 | Ja | Repo | https://github.com/JiaquanYe/TableMASTER-mmocr |
| LORE (Alibaba DAMO) | CenterNet Regression | WTW stark | Ja | Google Drive | https://github.com/AlibabaResearch/AdvancedLiterateMachinery |
| CascadeTabNet | Cascade R-CNN | ICDAR-Sieger | Ja | Repo | https://github.com/DevashishPrasad/CascadeTabNet |
| LGPMA | Pyramid Masks | 96.7 | Ja | DAVAR | https://github.com/hikopensource/DAVAR-Lab-OCR |
| SEM/SEMv2 | Split-Embed-Merge | 97.11 F1 | Ja | Train | https://github.com/ZZR8066/SEMv2 |
| MTL-TabNet | Multi-Task MMOCR | FinTab SOTA | Ja | Pretrained | https://github.com/namtuanly/MTL-TabNet |
| TDATR (2026) | Perceive-Fuse | 7 Bench SOTA | Ja | HuggingFace | https://github.com/Chunchunwumu/TDATR |
| MuTabNet | Hierarchical Transformer | ICDAR 2024 | Ja | Releases | https://github.com/JG1VPP/MuTabNet |
| StructEqTable | InternVL2-1B | Komplex-Header | Ja | HuggingFace | https://github.com/UniModal4Reasoning/StructEqTable-Deploy |
| Surya TableRec | Dedicated Model | Marker-intern | rowspan/colspan | Auto-DL | https://github.com/datalab-to/surya |
| RapidTable | Multi-Backend ONNX | Variabel | Backend-abhängig | Bundled | https://github.com/RapidAI/RapidTable |
| TableStructureRec | Curated ONNX Zoo | TEDS-ranked | Wired+Lineless | ONNX | https://github.com/RapidAI/TableStructureRec |
| TGRNet | CNN + GNN | ICCV 2021 | Ja | Checkpoints | https://github.com/xuewenyuan/TGRNet |
| TabStruct-Net | Mask R-CNN | ~90.1 | Ja | Google Drive | https://github.com/sachinraja13/TabStructNet |
| SPLERGE | Dual FCN split+merge | ICDAR 2013 | Ja | Partial | https://github.com/pyxploiter/deep-splerge |

---

## 4. Rule-Based Libraries (kein ML, kein GPU)

| Tool | Stars | Lizenz | Methode | Multi-Line | Link |
|---|---|---|---|---|---|
| pdfplumber | 10.3k | MIT | Line/Rect + Text-Cluster | Partial | https://github.com/jsvine/pdfplumber |
| PyMuPDF (`find_tables`) | 9.8k | AGPL | Vector lines/text grid | Partial | https://github.com/pymupdf/PyMuPDF |
| pypdf | 10k | BSD-3 | PDF-Objekte (keine Tabellen!) | N/A | https://github.com/py-pdf/pypdf |
| pdfminer.six | 7k | MIT | Layout-Parser (keine Tabellen!) | N/A | https://github.com/pdfminer/pdfminer.six |
| Camelot | 3.7k | MIT | Lattice (OpenCV) / Stream | Partial | https://github.com/camelot-dev/camelot |
| borb | 3.6k | AGPL | Line-Intersection | Partial | https://github.com/borb-pdf/borb |
| pdf2docx | 3.4k | MIT | PyMuPDF Regeln → DOCX | Ja | https://github.com/ArtifexSoftware/pdf2docx |
| tabula-py | 2.3k | MIT | Lattice/Stream (Java) | Partial | https://github.com/chezou/tabula-py |
| img2table | 864 | MIT | OpenCV + OCR | Ja (merged) | https://github.com/xavctn/img2table |
| pypdfium2 | 770 | Apache/BSD | PDFium Bindings | Nein | https://github.com/pypdfium2-team/pypdfium2 |
| pdfquery | 780 | MIT | XPath/CSS Selectors | Nein | https://github.com/jcushman/pdfquery |
| pdftext | 688 | Apache-2.0 | pypdfium2 structured blocks | Nein | https://github.com/datalab-to/pdftext |
| Apache PDFBox | 3.1k | Apache-2.0 | Java PDF Toolkit | Partial | https://github.com/apache/pdfbox |
| Apache Tika | 3.8k | Apache-2.0 | Universal Text Extractor | Nein | https://github.com/apache/tika |
| Extractous | 1.8k | Apache-2.0 | Rust Core | Nein | https://github.com/yobix-ai/extractous |
| FibrumPDF | 107 | — | Go Engine | Partial | https://github.com/intercepted16/fibrumpdf |
| pdfalto | — | GPL-2.0 | PDF → ALTO XML | N/A | https://github.com/kermitt2/pdfalto |
| Poppler/pdftotext | — | GPL-2.0 | C CLI text extraction | N/A | https://poppler.freedesktop.org/ |
| Xpdf (`-table` mode) | — | GPL-2.0 | Plain-text column alignment | Partial | https://www.xpdfreader.com/ |

---

## 5. Chinesische/Asiatische Ökosysteme

| Tool | Stars | Lizenz | Spezialität | Link |
|---|---|---|---|---|
| PaddleOCR (Baidu) | 78.3k | Apache-2.0 | PP-StructureV3 + VL-1.5 | https://github.com/PaddlePaddle/PaddleOCR |
| RAGFlow (Infiniflow) | 81k | Apache-2.0 | DeepDoc + External Parsers | https://github.com/infiniflow/ragflow |
| RapidOCR | 6.6k | Apache-2.0 | ONNX Cross-Platform OCR | https://github.com/RapidAI/RapidOCR |
| RapidTable | 422 | Apache-2.0 | Table→HTML (SLANet/UniTable) | https://github.com/RapidAI/RapidTable |
| TableStructureRec | 951 | Apache-2.0 | Best-of-breed Modell-Zoo | https://github.com/RapidAI/TableStructureRec |
| AdvancedLiterateMachinery (Alibaba) | 1.8k | Apache-2.0 | LORE, DocXChain, OmniParser | https://github.com/AlibabaResearch/AdvancedLiterateMachinery |
| mPLUG-DocOwl (Alibaba DAMO) | 2.4k | Apache-2.0 | Modular Doc MLLM | https://github.com/X-PLUG/mPLUG-DocOwl |
| Qwen2.5-VL (Alibaba Cloud) | 19.2k | Apache-2.0 | General VLM Doc Parse | https://github.com/QwenLM/Qwen2.5-VL |
| InternVL (Shanghai AI Lab) | 10k | MIT | GPT-4o-class open VLM | https://github.com/OpenGVLab/InternVL |
| OpenDoc-0.1B (Fudan) | 1.4k | Apache-2.0 | Ultra-light Parser | https://github.com/Topdu/OpenOCR |
| HunyuanOCR (Tencent) | 1.6k | Tencent Open | 1B VLM, 100+ Sprachen | https://github.com/Tencent-Hunyuan/HunyuanOCR |
| DeepSeek-OCR | 23.2k | MIT | VLM "optical compression" | https://github.com/deepseek-ai/DeepSeek-OCR |
| Dolphin (ByteDance) | 9k | Apache-2.0 | Analyze-then-parse VLM | https://github.com/bytedance/Dolphin |
| dots.ocr (Xiaohongshu/RED) | 8.8k | MIT | 1.7B unified layout parser | https://github.com/rednote-hilab/dots.ocr |
| GOT-OCR2 (StepFun/UCAS) | 8.1k | Apache-2.0 | Unified OCR-2.0 Model | https://github.com/Ucas-HaoranWei/GOT-OCR2.0 |
| Qianfan-OCR (Baidu) | 396 | — | 4B Layout-as-Thought | https://github.com/baidubce/Qianfan-VL |

---

## 6. Neueste Tools 2025-2026

| Tool | Stars | Ansatz | Besonderheit | Link |
|---|---|---|---|---|
| Crawl4AI | 66k | Web Crawler + PDF | PDF Strategies | https://github.com/unclecode/crawl4ai |
| RAGFlow | 81k | RAG + DeepDoc | Plugin-Architecture | https://github.com/infiniflow/ragflow |
| Fire-PDF (Firecrawl) | — | Rust PDF Engine | 3.5-5.7× schneller | https://www.firecrawl.dev/changelog |
| NeMo Retriever | 2.9k | NVIDIA Microservices | Scalable Production | https://github.com/NVIDIA/NeMo-Retriever |
| Nemotron Parse v1.2 | — | 936M spatial VLM | May 2026 | https://huggingface.co/nvidia/NVIDIA-Nemotron-Parse-v1.2 |
| PaddleOCR-VL-1.5 | — | 0.9B Multi-task | Jan 2026, SOTA | https://github.com/PaddlePaddle/PaddleOCR |
| MinerU 3.1 | 64k | License change + VLM | Apr 2026 | https://github.com/opendatalab/MinerU |
| DeepSeek-OCR-2 | neu | Visual Causal Flow VLM | Jan 2026, MIT | https://github.com/deepseek-ai/DeepSeek-OCR |
| Qianfan-OCR | 396 | 4B Layout-as-Thought | #1 OmniDocBench v1.5 | https://github.com/baidubce/Qianfan-VL |
| pdfmux | 64 | Multi-Backend Router | Self-healing Fallback | https://github.com/NameetP/pdfmux |
| Granite-Docling-258M | — | IBM compact VLM | Sep 2025 | https://huggingface.co/ibm-granite/granite-docling-258M |
| LightOnOCR-2-1B | — | End-to-end page→text | Jan 2026 | https://huggingface.co/lightonai/LightOnOCR-2-1B |
| Nanonets-OCR2-3B | — | 3B image→MD | Jun 2025 | https://huggingface.co/nanonets/Nanonets-OCR2-3B |

---

## 7. Benchmarks & Evaluation

| Benchmark | Fokus | Link |
|---|---|---|
| OmniDocBench v1.5/v1.6 | CVPR'25 Standard; TEDS, md2md | https://github.com/opendatalab/OmniDocBench |
| PubTables-1M | Table detection/structure | https://github.com/microsoft/table-transformer |
| FinTabNet | Financial tables | (via TATR/GTE papers) |
| SciTSR | Scientific table structure | https://github.com/Academic-Hammer/SciTSR |
| WTW | Wired tables in the wild | https://github.com/wangwen-whu/WTW-Dataset |
| opendataloader-bench | 200 real-world PDFs | https://opendataloader.org/docs/benchmark |

---

## 8. Key Patterns für tomd

### Was ML-Tools anders machen bei Multi-Line-Zellen

Rule-based Tools (Camelot, pdfplumber, Tabula, tomd Pass 1-4) behandeln jede y-Zeile als neue Tabellenzeile. ML-Tools erkennen **Cell-Extent visuell** aus dem gerenderten Bild:

1. **Docling TableFormer**: Predicts OTSL cell tokens inkl. `lcel`/`ucel`/`xcel` für Spanning
2. **Marker/Surya**: Image-basierte Cell-Polygone + IoA Text-Zuordnung
3. **MinerU**: StructEqTable + cross-page merge Logik
4. **OpenDataLoader**: Conservative Page-Triage → escalate nur bei low-confidence

### Convergente Muster 2025-2026

1. **Hybrid ist Standard**: Schnelle lokale Heuristik + optionales ML nur für harte Seiten
2. **HTML als Table-IR**: MinerU, Unstructured, OpenDataLoader emittieren HTML für komplexe Tabellen
3. **Nie Newlines in Merge-Phase strippen** (MinerU Bug #4128 als Warnung)
4. **Tiered Escalation**: Cheap path first (rule-based), ML nur wenn nötig
5. **Sub-1B spezialisierte VLMs** schlagen generische 7B+ für deterministische Extraktion

### Warum Docling für tomd

| Kriterium | Docling | Marker | MinerU | Unstructured |
|---|---|---|---|---|
| Lizenz | **MIT** | GPL-3.0 | AGPL-basiert | Apache-2.0 |
| Cell-Grid API | **Ja (table.data)** | Nur MD | HTML/JSON | Element stream |
| Hybrid-fähig (Grid only) | **Ja** | Nein (full pipeline) | Nein | Nein |
| CPU-fähig | **Ja** | Ja | Empfohlen GPU | Optional |
| Span-Erhaltung (PyMuPDF) | **Ja (Architektur)** | Verliert Spans | Verliert Spans | Verliert Spans |
| Determinismus | **Ja** | Nein (LLM-Mode) | VLM-Varianz | Variabel |

---

## 9. Docling-Integration Status (tomd)

- **Code vorhanden**: `docling_backend.py`, `pipeline.py` Hook (L415-422)
- **Blocker**: Phase 9 — gemischte `coord_origin` (BOTTOMLEFT vs TOPLEFT) in DoclingDocument
- **Fix**: `to_top_left_origin(page_height)` + bbox-intersection matching
- **Pin**: `docling>=2.79.0,<2.96.0`, `docling-ibm-models>=3.8.1`
- **Nächster Schritt**: Phase 9 Diagnose-Script → Cell-BBox-Transform → Verifikation auf p4003r1

---

## 10. Nicht adoptieren (mit Begründung)

| Tool | Grund |
|---|---|
| Marker/Surya | GPL-3.0 — inkompatibel mit BSL-1.0 Distribution |
| Nougat | Tabellen-Qualität schlecht; Meta hat es aufgegeben |
| Camelot/pdfplumber/Tabula | Gleiche Row-Boundary-Schwäche wie tomd — löst Multi-Line nicht |
| MinerU als Ersatz | AGPL-nah; VLM-Varianz verletzt Determinismus-Mandat |
| Full-Doc Docling MD | Page-Triage bereits gescheitert (Content-Löschung, Position) |
| LayoutLMv3/UDOP | CC-BY-NC-SA; benötigt OCR-Pipeline; kein Table-Output |

---

*Recherche durchgeführt mit 8 parallelen Composer-2.5 Subagents. ~150+ Tools/Modelle evaluiert.*
