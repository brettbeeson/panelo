# Panelo

Panelo optimizes plywood cut layouts from CSV input and produces practical outputs for workshop use.

## Features

- CSV input with `width,length,qty` and optional `label`
- Multiple packing algorithms: `guillotine`, `maxrect`, `first-fit`
- Kerf support (`--kerf`)
- Output formats: text, CSV, JSON, ASCII, SVG, PDF
- NiceGUI web app for editing inputs, running plans, and downloading artifacts

## Installation

Recommended with `uv`:

```bash
uv sync
```

Or editable install:

```bash
pip install -e .
```

## CLI Usage

```bash
panelo [OPTIONS] PANELS_FILE SHEET_WIDTH SHEET_HEIGHT [OUTPUT_BASE]
```

Examples:

```bash
# Basic run (prints text plan to stdout)
panelo tests/data/input.csv 2400 1200

# Kerf-aware run
panelo tests/data/input.csv 2400 1200 --kerf 4

# Select algorithm
panelo tests/data/input.csv 2400 1200 --algorithm maxrect

# Write all artifacts using a base path
panelo tests/data/input.csv 2400 1200 output/plan
```

When `OUTPUT_BASE` is provided, Panelo writes:

- `OUTPUT_BASE.txt`
- `OUTPUT_BASE.csv`
- `OUTPUT_BASE.json`
- `OUTPUT_BASE.ascii.txt`
- `OUTPUT_BASE.pdf`
- `OUTPUT_BASE_sheetN.svg` (one SVG per sheet)

## CSV Input Format

Required columns:

```csv
width,length,qty,label
550,1842,6,Base/Top
390,1842,6,Front/Back
424,550,6,Left/Right
```

- `label` is optional
- Dimensions are in millimeters
- `qty` must be a positive integer

## Web App

Run locally:

```bash
uv run panelo-web
```

Web app highlights:

- Editable cut input table
- Upload CSV button
- Add row / remove last row / reset controls
- Notes card (included in PDF report)
- Tabs for cut list, layouts, and downloads
- Per-run artifacts stored under `runs/<run_id>/`

## PDF Behavior

- Generated via WeasyPrint from HTML
- Page 1 includes inputs, notes, demand, and cut list
- Following pages include sheet layout SVGs in single-column flow

## Development

Run tests:

```bash
uv run pytest -q
```
