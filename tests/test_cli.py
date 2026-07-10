"""Tests for panelo CLI and CSV parsing."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from panelo.cli import app
from panelo.core import load_panels_from_csv, pack_panels
from panelo.models import Panel


runner = CliRunner()


def test_load_panels_from_csv_width_length_qty(tmp_path: Path):
    """CSV loader should expand rows based on qty."""
    csv_path = tmp_path / "panels.csv"
    csv_path.write_text("width,length,qty\n100,200,2\n50,75,1\n", encoding="utf-8")

    panels = load_panels_from_csv(csv_path)

    assert len(panels) == 3
    assert sum(1 for p in panels if p.width == 100 and p.height == 200) == 2
    assert sum(1 for p in panels if p.width == 50 and p.height == 75) == 1


def test_load_panels_from_csv_requires_columns(tmp_path: Path):
    """CSV loader should reject missing required columns."""
    csv_path = tmp_path / "panels.csv"
    csv_path.write_text("w,h,qty\n100,200,1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="width,length,qty"):
        load_panels_from_csv(csv_path)


def test_pack_panels_applies_kerf_to_fit():
    """Kerf should reduce fit and may require additional sheets."""
    panels = [Panel(500, 500), Panel(500, 500)]

    sheets_no_kerf = pack_panels(
        [Panel(p.width, p.height) for p in panels],
        sheet_width=1000,
        sheet_height=600,
        algorithm="guillotine",
        kerf=0,
    )
    sheets_with_kerf = pack_panels(
        [Panel(p.width, p.height) for p in panels],
        sheet_width=1000,
        sheet_height=600,
        algorithm="guillotine",
        kerf=5,
    )

    assert len(sheets_no_kerf) == 1
    assert len(sheets_with_kerf) == 2


def test_cli_accepts_csv_and_kerf(tmp_path: Path):
    """CLI should load CSV and execute packing with kerf."""
    csv_path = tmp_path / "input.csv"
    csv_path.write_text("width,length,qty\n500,500,2\n", encoding="utf-8")

    result = runner.invoke(app, [str(csv_path), "1000", "600", "--kerf", "5"])

    assert result.exit_code == 0
    assert "CUTTING PLAN" in result.stdout
    assert "Total Sheets: 2" in result.stdout


def test_cli_rejects_invalid_csv(tmp_path: Path):
    """CLI should show a friendly validation error for bad CSV columns."""
    csv_path = tmp_path / "input.csv"
    csv_path.write_text("w,h,qty\n500,500,2\n", encoding="utf-8")

    result = runner.invoke(app, [str(csv_path), "1000", "500"])

    assert result.exit_code != 0
    assert "width,length,qty" in result.stderr


def test_cli_with_project_input_csv_fixture():
    """CLI should process the project CSV fixture with extra columns."""
    csv_path = Path(__file__).parent / "data" / "input.csv"

    result = runner.invoke(app, [str(csv_path), "1220", "2440", "--kerf", "3.2"])

    assert result.exit_code == 0
    assert "CUTTING PLAN" in result.stdout
    assert "Total Panels: 18" in result.stdout
    assert "Total Sheets:" in result.stdout


def test_cli_final_output_writes_all_formats(tmp_path: Path):
    """CLI should write all output formats when final output base is provided."""
    csv_path = tmp_path / "input.csv"
    csv_path.write_text("width,length,qty\n500,500,2\n", encoding="utf-8")
    output_base = tmp_path / "output" / "plan"

    result = runner.invoke(
        app,
        [str(csv_path), "1000", "600", str(output_base), "--kerf", "5"],
    )

    assert result.exit_code == 0
    assert "CUTTING PLAN" in result.stdout

    assert output_base.with_suffix(".txt").exists()
    assert output_base.with_suffix(".csv").exists()
    assert output_base.with_suffix(".json").exists()
    assert output_base.with_suffix(".pdf").exists()
    assert output_base.with_name(f"{output_base.name}_sheet1.svg").exists()
    assert output_base.with_name(f"{output_base.name}_sheet2.svg").exists()
    assert Path(f"{output_base}.ascii.txt").exists()


def test_cli_final_output_keeps_stdout(tmp_path: Path):
    """CLI should still print text plan even when writing files."""
    csv_path = tmp_path / "input.csv"
    csv_path.write_text("width,length,qty\n200,300,1\n", encoding="utf-8")
    output_base = tmp_path / "plan"

    result = runner.invoke(
        app,
        [str(csv_path), "1000", "600", str(output_base)],
    )

    assert result.exit_code == 0
    assert "CUTTING PLAN" in result.stdout


def test_cli_custom_svg_font_sizes(tmp_path: Path):
    """CLI should pass custom SVG font sizes to generated SVG output."""
    csv_path = tmp_path / "input.csv"
    csv_path.write_text("width,length,qty\n200,300,1\n", encoding="utf-8")
    output_base = tmp_path / "plan"

    result = runner.invoke(
        app,
        [
            str(csv_path),
            "1000",
            "600",
            str(output_base),
            "--svg-title-font-size",
            "32",
            "--svg-label-font-size",
            "26",
        ],
    )

    assert result.exit_code == 0

    svg_content = output_base.with_suffix(".svg").read_text(encoding="utf-8")
    assert "font-size: 32px" in svg_content
    assert "font-size: 26px" in svg_content
