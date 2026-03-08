# ruff: noqa: E402
from pathlib import Path
import argparse
import warnings

warnings.filterwarnings("ignore", message=".*ARC4 has been moved.*")

import camelot
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption


def build_docling_converter(enable_table_structure: bool) -> DocumentConverter:
    pipeline_options = PdfPipelineOptions(do_table_structure=enable_table_structure)
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )


def export_docling_table_debug(pdf_path: Path, flavor: str) -> Path:
    debug_converter = build_docling_converter(enable_table_structure=True)
    debug_result = debug_converter.convert(str(pdf_path))

    lines: list[str] = [
        "# Docling Table Debug",
        "",
        f"- Source PDF: `{pdf_path.name}`",
        f"- Detected Docling tables: `{len(debug_result.document.tables)}`",
        f"- Camelot flavor used in main run: `{flavor}`",
        "",
    ]

    for i, table in enumerate(debug_result.document.tables):
        df = table.export_to_dataframe(doc=debug_result.document)
        lines.append(f"## Docling Table {i + 1}")
        lines.append("")
        lines.append(df.to_markdown(index=False))
        lines.append("")

    debug_file = pdf_path.with_suffix(".docling-table-debug.md")
    debug_file.write_text("\n".join(lines), encoding="utf-8")
    return debug_file


def convert_pdf_to_markdown(
    pdf_path: Path,
    flavor: str = "lattice",
    debug_docling_tables: bool = False,
) -> tuple[Path, Path | None]:
    # Keep Docling focused on body text so table content comes from Camelot.
    text_converter = build_docling_converter(enable_table_structure=False)
    result = text_converter.convert(str(pdf_path))
    markdown_text = result.document.export_to_markdown()

    tables = camelot.read_pdf(str(pdf_path), pages="all", flavor=flavor)

    table_markdown_blocks: list[str] = []
    for i, table in enumerate(tables):
        df = table.df
        md_table = df.to_markdown(index=False)
        table_markdown_blocks.append(f"\n\n### Table {i + 1}\n\n{md_table}\n")

    final_md = markdown_text + "\n".join(table_markdown_blocks)

    output_file = pdf_path.with_suffix(".md")
    output_file.write_text(final_md, encoding="utf-8")

    debug_file: Path | None = None
    if debug_docling_tables:
        debug_file = export_docling_table_debug(pdf_path, flavor=flavor)

    return output_file, debug_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a PDF to markdown using Docling and append Camelot table extraction."
    )
    parser.add_argument("pdf_path", help="Path to the input PDF file")
    parser.add_argument(
        "--flavor",
        choices=["lattice", "stream"],
        default="lattice",
        help="Camelot extraction flavor (default: lattice)",
    )
    parser.add_argument(
        "--debug-docling-tables",
        action="store_true",
        help="Export Docling-detected tables to a separate debug markdown file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf_path = Path(args.pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    output_file, debug_file = convert_pdf_to_markdown(
        pdf_path,
        flavor=args.flavor,
        debug_docling_tables=args.debug_docling_tables,
    )
    print(f"Saved: {output_file}")
    if debug_file is not None:
        print(f"Saved Docling debug: {debug_file}")


if __name__ == "__main__":
    main()
