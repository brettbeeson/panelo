"""Integration test: CSV input to all output formats."""

import json
from pathlib import Path

from panelo import output
from panelo.core import load_panels_from_csv, pack_panels


def test_csv_input_generates_all_outputs():
    """Read fixture CSV and generate CSV/SVG/JSON/TXT/ASCII outputs."""
    tests_dir = Path(__file__).parent
    input_csv = tests_dir / "data" / "input.csv"
    output_dir = tests_dir / "output" / "integration"
    output_dir.mkdir(parents=True, exist_ok=True)

    panels = load_panels_from_csv(input_csv)
    sheets = pack_panels(
        panels,
        sheet_width=1220,
        sheet_height=2440,
        algorithm="guillotine",
        kerf=3.2,
    )

    json_path = output_dir / "integration_output.json"
    csv_path = output_dir / "integration_output.csv"
    txt_path = output_dir / "integration_output.txt"
    ascii_path = output_dir / "integration_output_ascii.txt"
    svg_path = output_dir / "integration_output.svg"

    json_content = output.to_json(sheets)
    csv_content = output.to_csv(sheets)
    text_content = output.to_text(sheets)
    ascii_content = output.to_ascii(sheets)
    svg_content = output.to_svg(sheets, filename=str(svg_path))

    json_path.write_text(json_content, encoding="utf-8")
    csv_path.write_text(csv_content, encoding="utf-8")
    txt_path.write_text(text_content, encoding="utf-8")
    ascii_path.write_text(ascii_content, encoding="utf-8")

    assert json_path.exists()
    assert csv_path.exists()
    assert txt_path.exists()
    assert ascii_path.exists()

    svg_files = sorted(output_dir.glob("integration_output_sheet*.svg"))
    assert len(svg_files) == len(sheets)

    data = json.loads(json_content)
    assert "sheets" in data
    assert len(data["sheets"]) > 0

    assert "Sheet #" in csv_content
    assert "CUTTING PLAN" in text_content
    assert "Panels:" in ascii_content
    assert svg_content.startswith("<?xml")
    assert "<svg" in svg_content
