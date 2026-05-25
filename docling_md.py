# ruff: noqa: E402
import argparse
import sys
import time
import warnings
from pathlib import Path
from typing import Optional, Tuple, Dict, List

# Suppress the ARC4 cryptography warning
warnings.filterwarnings("ignore", message=".*ARC4 has been moved.*")

# Rich interface integration
try:
    from rich.console import Console
    from rich.theme import Theme
    from rich.status import Status
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    custom_theme = Theme({
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "accent": "bold magenta",
        "doc": "bold blue"
    })
    console = Console(theme=custom_theme)
except ImportError:
    # Standard terminal fallback
    class DummyConsole:
        def print(self, *args, **kwargs):
            style = kwargs.pop("style", None)
            if style == "error":
                print("[ERROR]", *args, **kwargs)
            elif style == "warning":
                print("[WARNING]", *args, **kwargs)
            elif style == "success":
                print("[SUCCESS]", *args, **kwargs)
            else:
                print(*args, **kwargs)

        def log(self, *args, **kwargs):
            print("[INFO]", *args, **kwargs)

        def status(self, text, **kwargs):
            class DummyStatus:
                def __enter__(self):
                    print(f"... {text}")
                    return self
                def __exit__(self, exc_type, exc_val, exc_tb):
                    pass
            return DummyStatus()
            
    console = DummyConsole()

# Docling Imports
try:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc.document import DoclingDocument
except ImportError as e:
    console.print(f"Error: Required dependency docling is not installed: {e}", style="error")
    sys.exit(1)

# Camelot Import
try:
    import camelot
    HAS_CAMELOT = True
except ImportError:
    HAS_CAMELOT = False


def build_docling_converter(
    enable_table_structure: bool = True,
    enable_ocr: bool = True,
    export_images: bool = False
) -> DocumentConverter:
    """Builds a configured DocumentConverter instance."""
    pdf_pipeline_options = PdfPipelineOptions()
    pdf_pipeline_options.do_table_structure = enable_table_structure
    pdf_pipeline_options.do_ocr = enable_ocr
    
    if export_images:
        pdf_pipeline_options.generate_picture_images = True
        pdf_pipeline_options.generate_page_images = True
        pdf_pipeline_options.images_scale = 2.0
    
    # We only customize the PDF pipeline options; other formats use built-in parsers
    format_options = {
        InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_pipeline_options)
    }
    
    return DocumentConverter(format_options=format_options)


def export_docling_table_debug(doc: DoclingDocument, pdf_path: Path, flavor: str) -> Path:
    """Exports Docling-detected tables to a separate markdown file for comparison/debugging."""
    lines: list[str] = [
        "# Docling Table Debug",
        "",
        f"- Source PDF: `{pdf_path.name}`",
        f"- Detected Docling tables: `{len(doc.tables)}`",
        f"- Camelot flavor used in main run: `{flavor}`",
        "",
    ]

    for i, table in enumerate(doc.tables):
        df = table.export_to_dataframe(doc=doc)
        lines.append(f"## Docling Table {i + 1}")
        lines.append("")
        lines.append(df.to_markdown(index=False))
        lines.append("")

    debug_file = pdf_path.with_suffix(".docling-table-debug.md")
    debug_file.write_text("\n".join(lines), encoding="utf-8")
    return debug_file


def extract_camelot_tables(pdf_path: Path, flavor: str) -> List[str]:
    """Uses Camelot to extract high-accuracy tables from a programmatic PDF."""
    if not HAS_CAMELOT:
        console.print("Camelot is not installed or import failed. Skipping Camelot table extraction.", style="warning")
        return []
    
    try:
        tables = camelot.read_pdf(str(pdf_path), pages="all", flavor=flavor)
        table_blocks: List[str] = []
        for i, table in enumerate(tables):
            df = table.df
            md_table = df.to_markdown(index=False)
            table_blocks.append(f"\n\n### Table {i + 1} (Camelot {flavor})\n\n{md_table}\n")
        return table_blocks
    except Exception as e:
        console.print(f"Camelot table extraction failed: {e}. Falling back to default handling.", style="warning")
        return []


def export_images_assets(doc: DoclingDocument, input_path: Path, output_dir: Path) -> List[str]:
    """Exports embedded figures and table snapshots as images, returning relative paths."""
    assets_dir = output_dir / f"{input_path.stem}_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    image_paths: List[str] = []
    
    exported_count = 0
    for element, _level in doc.iterate_items():
        if element.label in ["picture", "chart", "table"]:
            try:
                # Try getting the image using get_image method
                pil_img = element.get_image(doc)
                if pil_img is not None:
                    el_type = element.label
                    el_id = element.self_ref.split("/")[-1]
                    img_filename = f"{el_type}_{el_id}.png"
                    img_path = assets_dir / img_filename
                    
                    pil_img.save(img_path)
                    image_paths.append(f"{assets_dir.name}/{img_filename}")
                    exported_count += 1
            except Exception as e:
                # Ignore failed extractions and proceed
                pass
                
    if exported_count > 0:
        console.print(f"Successfully exported {exported_count} images to {assets_dir.name}/", style="success")
    return image_paths


def replace_image_placeholders(markdown_text: str, image_mappings: List[str]) -> str:
    """Replaces sequential '<!-- image -->' placeholders in markdown with actual image file links."""
    parts = markdown_text.split("<!-- image -->")
    
    result_parts = []
    for i, part in enumerate(parts):
        result_parts.append(part)
        if i < len(image_mappings):
            result_parts.append(f"\n\n![Figure]({image_mappings[i]})\n\n")
        elif i < len(parts) - 1:
            result_parts.append("<!-- image -->")
            
    return "".join(result_parts)


def convert_document(
    input_path: Path,
    output_dir: Path,
    table_mode: str = "native",
    flavor: str = "lattice",
    enable_ocr: bool = True,
    export_images: bool = False,
    debug_docling_tables: bool = False
) -> Tuple[Path, Optional[Path]]:
    """Converts a document to Markdown with premium options and table layout models."""
    start_time = time.time()
    
    # Detect Input Format
    suffix = input_path.suffix.lower()
    is_pdf = suffix == ".pdf"
    
    # Camelot is PDF-only. If input is not PDF, fall back gracefully to native mode.
    actual_table_mode = table_mode
    if not is_pdf and table_mode in ["camelot", "hybrid"]:
        console.print(f"Input file '{input_path.name}' is not a PDF. Table mode '{table_mode}' forced to 'native'.", style="warning")
        actual_table_mode = "native"
        
    # Standard Docling Table Extraction Strategy
    # If the user chose camelot or hybrid, we do standard layout parsing without Docling tables (Docling does the text, Camelot does tables)
    do_docling_tables = actual_table_mode in ["native", "hybrid"]
    
    # 1. Initialize DocumentConverter
    converter = build_docling_converter(
        enable_table_structure=do_docling_tables,
        enable_ocr=enable_ocr,
        export_images=export_images
    )
    
    # 2. Convert via Docling
    with console.status(f"Parsing [doc]{input_path.name}[/doc] using Docling ..."):
        result = converter.convert(str(input_path))
        markdown_text = result.document.export_to_markdown()
        
    # 3. Handle image exports
    if export_images:
        with console.status("Extracting figures and illustrations..."):
            image_mappings = export_images_assets(result.document, input_path, output_dir)
            if image_mappings:
                markdown_text = replace_image_placeholders(markdown_text, image_mappings)
                
    # 4. Table Processing via Camelot (PDF only)
    table_markdown_blocks: List[str] = []
    if is_pdf and actual_table_mode in ["camelot", "hybrid"]:
        with console.status(f"Extracting tables with Camelot ({flavor} flavor)..."):
            table_markdown_blocks = extract_camelot_tables(input_path, flavor=flavor)
            
    # 5. Join final Markdown
    if table_markdown_blocks:
        if actual_table_mode == "camelot":
            # Just append Camelot tables at the end of the text-parsed doc
            final_md = markdown_text + "\n" + "\n".join(table_markdown_blocks)
        else:
            # Hybrid mode: append Camelot tables in their own high-fidelity section
            final_md = markdown_text + "\n\n## High-Fidelity Appended Tables\n" + "\n".join(table_markdown_blocks)
    else:
        final_md = markdown_text
        
    # 6. Save final file
    output_file = output_dir / f"{input_path.stem}.md"
    output_file.write_text(final_md, encoding="utf-8")
    
    # 7. Debug docling tables if requested (runs a separate converter if docling tables were turned off)
    debug_file: Optional[Path] = None
    if debug_docling_tables and is_pdf:
        if do_docling_tables:
            debug_file = export_docling_table_debug(result.document, input_path, flavor=flavor)
        else:
            with console.status("Generating Docling table debug view..."):
                debug_converter = build_docling_converter(enable_table_structure=True, enable_ocr=enable_ocr)
                debug_result = debug_converter.convert(str(input_path))
                debug_file = export_docling_table_debug(debug_result.document, input_path, flavor=flavor)
                
    elapsed_time = time.time() - start_time
    console.print(f"Converted [doc]{input_path.name}[/doc] in [accent]{elapsed_time:.2f}s[/accent]. Output: [success]{output_file.name}[/success]", style="info")
    
    return output_file, debug_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Premium multi-format document parser using Docling and Camelot."
    )
    parser.add_argument("document_path", help="Path to the input document (PDF, Word, PPTX, XLSX, HTML, or Image)")
    parser.add_argument(
        "--table-mode",
        choices=["native", "camelot", "hybrid"],
        default="native",
        help="Table extraction mode: 'native' (Docling TableFormer), 'camelot' (PDF Camelot grids), 'hybrid' (both) (default: native)",
    )
    parser.add_argument(
        "--flavor",
        choices=["lattice", "stream"],
        default="lattice",
        help="Camelot extraction flavor (default: lattice)",
    )
    parser.add_argument(
        "--ocr",
        dest="enable_ocr",
        action="store_true",
        default=True,
        help="Enable OCR for scanned images/PDFs (default: True)"
    )
    parser.add_argument(
        "--no-ocr",
        dest="enable_ocr",
        action="store_false",
        help="Disable OCR entirely"
    )
    parser.add_argument(
        "--export-images",
        action="store_true",
        help="Export figures and tables as visual PNG assets"
    )
    parser.add_argument(
        "--debug-docling-tables",
        action="store_true",
        help="Export Docling-detected tables to a separate comparison file (PDF only)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=".",
        help="Directory to save generated markdown files (default: current directory)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.document_path)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        console.print(f"Error: Document not found: '{input_path}'", style="error")
        sys.exit(1)

    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    try:
        output_file, debug_file = convert_document(
            input_path=input_path,
            output_dir=output_dir,
            table_mode=args.table_mode,
            flavor=args.flavor,
            enable_ocr=args.enable_ocr,
            export_images=args.export_images,
            debug_docling_tables=args.debug_docling_tables
        )
        
        console.print(f"Successfully saved output markdown: [success]{output_file.resolve()}[/success]")
        if debug_file:
            console.print(f"Saved Docling table debug comparison: [info]{debug_file.resolve()}[/info]")
            
    except Exception as e:
        console.print(f"Conversion failed due to an unexpected error: {e}", style="error")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
