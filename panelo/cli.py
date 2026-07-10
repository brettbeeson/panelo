"""Command line interface for panelo."""

from pathlib import Path
from typing import Optional
import typer

from panelo import output as output_formatters
from panelo.core import load_panels_from_csv, pack_panels

app = typer.Typer()


@app.command()
def main(
    panels_file: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="CSV file with columns: width,length,qty",
    ),
    sheet_width: float = typer.Argument(..., help="Sheet width in millimeters"),
    sheet_height: float = typer.Argument(..., help="Sheet height in millimeters"),
    output: Optional[Path] = typer.Argument(
        None,
        help="Optional base output name/path. Writes .txt, .csv, .json, .svg, and .ascii.txt",
    ),
    algorithm: str = typer.Option(
        "guillotine",
        "--algorithm", "-a",
        help="Packing algorithm: guillotine, first-fit, maxrect"
    ),
    kerf: float = typer.Option(
        0.0,
        "--kerf",
        min=0.0,
        help="Kerf width (saw blade thickness) in mm"
    ),
    svg_title_font_size: int = typer.Option(
        40,
        "--svg-title-font-size",
        min=6,
        help="SVG title/header font size in px",
    ),
    svg_label_font_size: int = typer.Option(
        30,
        "--svg-label-font-size",
        min=6,
        help="SVG panel label font size in px",
    ),
    svg_dimension_font_size: int = typer.Option(
        16,
        "--svg-dimension-font-size",
        min=6,
        help="SVG dimension chain font size in px",
    ),
    grain: bool = typer.Option(
        False,
        "--grain",
        help="Consider wood grain direction - NOT IMPLEMENTED YET"
    ),
):
    """Main command for panelo CLI."""
    # Validate algorithm choice
    valid_algorithms = ["guillotine", "first-fit", "maxrect"]
    if algorithm not in valid_algorithms:
        raise typer.BadParameter(
            f"Invalid algorithm '{algorithm}'. Choose from: {', '.join(valid_algorithms)}"
        )
    
    # Check for not-yet-implemented features
    if grain:
        raise typer.BadParameter("--grain option is not implemented yet")

    try:
        panels = load_panels_from_csv(panels_file)
        sheets = pack_panels(
            panels,
            sheet_width=sheet_width,
            sheet_height=sheet_height,
            algorithm=algorithm,
            kerf=kerf,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    text_output = output_formatters.to_text(sheets)

    if output is not None:
        base = output
        base.parent.mkdir(parents=True, exist_ok=True)

        txt_path = base.with_suffix(".txt")
        csv_path = base.with_suffix(".csv")
        json_path = base.with_suffix(".json")
        svg_path = base.with_suffix(".svg")
        pdf_path = base.with_suffix(".pdf")
        ascii_path = Path(f"{base}.ascii.txt")

        txt_path.write_text(text_output, encoding="utf-8")
        csv_path.write_text(output_formatters.to_csv(sheets), encoding="utf-8")
        json_path.write_text(output_formatters.to_json(sheets), encoding="utf-8")
        ascii_path.write_text(output_formatters.to_ascii(sheets), encoding="utf-8")
        output_formatters.to_svg(
            sheets,
            filename=str(svg_path),
            title_font_size=svg_title_font_size,
            label_font_size=svg_label_font_size,
            dimension_font_size=svg_dimension_font_size,
        )
        output_formatters.to_pdf(
            sheets,
            filename=str(pdf_path),
            input_panels=panels,
            panels_file=str(panels_file),
            sheet_width=sheet_width,
            sheet_height=sheet_height,
            algorithm=algorithm,
            kerf=kerf,
            svg_dimension_font_size=svg_dimension_font_size,
        )

    typer.echo(text_output)


if __name__ == "__main__":
    app()
