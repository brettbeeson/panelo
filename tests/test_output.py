"""Tests for output formatters."""

import json
import os
import shutil
import pytest
from panelo.models import Panel, Sheet
from panelo.algorithms import GuillotineAlgorithm
from panelo import output


@pytest.fixture
def sample_sheets():
    """Create sample sheets for testing."""
    packer = GuillotineAlgorithm()
    panels = [
        Panel(400, 600),
        Panel(300, 500),
        Panel(200, 400),
    ]
    return packer.pack(panels, sheet_width=1220, sheet_height=2440)


@pytest.fixture(scope="module")
def output_dir():
    """Create and return a local output directory."""
    # Get tests directory
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(tests_dir, "output")
    
    # Clean and recreate directory
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    os.makedirs(output_path)
    
    print(f"\n\nTest outputs saved to: {output_path}")
    return output_path


def test_to_json(sample_sheets, output_dir):
    """Test JSON output format."""
    result = output.to_json(sample_sheets)
    
    # Save to file
    json_path = os.path.join(output_dir, "output.json")
    with open(json_path, 'w') as f:
        f.write(result)
    print(f"JSON saved: {json_path}")
    
    # Should be valid JSON
    data = json.loads(result)
    
    assert "sheets" in data
    assert len(data["sheets"]) > 0
    
    sheet = data["sheets"][0]
    assert "sheet_number" in sheet
    assert "width" in sheet
    assert "height" in sheet
    assert "utilization_percent" in sheet
    assert "panels" in sheet
    
    if sheet["panels"]:
        panel = sheet["panels"][0]
        assert "panel_number" in panel
        assert "width" in panel
        assert "height" in panel
        assert "x" in panel
        assert "y" in panel
        assert "rotated" in panel


def test_to_csv(sample_sheets, output_dir):
    """Test CSV output format."""
    result = output.to_csv(sample_sheets)
    
    # Save to file
    csv_path = os.path.join(output_dir, "output.csv")
    with open(csv_path, 'w') as f:
        f.write(result)
    print(f"CSV saved: {csv_path}")
    
    lines = result.strip().split('\n')
    
    # Should have header
    assert len(lines) > 0
    assert "Sheet #" in lines[0]
    assert "Panel #" in lines[0]
    assert "Width (mm)" in lines[0]
    
    # Should have data rows
    assert len(lines) > 1


def test_to_text(sample_sheets, output_dir):
    """Test text output format."""
    result = output.to_text(sample_sheets)
    
    # Save to file
    text_path = os.path.join(output_dir, "output.txt")
    with open(text_path, 'w') as f:
        f.write(result)
    print(f"Text saved: {text_path}")
    
    assert "CUTTING PLAN" in result
    assert "Total Sheets:" in result
    assert "Total Panels:" in result
    assert "SHEET 1" in result
    assert "Utilization:" in result


def test_to_ascii(sample_sheets, output_dir):
    """Test ASCII art output format."""
    result = output.to_ascii(sample_sheets)
    
    # Save to file
    ascii_path = os.path.join(output_dir, "output_ascii.txt")
    with open(ascii_path, 'w') as f:
        f.write(result)
    print(f"ASCII saved: {ascii_path}")
    
    assert "Sheet 1" in result
    assert "utilized" in result
    assert "Panels:" in result
    # Should contain border characters
    assert "+" in result or "|" in result or "-" in result


def test_to_svg(sample_sheets, output_dir):
    """Test SVG output format."""
    svg_path = os.path.join(output_dir, "output.svg")
    result = output.to_svg(sample_sheets, filename=svg_path)
    print(f"SVG saved: {svg_path}")
    
    assert result.startswith('<?xml')
    assert '<svg' in result
    assert '</svg>' in result
    assert 'Sheet 1' in result
    assert 'class="panel"' in result
    assert 'font-size: 20px' in result
    assert 'font-size: 18px' in result
    
    # Verify file was created
    assert os.path.exists(svg_path)


def test_to_svg_writes_one_file_per_sheet(output_dir):
    """SVG output should emit one file per sheet when multiple sheets are present."""
    packer = GuillotineAlgorithm()
    panels = [Panel(900, 900), Panel(900, 900)]
    sheets = packer.pack(panels, sheet_width=1000, sheet_height=1000)
    assert len(sheets) == 2

    base_svg_path = os.path.join(output_dir, "multi.svg")
    output.to_svg(sheets, filename=base_svg_path)

    assert os.path.exists(os.path.join(output_dir, "multi_sheet1.svg"))
    assert os.path.exists(os.path.join(output_dir, "multi_sheet2.svg"))


def test_to_svg_includes_panel_label(output_dir):
    """SVG panel text should include the panel label when present."""
    sheet = Sheet(1000, 1000)
    sheet.add_panel(Panel(300, 200, x=0, y=0, label="Door"))

    svg_path = os.path.join(output_dir, "labeled.svg")
    result = output.to_svg([sheet], filename=svg_path)

    assert "Door" in result


def test_to_pdf(sample_sheets, output_dir):
    """Test PDF output generation."""
    pdf_path = os.path.join(output_dir, "output.pdf")

    output.to_pdf(
        sample_sheets,
        filename=pdf_path,
        input_panels=[Panel(400, 600, label="Base")],
        panels_file="tests/data/input.csv",
        sheet_width=1220,
        sheet_height=2440,
        algorithm="guillotine",
        kerf=3.2,
        notes="Kitchen run\nUse oak veneer on visible faces",
    )

    assert os.path.exists(pdf_path)
    with open(pdf_path, "rb") as f:
        header = f.read(4)
    assert header == b"%PDF"


def test_to_svg_font_sizes_are_configurable(output_dir):
    """SVG formatter should accept custom title/label font sizes."""
    sheet = Sheet(1000, 1000)
    sheet.add_panel(Panel(300, 200, x=0, y=0, label="Drawer"))

    result = output.to_svg([sheet], title_font_size=28, label_font_size=24, dimension_font_size=16)

    assert "font-size: 28px" in result
    assert "font-size: 24px" in result
    assert "font-size: 16px" in result


def test_to_svg_includes_dimension_chains(output_dir):
    """SVG should include segment and cumulative dimension chains."""
    sheet = Sheet(1200, 800)
    sheet.add_panel(Panel(600, 400, x=0, y=0, label="A"))
    sheet.add_panel(Panel(600, 400, x=600, y=0, label="B"))

    result = output.to_svg([sheet])

    assert 'class="dim-line"' in result
    assert 'class="dim-text"' in result
    # Segment and cumulative labels should both be present.
    assert ">600<" in result
    assert ">1200<" in result


def test_empty_sheets():
    """Test formatters with empty sheet list."""
    empty_sheets = []
    
    # JSON should handle empty list
    json_result = output.to_json(empty_sheets)
    data = json.loads(json_result)
    assert data["sheets"] == []
    
    # CSV should have header only
    csv_result = output.to_csv(empty_sheets)
    lines = csv_result.strip().split('\n')
    assert len(lines) == 1  # Header only
    
    # Text should show zero sheets
    text_result = output.to_text(empty_sheets)
    assert "Total Sheets: 0" in text_result


def test_output_consistency(sample_sheets):
    """Test that all formats report the same number of sheets and panels."""
    # Get counts from different formats
    json_data = json.loads(output.to_json(sample_sheets))
    json_sheet_count = len(json_data["sheets"])
    json_panel_count = sum(len(s["panels"]) for s in json_data["sheets"])
    
    csv_result = output.to_csv(sample_sheets)
    csv_lines = csv_result.strip().split('\n')
    csv_panel_count = len(csv_lines) - 1  # Subtract header
    
    text_result = output.to_text(sample_sheets)
    
    # All should agree
    assert json_sheet_count == len(sample_sheets)
    assert json_panel_count == csv_panel_count
    assert f"Total Sheets: {json_sheet_count}" in text_result
    assert f"Total Panels: {json_panel_count}" in text_result


def test_outputs_round_dimensions_to_whole_mm():
    """Dimension and coordinate values should be rounded to 0 decimals."""
    sheet = Sheet(1000.4, 499.6)
    panel = Panel(100.7, 200.2, x=10.6, y=20.4)
    sheet.add_panel(panel)
    sheets = [sheet]

    json_result = output.to_json(sheets)
    data = json.loads(json_result)
    panel_data = data["sheets"][0]["panels"][0]

    assert data["sheets"][0]["width"] == 1000
    assert data["sheets"][0]["height"] == 500
    assert panel_data["width"] == 101
    assert panel_data["height"] == 200
    assert panel_data["x"] == 11
    assert panel_data["y"] == 20

    csv_result = output.to_csv(sheets)
    assert "101" in csv_result
    assert "200" in csv_result
    assert "11" in csv_result
    assert "20" in csv_result

    text_result = output.to_text(sheets)
    assert "SHEET 1 - 1000mm × 500mm" in text_result
    assert "101×200" in text_result
    assert "(11, 20)" in text_result
