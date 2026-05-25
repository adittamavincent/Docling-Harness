# Docling Harness 🦅

A supercharged multi-format document-to-markdown conversion utility powered by **Docling v2** and **Camelot**. Designed for high-fidelity document parsing, structure extraction, and precise table handling.

---

## Aim of the Project

The aim of **Docling Harness** is to provide a unified, zero-configuration interface for converting various document types (PDFs, Word documents, PowerPoint presentations, Excel sheets, HTML files, and scanned images) into clean, standard Markdown. 

By leveraging the structural layout analysis of Docling together with the programmatic table grid extraction of Camelot, Docling Harness offers a hybrid approach to parse complex PDF layouts and extract precise data representations suitable for LLM indexing, RAG systems, or clean document archiving.

---

## Supported Formats

- **PDF** (`.pdf`)
- **Word** (`.docx`, `.doc`)
- **PowerPoint** (`.pptx`)
- **Excel** (`.xlsx`)
- **Images** (`.png`, `.jpg`, `.jpeg`, `.tiff`)
- **Web Pages** (`.html`, `.htm`)

---

## Table Extraction Modes

Docling Harness offers three distinct strategies for extracting tables from your files:

1. **`native` (Docling TableFormer)** (Default)
   - Uses Docling's advanced deep learning-based visual structure recognizer.
   - **Best for:** Scanned documents, non-programmatic PDFs, complex Word documents, images, and tables with spanning cells.
   
2. **`camelot` (Camelot Grid Extractor)**
   - Disables Docling's table parser and uses **Camelot** exclusively to extract programmatic table grids from PDFs.
   - **Best for:** Highly structured programmatic PDFs where tables have grid lines or clear white-space separations.
   
3. **`hybrid` (Combined Engine)**
   - Uses Docling to parse the main document body structure (headings, lists, paragraphs) and appends high-fidelity table grids extracted by **Camelot** in a dedicated reference section.
   - **Best for:** Documents where both visual body flow and exact programmatic spreadsheet data are required.

---

## Installation & Setup

This repository uses [uv](https://github.com/astral-sh/uv) for fast, robust package and project management. 

### Prerequisites

Make sure you have `uv` installed. If you do not have it, you can install it using Homebrew:
```bash
brew install uv
```

### Setup Workspace

Simply navigate to the project directory. The `uv` package manager will automatically handle compiling and caching dependencies inside a virtual environment upon execution!
```bash
# Verify uv is installed
uv --version
```

---

## Usage Guide

You can run the converter using **`uv run`** or via the included **`docling-harness`** shell wrapper.

### 1. Unified Command (Recommended)

Run the included `./docling-harness` script directly from the workspace. It automatically resolves dependencies, handles execution via `uv run`, and functions perfectly from any working directory.

> [!NOTE]
> If you encounter a `Permission denied` error when executing the script for the first time, make it executable:
> ```bash
> chmod +x docling-harness
> # Or, if required by system configuration:
> sudo chmod +x docling-harness
> ```

> [!TIP]
> **Apple Silicon macOS Compatibility:**
> Docling's standard layout parsing uses deep learning models that are incompatible with PyTorch's MPS double-precision (`float64`) operations.
> To bypass this layout model crash out-of-the-box, **Docling Harness automatically defaults its accelerator `--device` to `cpu` on macOS** when set to `auto` (the default). If you explicitly specify `--device mps` and encounter a `TypeError`, the tool will cleanly catch the exception and instruct you to run with `--device cpu`.

To convert a document, simply run:
```bash
./docling-harness path/to/document.pdf [options]
```

### 2. Standard `uv run`

Expose the script directly in your terminal workspace:
```bash
# Native Mode (Default)
uv run docling-harness input.docx -o output_directory/

# Hybrid PDF Parsing (Docling layout + Camelot grid extraction)
uv run docling-harness input.pdf --table-mode hybrid --flavor lattice

# No OCR scanned detection (speeds up programmatic PDF processing)
uv run docling-harness input.pdf --table-mode native --no-ocr
```

### 3. CLI Arguments

| Argument | Choices | Default | Description |
| :--- | :--- | :--- | :--- |
| `document_path` | *filepath* | *(Required)* | Path to the source file (PDF, Word, PPTX, Images, etc.) |
| `--table-mode` | `native`, `camelot`, `hybrid` | `native` | Selection strategy for table parser engines |
| `--flavor` | `lattice`, `stream` | `lattice` | Camelot parser flavor (lattice matches grid lines, stream uses whitespace) |
| `--ocr` / `--no-ocr` | — | `--ocr` | Enable or disable Optical Character Recognition (OCR) for scanned sheets |
| `--export-images` | — | `False` | Extract charts, figures, and table snapshots as visual PNG assets |
| `--debug-docling-tables` | — | `False` | Output a separate debug markdown showing Docling-detected tables |
| `-o`, `--output-dir` | *directory* | `.` | Target directory to save markdown outputs and assets |
| `--device` | `auto`, `cpu`, `cuda`, `mps` | `auto` | Accelerator backend. Defaults to `cpu` on macOS to bypass PyTorch MPS `float64` issues |

---

## Examples

### Extracting Images and Figures

To parse a PowerPoint or a PDF and extract all embedded visual illustrations and charts, use the `--export-images` flag:
```bash
./docling-harness sample.pptx --export-images -o output/
```
This generates:
- `output/sample.md` (with inline images mapped to local assets)
- `output/sample_assets/` (containing extracted high-resolution PNGs)

### Programmatic PDF Parsing with Camelot Stream

For PDFs containing tables without physical border lines, use the `stream` flavor in hybrid mode:
```bash
./docling-harness financial_report.pdf --table-mode hybrid --flavor stream
```

### Scanned Document OCR Parsing

Convert a scanned image directly to Markdown text:
```bash
./docling-harness receipt.jpg --ocr
```
