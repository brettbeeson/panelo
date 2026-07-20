"""Output formatters for panelo packing results."""

import json
import csv
from io import StringIO
from pathlib import Path
from collections import defaultdict
from typing import List, Optional

from panelo.models import Panel, Sheet


def _mm(value: float) -> int:
    """Round a measurement to whole millimeters."""
    return int(round(value))


def _placed_size(panel) -> tuple[int, int]:
    """Get panel placed width/height in whole millimeters."""
    panel_w = panel.height if panel.rotated else panel.width
    panel_h = panel.width if panel.rotated else panel.height
    return _mm(panel_w), _mm(panel_h)


def to_json(sheets: List[Sheet]) -> str:
    """Format sheets as JSON.
    
    Args:
        sheets: List of sheets with placed panels
        
    Returns:
        JSON string with sheet and panel data
    """
    output = []
    
    for i, sheet in enumerate(sheets, 1):
        sheet_data = {
            "sheet_number": i,
            "width": _mm(sheet.width),
            "height": _mm(sheet.height),
            "utilization_percent": round(sheet.get_utilization(), 2),
            "panels": []
        }
        
        for j, panel in enumerate(sheet.panels, 1):
            panel_w, panel_h = _placed_size(panel)
            
            panel_data = {
                "panel_number": j,
                "width": _mm(panel.width),
                "height": _mm(panel.height),
                "x": _mm(panel.x),
                "y": _mm(panel.y),
                "rotated": panel.rotated,
                "actual_width": panel_w,
                "actual_height": panel_h
            }
            sheet_data["panels"].append(panel_data)
        
        output.append(sheet_data)
    
    return json.dumps({"sheets": output}, indent=2)


def to_csv(sheets: List[Sheet]) -> str:
    """Format sheets as CSV for Excel.
    
    Args:
        sheets: List of sheets with placed panels
        
    Returns:
        CSV string with panel data
    """
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Sheet #",
        "Panel #",
        "Width (mm)",
        "Height (mm)",
        "X Position",
        "Y Position",
        "Actual Width",
        "Actual Height"
    ])
    
    # Data rows
    for sheet_num, sheet in enumerate(sheets, 1):
        for panel_num, panel in enumerate(sheet.panels, 1):
            panel_w = panel.height if panel.rotated else panel.width
            panel_h = panel.width if panel.rotated else panel.height
            
            writer.writerow([
                sheet_num,
                panel_num,
                _mm(panel.width),
                _mm(panel.height),
                _mm(panel.x),
                _mm(panel.y),
                panel_w,
                panel_h
            ])
    
    return output.getvalue()


def to_text(sheets: List[Sheet]) -> str:
    """Format sheets as human-readable text.
    
    Args:
        sheets: List of sheets with placed panels
        
    Returns:
        Formatted text string
    """
    lines = []
    lines.append("=" * 80)
    lines.append("CUTTING PLAN")
    lines.append("=" * 80)
    lines.append("")
    
    total_panels = sum(len(s.panels) for s in sheets)
    total_area = sum(_mm(p.width) * _mm(p.height) for sheet in sheets for p in sheet.panels)
    
    lines.append(f"Total Sheets: {len(sheets)}")
    lines.append(f"Total Panels: {total_panels}")
    lines.append(f"Total Panel Area: {total_area:,.0f} mm²")
    lines.append("")
    
    for i, sheet in enumerate(sheets, 1):
        lines.append("-" * 80)
        lines.append(f"SHEET {i} - {_mm(sheet.width)}mm × {_mm(sheet.height)}mm")
        lines.append(f"Utilization: {sheet.get_utilization():.2f}%")
        lines.append("-" * 80)
        lines.append(f"{'Panel':<8} {'Size (mm)':<15} {'Position (mm)':<20} {'Rotated':<10}")
        lines.append("-" * 80)
        
        for j, panel in enumerate(sheet.panels, 1):
            panel_w, panel_h = _placed_size(panel)
            size_str = f"{_mm(panel.width)}×{_mm(panel.height)}"
            pos_str = f"({_mm(panel.x)}, {_mm(panel.y)})"
            rotated_str = "Yes" if panel.rotated else "No"
            
            lines.append(f"{j:<8} {size_str:<15} {pos_str:<20} {rotated_str:<10}")
        
        lines.append("")
    
    lines.append("=" * 80)
    
    return "\n".join(lines)


def to_ascii(sheets: List[Sheet], scale: int = 50) -> str:
    """Format sheets as ASCII art visualization.
    
    Args:
        sheets: List of sheets with placed panels
        scale: Pixels per mm (smaller = more compact)
        
    Returns:
        ASCII art string showing panel layouts
    """
    lines = []
    
    for i, sheet in enumerate(sheets, 1):
        lines.append(
            f"\nSheet {i} ({_mm(sheet.width)}×{_mm(sheet.height)}mm) - {sheet.get_utilization():.1f}% utilized"
        )
        lines.append("")
        
        # Calculate dimensions in characters
        width_chars = int(sheet.width / scale)
        height_chars = int(sheet.height / scale)
        
        # Limit size for readability
        if width_chars > 80:
            scale = sheet.width / 80
            width_chars = 80
            height_chars = int(sheet.height / scale)
        
        if height_chars > 40:
            scale = sheet.height / 40
            height_chars = 40
            width_chars = int(sheet.width / scale)
        
        # Create grid
        grid = [[' ' for _ in range(width_chars + 2)] for _ in range(height_chars + 2)]
        
        # Draw border
        for x in range(width_chars + 2):
            grid[0][x] = '-'
            grid[height_chars + 1][x] = '-'
        for y in range(height_chars + 2):
            grid[y][0] = '|'
            grid[y][width_chars + 1] = '|'
        grid[0][0] = grid[0][width_chars + 1] = grid[height_chars + 1][0] = grid[height_chars + 1][width_chars + 1] = '+'
        
        # Draw panels
        for panel_num, panel in enumerate(sheet.panels, 1):
            panel_w, panel_h = _placed_size(panel)
            
            x1 = int(_mm(panel.x) / scale) + 1
            y1 = int(_mm(panel.y) / scale) + 1
            x2 = int((_mm(panel.x) + panel_w) / scale) + 1
            y2 = int((_mm(panel.y) + panel_h) / scale) + 1
            
            # Ensure within bounds
            x1 = max(1, min(x1, width_chars))
            x2 = max(1, min(x2, width_chars))
            y1 = max(1, min(y1, height_chars))
            y2 = max(1, min(y2, height_chars))
            
            # Draw panel borders
            char = str(panel_num % 10)
            for x in range(x1, x2 + 1):
                if y1 <= height_chars:
                    grid[y1][x] = char
                if y2 <= height_chars:
                    grid[y2][x] = char
            for y in range(y1, y2 + 1):
                if y <= height_chars:
                    grid[y][x1] = char
                    if x2 <= width_chars:
                        grid[y][x2] = char
        
        # Convert grid to string
        for row in grid:
            lines.append(''.join(row))
        
        lines.append("")
        
        # Legend
        lines.append("Panels:")
        for j, panel in enumerate(sheet.panels, 1):
            rot = " (rotated)" if panel.rotated else ""
            lines.append(
                f"  {j}: {_mm(panel.width)}×{_mm(panel.height)}mm at ({_mm(panel.x)}, {_mm(panel.y)}){rot}"
            )
        
        lines.append("")
    
    return "\n".join(lines)


def to_svg(
    sheets: List[Sheet],
    filename: str = None,
    title_font_size: int = 20,
    label_font_size: int = 18,
    dimension_font_size: int =20,
) -> str:
    """Format sheets as SVG graphics.
    
    Args:
        sheets: List of sheets with placed panels
        filename: Optional filename to save to
        
    Returns:
        SVG string
    """
    if not sheets:
        return ""

    def _axis_breaks(sheet: Sheet, axis: str) -> List[int]:
        if axis == "x":
            max_dim = _mm(sheet.width)
        else:
            max_dim = _mm(sheet.height)

        breaks = {0, max_dim}
        for panel in sheet.panels:
            panel_w, panel_h = _placed_size(panel)
            if axis == "x":
                start = _mm(panel.x)
                end = _mm(panel.x) + panel_w
            else:
                start = _mm(panel.y)
                end = _mm(panel.y) + panel_h

            breaks.add(max(0, min(start, max_dim)))
            breaks.add(max(0, min(end, max_dim)))

        return sorted(breaks)

    def _sheet_svg(sheet: Sheet, sheet_num: int) -> str:
        left_margin = 170
        right_margin = 50
        top_margin = 120
        bottom_margin = 50
        sheet_x = left_margin
        sheet_y = top_margin
        sheet_w = _mm(sheet.width)
        sheet_h = _mm(sheet.height)
        svg_width = sheet_w + left_margin + right_margin
        svg_height = sheet_h + top_margin + bottom_margin

        svg_parts = []
        svg_parts.append(f'<?xml version="1.0" encoding="UTF-8"?>')
        svg_parts.append(f'<svg width="{svg_width}" height="{svg_height}" xmlns="http://www.w3.org/2000/svg">')
        svg_parts.append(f'  <style>')
        svg_parts.append(f'    .sheet {{ fill: white; stroke: black; stroke-width: 2; }}')
        svg_parts.append(f'    .panel {{ fill: lightblue; stroke: darkblue; stroke-width: 1; opacity: 0.8; }}')
        svg_parts.append(f'    .text {{ font-family: Arial; font-size: {title_font_size}px; fill: black; }}')
        svg_parts.append(f'    .label {{ font-family: Arial; font-size: {label_font_size}px; fill: darkblue; }}')
        svg_parts.append(f'    .dim-line {{ stroke: #333; stroke-width: 1; fill: none; }}')
        svg_parts.append(f'    .dim-text {{ font-family: Arial; font-size: {dimension_font_size}px; fill: #333; }}')
        svg_parts.append(f'  </style>')

        svg_parts.append(f'  <!-- Sheet {sheet_num} -->')
        svg_parts.append(
            f'  <rect x="{sheet_x}" y="{sheet_y}" width="{sheet_w}" height="{sheet_h}" class="sheet"/>'
        )
        svg_parts.append(
            f'  <text x="{sheet_x}" y="{40}" class="text">Sheet {sheet_num}: {sheet_w}×{sheet_h}mm ({sheet.get_utilization():.1f}%)</text>'
        )

        x_breaks = _axis_breaks(sheet, "x")
        y_breaks = _axis_breaks(sheet, "y")

        # Top dimension chains: line 1 = segment lengths, line 2 = cumulative from left origin.
        top_seg_y = sheet_y - 54
        top_cum_y = sheet_y - 26
        for xb in x_breaks:
            x = sheet_x + xb
            svg_parts.append(f'  <line x1="{x}" y1="{sheet_y}" x2="{x}" y2="{top_cum_y + 4}" class="dim-line"/>')
            svg_parts.append(f'  <line x1="{x}" y1="{top_seg_y - 4}" x2="{x}" y2="{top_seg_y + 4}" class="dim-line"/>')
            svg_parts.append(f'  <line x1="{x}" y1="{top_cum_y - 4}" x2="{x}" y2="{top_cum_y + 4}" class="dim-line"/>')

        for start, end in zip(x_breaks, x_breaks[1:]):
            x1 = sheet_x + start
            x2 = sheet_x + end
            mid = (x1 + x2) / 2
            seg = end - start
            svg_parts.append(f'  <line x1="{x1}" y1="{top_seg_y}" x2="{x2}" y2="{top_seg_y}" class="dim-line"/>')
            svg_parts.append(f'  <line x1="{x1}" y1="{top_cum_y}" x2="{x2}" y2="{top_cum_y}" class="dim-line"/>')
            svg_parts.append(
                f'  <text x="{mid}" y="{top_seg_y - 6}" text-anchor="middle" class="dim-text">{seg}</text>'
            )

        prev_x = -10_000
        top_level = 0
        for xb in x_breaks:
            x = sheet_x + xb
            if x - prev_x < 32:
                top_level = (top_level + 1) % 3
            else:
                top_level = 0
            top_label_y = top_cum_y - 6 - (top_level * 10)
            svg_parts.append(
                f'  <text x="{x}" y="{top_label_y}" text-anchor="middle" class="dim-text">{xb}</text>'
            )
            prev_x = x

        # Left dimension chains: line 1 = segment lengths, line 2 = cumulative from top origin.
        left_seg_x = sheet_x - 88
        left_cum_x = sheet_x - 44
        for yb in y_breaks:
            y = sheet_y + yb
            svg_parts.append(f'  <line x1="{sheet_x}" y1="{y}" x2="{left_cum_x + 4}" y2="{y}" class="dim-line"/>')
            svg_parts.append(f'  <line x1="{left_seg_x - 4}" y1="{y}" x2="{left_seg_x + 4}" y2="{y}" class="dim-line"/>')
            svg_parts.append(f'  <line x1="{left_cum_x - 4}" y1="{y}" x2="{left_cum_x + 4}" y2="{y}" class="dim-line"/>')

        for start, end in zip(y_breaks, y_breaks[1:]):
            y1 = sheet_y + start
            y2 = sheet_y + end
            mid = (y1 + y2) / 2
            seg = end - start
            svg_parts.append(f'  <line x1="{left_seg_x}" y1="{y1}" x2="{left_seg_x}" y2="{y2}" class="dim-line"/>')
            svg_parts.append(f'  <line x1="{left_cum_x}" y1="{y1}" x2="{left_cum_x}" y2="{y2}" class="dim-line"/>')
            svg_parts.append(
                f'  <text x="{left_seg_x - 6}" y="{mid}" text-anchor="middle" class="dim-text" '
                f'transform="rotate(-90 {left_seg_x - 6} {mid})">{seg}</text>'
            )

        prev_y = -10_000
        left_level = 0
        for yb in y_breaks:
            y = sheet_y + yb
            if y - prev_y < 26:
                left_level = (left_level + 1) % 3
            else:
                left_level = 0
            left_label_x = left_cum_x - 6 - (left_level * 10)
            svg_parts.append(
                f'  <text x="{left_label_x}" y="{y}" text-anchor="middle" class="dim-text" '
                f'transform="rotate(-90 {left_label_x} {y})">{yb}</text>'
            )
            prev_y = y

        for panel_num, panel in enumerate(sheet.panels, 1):
            panel_w, panel_h = _placed_size(panel)
            px = sheet_x + _mm(panel.x)
            py = sheet_y + _mm(panel.y)

            svg_parts.append(f'  <rect x="{px}" y="{py}" width="{panel_w}" height="{panel_h}" class="panel"/>')

            label_x = px + panel_w / 2
            label_y = py + panel_h / 2
            # rot_text = " R" if panel.rotated else ""
            panel_label = panel.label if getattr(panel, "label", "") else f"Panel {panel_num}"
            svg_parts.append(
                f'  <text x="{label_x}" y="{label_y}" class="label" text-anchor="middle">{panel_label} ({_mm(panel.width)}×{_mm(panel.height)})</text>'
            )

        svg_parts.append('</svg>')
        return '\n'.join(svg_parts)

    svg_docs = [_sheet_svg(sheet, sheet_num) for sheet_num, sheet in enumerate(sheets, 1)]

    if filename:
        file_path = Path(filename)
        if len(svg_docs) == 1:
            file_path.write_text(svg_docs[0], encoding="utf-8")
        else:
            for i, svg_doc in enumerate(svg_docs, start=1):
                sheet_file = file_path.with_name(f"{file_path.stem}_sheet{i}{file_path.suffix or '.svg'}")
                sheet_file.write_text(svg_doc, encoding="utf-8")

    return svg_docs[0] if len(svg_docs) == 1 else "\n\n".join(svg_docs)


def to_pdf(
    sheets: List[Sheet],
    filename: str,
    input_panels: Optional[List[Panel]] = None,
    panels_file: Optional[str] = None,
    sheet_width: Optional[float] = None,
    sheet_height: Optional[float] = None,
    algorithm: Optional[str] = None,
    kerf: Optional[float] = None,
    notes: Optional[str] = None,
    svg_dimension_font_size: int =20,
) -> None:
    """Write a PDF cutting report via HTML+WeasyPrint.

    Page 1: inputs, notes, cut list.  Page 2+: sheet layout SVGs, two per row.
    """
    try:
        import weasyprint
    except ImportError as exc:
        raise RuntimeError("PDF export requires 'weasyprint'. Run: uv add weasyprint") from exc

    # ------------------------------------------------------------------ helpers
    def _esc(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _trows(rows: List[List[str]]) -> str:
        out = []
        for row in rows:
            cells = "".join(f"<td>{_esc(str(c))}</td>" for c in row)
            out.append(f"<tr>{cells}</tr>")
        return "\n".join(out)

    CSS = """
    @page { size: A4; margin: 18mm 14mm; @bottom-right { content: counter(page) " / " counter(pages); font-size: 8pt; color: #666; } }
    body { font-family: Helvetica, Arial, sans-serif; font-size: 9pt; color: #111; }
    h1 { font-size: 16pt; margin: 0 0 10pt; }
    h2 { font-size: 11pt; margin: 14pt 0 4pt; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 10pt; }
    th { background: #e8eef8; text-align: left; padding: 3pt 5pt; font-size: 8.5pt; border: 0.5pt solid #aaa; }
    td { padding: 2pt 5pt; font-size: 8pt; border: 0.5pt solid #ccc; vertical-align: top; }
    tr:nth-child(even) td { background: #f7f9fd; }
    .notes td { font-size: 9pt; white-space: pre-wrap; }
    .page-break { page-break-before: always; }
    .sheet-grid { display: grid; grid-template-columns: 1fr; gap: 10pt; }
    .sheet-cell { break-inside: avoid; }
    .sheet-label { font-size: 8pt; font-weight: bold; margin-bottom: 3pt; }
    .sheet-cell svg { width: 100%; height: auto; display: block; }
    """

    # ------------------------------------------------------------------ page 1
    info_rows_data: List[List[str]] = []
    # if panels_file:
    #     info_rows_data.append(["CSV", panels_file])
    if sheet_width is not None and sheet_height is not None:
        info_rows_data.append(["Sheet Size", f"{_mm(sheet_width)} × {_mm(sheet_height)} mm"])
    # if algorithm is not None:
    #     info_rows_data.append(["Algorithm", algorithm])
    if kerf is not None:
        info_rows_data.append(["Kerf", f"{kerf:g} mm"])
    info_rows_data.append(["Total Sheets", str(len(sheets))])
    info_rows_data.append(["Total Panels", str(sum(len(s.panels) for s in sheets))])

    info_html = (
        "<table><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody>"
        + _trows(info_rows_data)
        + "</tbody></table>"
    )

    notes_text = (notes or "").strip() or "-"
    notes_html = f'<table class="notes"><tbody><tr><td>{_esc(notes_text)}</td></tr></tbody></table>'

    demand_html = ""
    if input_panels:
        grouped: dict = defaultdict(int)
        for p in input_panels:
            key = (p.label or "-", _mm(p.width), _mm(p.height))
            grouped[key] += 1
        demand_rows_data = [
            [str(qty), label, f"{w} × {h} mm"]
            for (label, w, h), qty in sorted(grouped.items())
        ]
        demand_html = (
            "<h2>Cut Panels Summary</h2>"
            "<table><thead><tr><th>Qty</th><th>Label</th><th>Size</th></tr></thead><tbody>"
            + _trows(demand_rows_data)
            + "</tbody></table>"
        )

    cut_rows_data = [
        [str(sn), str(pn), panel.label or "-",
         f"{_mm(panel.width)} × {_mm(panel.height)}",
         f"({_mm(panel.x)}, {_mm(panel.y)})"]
        for sn, sheet in enumerate(sheets, 1)
        for pn, panel in enumerate(sheet.panels, 1)
    ]
    cut_html = (
        "<h2>Cut Panels</h2>"
        "<table><thead><tr><th>Sheet</th><th>#</th><th>Label</th><th>Size (mm)</th><th>Position</th></tr></thead><tbody>"
        + _trows(cut_rows_data)
        + "</tbody></table>"
    )

    # ------------------------------------------------------------------ page 2+
    sheet_cells = []
    for sheet_num, sheet in enumerate(sheets, 1):
        svg_doc = to_svg(
            [sheet],
            title_font_size=20,
            label_font_size=18,
            dimension_font_size=svg_dimension_font_size,
        )
        # Strip XML declaration so SVG embeds cleanly in HTML
        svg_doc = svg_doc.replace('<?xml version="1.0" encoding="UTF-8"?>', "").strip()
        label = f"Sheet {sheet_num} — {_mm(sheet.width)} × {_mm(sheet.height)} mm  ({sheet.get_utilization():.1f}%)"
        sheet_cells.append(
            f'<div class="sheet-cell">'
            f'<div class="sheet-label">{_esc(label)}</div>'
            f'{svg_doc}'
            f'</div>'
        )
    layouts_html = (
        f'<div class="page-break"></div>'
        f'<h2>Sheet Layouts</h2>'
        f'<div class="sheet-grid">{chr(10).join(sheet_cells)}</div>'
    ) if sheet_cells else ""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body>
<h1>Panelo Cutting Report</h1>
<h2>Inputs</h2>{info_html}
<h2>Notes</h2>{notes_html}
{demand_html}
{cut_html}
{layouts_html}
</body></html>"""

    weasyprint.HTML(string=html).write_pdf(filename)


