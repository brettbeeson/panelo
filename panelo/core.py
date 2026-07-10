"""Core functionality for panelo."""

import csv
from pathlib import Path
from typing import List

from panelo.algorithms import FirstFitAlgorithm, GuillotineAlgorithm, MaxRectAlgorithm
from panelo.models import Panel, Sheet


def hello_world() -> str:
    """Return a hello world message.

    Returns:
        str: The hello world message.
    """
    return "Hello World"


def load_panels_from_csv(csv_path: Path) -> List[Panel]:
    """Load panels from a CSV file.

    Expected columns are: width,length,qty

    Args:
        csv_path: Path to CSV file

    Returns:
        Flat list of `Panel` instances expanded by qty
    """
    panels: List[Panel] = []

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("CSV file is empty")

        normalized_fields = {field.strip().lower() for field in reader.fieldnames if field}
        required = {"width", "length", "qty"}
        if not required.issubset(normalized_fields):
            raise ValueError("CSV must contain columns: width,length,qty")

        for row_index, row in enumerate(reader, start=2):
            normalized_row = {
                (key or "").strip().lower(): (value or "").strip()
                for key, value in row.items()
            }

            try:
                width = float(normalized_row.get("width", ""))
                length = float(normalized_row.get("length", ""))
                qty = int(normalized_row.get("qty", ""))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid row {row_index}: expected numeric width,length,qty") from exc

            if width <= 0 or length <= 0:
                raise ValueError(f"Invalid row {row_index}: width and length must be > 0")
            if qty <= 0:
                raise ValueError(f"Invalid row {row_index}: qty must be > 0")

            label = normalized_row.get("label", "")

            for _ in range(qty):
                panels.append(Panel(width, length, label=label))

    if not panels:
        raise ValueError("CSV did not contain any panel rows")

    return panels


def pack_panels(
    panels: List[Panel],
    sheet_width: float,
    sheet_height: float,
    algorithm: str = "guillotine",
    kerf: float = 0.0,
) -> List[Sheet]:
    """Pack panels using the selected algorithm.

    Args:
        panels: Panels to pack
        sheet_width: Sheet width in mm
        sheet_height: Sheet height in mm
        algorithm: One of guillotine, first-fit, maxrect
        kerf: Kerf width (mm) applied as spacing between panels

    Returns:
        Sheets with positioned panels
    """
    if sheet_width <= 0 or sheet_height <= 0:
        raise ValueError("Sheet width and height must be > 0")
    if kerf < 0:
        raise ValueError("Kerf must be >= 0")

    algorithms = {
        "guillotine": GuillotineAlgorithm(),
        "first-fit": FirstFitAlgorithm(),
        "maxrect": MaxRectAlgorithm(),
    }

    if algorithm not in algorithms:
        raise ValueError(
            f"Invalid algorithm '{algorithm}'. Choose from: {', '.join(algorithms.keys())}"
        )

    return algorithms[algorithm].pack(panels, sheet_width, sheet_height, kerf=kerf)
