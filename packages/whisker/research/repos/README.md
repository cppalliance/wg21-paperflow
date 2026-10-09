# Research repos (manual clone)

These directories are **not** in the GitHub workspace mirror (too large, nested git repos). Clone shallow copies locally before redteam / repo-inspection work.

Target layout: `packages/whisker/research/repos/<name>/`

## Clone all (PowerShell, from repo root)

```powershell
$dest = "packages/whisker/research/repos"
$repos = @{
  camelot                  = "https://github.com/camelot-dev/camelot.git"
  docling                  = "https://github.com/docling-project/docling.git"
  Dolphin                  = "https://github.com/bytedance/Dolphin.git"
  firecrawl                = "https://github.com/firecrawl/firecrawl.git"
  grobid                   = "https://github.com/kermitt2/grobid.git"
  html2text                = "https://github.com/Alir3z4/html2text.git"
  html-to-markdown-go      = "https://github.com/JohannesKaufmann/html-to-markdown.git"
  html-to-markdown-py      = "https://github.com/kreuzberg-dev/html-to-markdown.git"
  img2table                = "https://github.com/xavctn/img2table.git"
  markdownify              = "https://github.com/matthewwithanm/python-markdownify.git"
  marker                   = "https://github.com/datalab-to/marker.git"
  markitdown               = "https://github.com/microsoft/markitdown.git"
  mdream                   = "https://github.com/harlan-zw/mdream.git"
  MinerU                   = "https://github.com/opendatalab/MinerU.git"
  node-html-markdown       = "https://github.com/crosstype/node-html-markdown.git"
  nougat                   = "https://github.com/facebookresearch/nougat.git"
  olmocr                   = "https://github.com/allenai/olmocr.git"
  opendataloader-bench-tmp = "https://github.com/opendataloader-project/opendataloader-bench.git"
  opendataloader-pdf       = "https://github.com/opendataloader-project/opendataloader-pdf.git"
  pandoc                   = "https://github.com/jgm/pandoc.git"
  PDF-Extract-Kit          = "https://github.com/opendatalab/PDF-Extract-Kit.git"
  pdfplumber               = "https://github.com/jsvine/pdfplumber.git"
  pdf-to-markdown          = "https://github.com/jzillmann/pdf-to-markdown.git"
  PyMuPDF                  = "https://github.com/pymupdf/PyMuPDF.git"
  pymupdf4llm              = "https://github.com/pymupdf/pymupdf4llm.git"
  surya                    = "https://github.com/datalab-to/surya.git"
  tabula-java              = "https://github.com/tabulapdf/tabula-java.git"
  deepeval                 = "https://github.com/confident-ai/deepeval.git"
  langextract              = "https://github.com/google/langextract.git"
  litellm                  = "https://github.com/BerriAI/litellm.git"
  marker-v1.10.2           = "https://github.com/datalab-to/marker.git"
  marker-v2.0.0            = "https://github.com/datalab-to/marker.git"
  mineru-vl-utils          = "https://github.com/opendatalab/mineru-vl-utils.git"
  promptfoo                = "https://github.com/promptfoo/promptfoo.git"
  ragas                    = "https://github.com/explodinggradients/ragas.git"
  sglang                   = "https://github.com/sgl-project/sglang.git"
  tabula-java-tmp          = "https://github.com/tabulapdf/tabula-java.git"
  turndown                 = "https://github.com/mixmark-io/turndown.git"
  unstructured             = "https://github.com/Unstructured-IO/unstructured.git"
  unstructured-ingest      = "https://github.com/Unstructured-IO/unstructured-ingest.git"
  vllm                     = "https://github.com/vllm-project/vllm.git"
}
foreach ($name in ($repos.Keys | Sort-Object)) {
  $path = Join-Path $dest $name
  if (Test-Path $path) { Write-Host "skip $name (exists)"; continue }
  git clone --depth 1 $repos[$name] $path
}
```

## Per-repo table

| Directory | Upstream |
|-----------|----------|
| camelot | https://github.com/camelot-dev/camelot |
| deepeval | https://github.com/confident-ai/deepeval |
| docling | https://github.com/docling-project/docling |
| Dolphin | https://github.com/bytedance/Dolphin |
| firecrawl | https://github.com/firecrawl/firecrawl |
| grobid | https://github.com/kermitt2/grobid |
| html2text | https://github.com/Alir3z4/html2text |
| html-to-markdown-go | https://github.com/JohannesKaufmann/html-to-markdown |
| html-to-markdown-py | https://github.com/kreuzberg-dev/html-to-markdown |
| img2table | https://github.com/xavctn/img2table |
| langextract | https://github.com/google/langextract |
| litellm | https://github.com/BerriAI/litellm |
| markdownify | https://github.com/matthewwithanm/python-markdownify |
| marker | https://github.com/datalab-to/marker |
| marker-v1.10.2 | https://github.com/datalab-to/marker (pinned to v1.10.2) |
| marker-v2.0.0 | https://github.com/datalab-to/marker (pinned to v2.0.0) |
| markitdown | https://github.com/microsoft/markitdown |
| mdream | https://github.com/harlan-zw/mdream |
| MinerU | https://github.com/opendatalab/MinerU |
| mineru-vl-utils | https://github.com/opendatalab/mineru-vl-utils |
| node-html-markdown | https://github.com/crosstype/node-html-markdown |
| nougat | https://github.com/facebookresearch/nougat |
| olmocr | https://github.com/allenai/olmocr |
| opendataloader-bench-tmp | https://github.com/opendataloader-project/opendataloader-bench |
| opendataloader-pdf | https://github.com/opendataloader-project/opendataloader-pdf |
| pandoc | https://github.com/jgm/pandoc |
| PDF-Extract-Kit | https://github.com/opendatalab/PDF-Extract-Kit |
| pdfplumber | https://github.com/jsvine/pdfplumber |
| promptfoo | https://github.com/promptfoo/promptfoo |
| pdf-to-markdown | https://github.com/jzillmann/pdf-to-markdown |
| PyMuPDF | https://github.com/pymupdf/PyMuPDF |
| pymupdf4llm | https://github.com/pymupdf/pymupdf4llm |
| ragas | https://github.com/explodinggradients/ragas |
| sglang | https://github.com/sgl-project/sglang |
| surya | https://github.com/datalab-to/surya |
| tabula-java | https://github.com/tabulapdf/tabula-java |
| tabula-java-tmp | https://github.com/tabulapdf/tabula-java (duplicate checkout) |
| turndown | https://github.com/mixmark-io/turndown |
| unstructured | https://github.com/Unstructured-IO/unstructured |
| unstructured-ingest | https://github.com/Unstructured-IO/unstructured-ingest |
| vllm | https://github.com/vllm-project/vllm |

See also `packages/whisker/research/models-vram-deployment-survey.md` for model/VRAM notes tied to these tools.
