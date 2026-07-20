"""Local NiceGUI web app for panelo."""

from collections import defaultdict

import csv
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from nicegui import app, ui

from panelo import output as output_formatters
from panelo.core import pack_panels
from panelo.models import Panel

_last_submit: dict[str, float] = defaultdict(float)
SUBMIT_COOLDOWN = 30


def can_submit(client_id: str) -> bool:
    now = time.monotonic()

    if now - _last_submit[client_id] < SUBMIT_COOLDOWN:
        return False

    _last_submit[client_id] = now
    return True



def _env_int(name: str, default: int) -> int:
    """Read an integer env var with a safe default."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_path(name: str, default: str) -> Path:
    """Read a filesystem path env var with a safe default."""
    raw = os.getenv(name, "").strip()
    return Path(raw or default)


def _normalize_base_path(value: str) -> str:
    """Normalize base path for reverse proxy deployment."""
    raw = (value or "").strip()
    if not raw or raw == "/":
        return ""
    if not raw.startswith("/"):
        raw = f"/{raw}"
    return raw.rstrip("/")


APP_HOST = os.getenv("PANELO_HOST", "127.0.0.1")
APP_PORT = _env_int("PANELO_PORT", 7070)
APP_BASE_PATH = _normalize_base_path(os.getenv("PANELO_BASE_PATH", ""))
RUNS_ROUTE = f"{APP_BASE_PATH}/runs" if APP_BASE_PATH else "/runs"
APP_ROUTE = f"{APP_BASE_PATH}/" if APP_BASE_PATH else "/"
RUNS_ROOT = _env_path("PANELO_RUNS_ROOT", "runs")
RUN_RETENTION_DAYS = _env_int("PANELO_RUN_RETENTION_DAYS", 30)
LOCAL_PROJECTS_STORAGE_KEY = "panelo.projects.v1"
LOCAL_PROJECTS_MAX = 20


def _cleanup_old_runs() -> int:
    """Delete run directories older than configured retention days."""
    if RUN_RETENTION_DAYS <= 0:
        return 0

    cutoff_ts = time.time() - (RUN_RETENTION_DAYS * 24 * 60 * 60)
    deleted = 0

    if not RUNS_ROOT.exists():
        return 0

    for child in RUNS_ROOT.iterdir():
        if not child.is_dir():
            continue

        try:
            if child.stat().st_mtime < cutoff_ts:
                shutil.rmtree(child, ignore_errors=True)
                deleted += 1
        except OSError:
            # Ignore transient filesystem errors; cleanup is best-effort.
            continue

    return deleted


RUNS_ROOT.mkdir(parents=True, exist_ok=True)
_cleanup_old_runs()
app.add_static_files(RUNS_ROUTE, str(RUNS_ROOT.resolve()))


def _default_input_path() -> Path:
    """Return the packaged default input CSV path."""
    return Path(__file__).with_name("input.csv")


def _load_default_rows() -> List[Dict[str, Any]]:
    """Load default table rows from packaged input.csv."""
    try:
        return _import_csv_replace(_default_input_path())
    except Exception:
        return [{"width": 600, "length": 400, "qty": 1, "label": ""}]


def _svg_for_web(svg_text: str) -> str:
    """Wrap and style SVG so full layout fits in the visible results pane."""
    if "<svg" not in svg_text:
        return svg_text

    open_tag_match = re.search(r"<svg\b([^>]*)>", svg_text)
    if not open_tag_match:
        return svg_text

    attrs = open_tag_match.group(1)

    width_match = re.search(r'\bwidth="([0-9.]+)"', attrs)
    height_match = re.search(r'\bheight="([0-9.]+)"', attrs)

    if "viewBox" not in attrs and width_match and height_match:
        width = float(width_match.group(1))
        height = float(height_match.group(1))
        attrs += f' viewBox="0 0 {int(round(width))} {int(round(height))}"'

    if "preserveAspectRatio" not in attrs:
        attrs += ' preserveAspectRatio="xMidYMid meet"'

    attrs = re.sub(r'\s\bwidth="[^"]*"', "", attrs)
    attrs = re.sub(r'\s\bheight="[^"]*"', "", attrs)

    responsive_style = "width: 100%; height: auto; display: block; margin: 0 auto;"
    style_match = re.search(r'\bstyle="([^"]*)"', attrs)
    if style_match:
        existing_style = style_match.group(1).strip()
        combined = f"{existing_style}; {responsive_style}" if existing_style else responsive_style
        attrs = re.sub(r'\bstyle="[^"]*"', f'style="{combined}"', attrs)
    else:
        attrs += f' style="{responsive_style}"'

    new_open_tag = f"<svg{attrs}>"
    styled = svg_text.replace(open_tag_match.group(0), new_open_tag, 1)
    return f'<div style="width: 100%; overflow: auto;">{styled}</div>'


@dataclass
class AppState:
    """Mutable app state for UI interactions."""

    rows: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"width": 600, "length": 400, "qty": 1, "label": ""}
    ])
    sheet_width: int = 2400
    sheet_height: int = 1200
    kerf: float = 4.0
    algorithm: str = "guillotine"
    svg_title_font_size: int = 40
    svg_label_font_size: int = 30
    svg_dimension_font_size: int = 16
    notes: str = ""
    current_run_id: str = ""
    current_project_id: str = ""
    current_project_name: str = "Untitled Project"
    latest_run_summary: Dict[str, Any] = field(default_factory=dict)

    # latest run outputs
    last_error: str = ""
    last_info: str = ""
    last_file_paths: List[str] = field(default_factory=list)
    text_output: str = ""
    csv_output: str = ""
    json_output: str = ""
    ascii_output: str = ""
    svg_preview: str = ""


def _parse_row(row: Dict[str, Any], row_num: int) -> Dict[str, Any]:
    """Validate and normalize a UI table row."""
    try:
        width = float(row.get("width", 0))
        length = float(row.get("length", 0))
        qty = int(row.get("qty", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Row {row_num}: width/length/qty must be numeric") from exc

    if width <= 0 or length <= 0:
        raise ValueError(f"Row {row_num}: width and length must be > 0")
    if qty <= 0:
        raise ValueError(f"Row {row_num}: qty must be > 0")

    return {
        "width": width,
        "length": length,
        "qty": qty,
        "label": str(row.get("label", "")).strip(),
    }


def _rows_to_csv(rows: List[Dict[str, Any]]) -> str:
    """Serialize table rows to CSV expected by core loader."""
    out = ["width,length,qty,label"]
    for row in rows:
        safe_label = str(row["label"]).replace(",", " ")
        out.append(f"{row['width']},{row['length']},{row['qty']},{safe_label}")
    return "\n".join(out) + "\n"


def _import_csv_replace(path: Path) -> List[Dict[str, Any]]:
    """Import CSV rows and replace current table content."""
    imported: List[Dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("CSV is empty")

        for idx, raw_row in enumerate(reader, start=2):
            normalized = {(k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items()}
            try:
                width = float(normalized.get("width", ""))
                length = float(normalized.get("length", ""))
                qty = int(normalized.get("qty", ""))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid CSV row {idx}") from exc

            if width <= 0 or length <= 0 or qty <= 0:
                raise ValueError(f"Invalid CSV row {idx}: dimensions/qty must be > 0")

            imported.append(
                {
                    "width": int(round(width)),
                    "length": int(round(length)),
                    "qty": qty,
                    "label": normalized.get("label", ""),
                }
            )

    if not imported:
        raise ValueError("CSV did not contain any usable rows")

    return imported


def _import_csv_bytes_replace(content: bytes) -> List[Dict[str, Any]]:
    """Import CSV rows from uploaded file bytes and replace table content."""
    imported: List[Dict[str, Any]] = []
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))

    if reader.fieldnames is None:
        raise ValueError("CSV is empty")

    for idx, raw_row in enumerate(reader, start=2):
        normalized = {(k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items()}
        try:
            width = float(normalized.get("width", ""))
            length = float(normalized.get("length", ""))
            qty = int(normalized.get("qty", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid CSV row {idx}") from exc

        if width <= 0 or length <= 0 or qty <= 0:
            raise ValueError(f"Invalid CSV row {idx}: dimensions/qty must be > 0")

        imported.append(
            {
                "width": int(round(width)),
                "length": int(round(length)),
                "qty": qty,
                "label": normalized.get("label", ""),
            }
        )

    if not imported:
        raise ValueError("CSV did not contain any usable rows")

    return imported


def _new_run_dir() -> tuple[str, Path]:
    """Create a new run directory under runs/ and return (run_id, path)."""
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    _cleanup_old_runs()
    run_id = uuid4().hex[:16]
    run_dir = RUNS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


@ui.page('/')
def main_page() -> None:
    """Build the main web page."""
    state = AppState()
    state.rows = _load_default_rows()

    def _empty_project_store() -> Dict[str, Any]:
        return {"version": 1, "currentProjectId": "", "projects": []}

    async def _read_project_store() -> Dict[str, Any]:
        script = (
            "(() => {"
            "try { return localStorage.getItem(" + json.dumps(LOCAL_PROJECTS_STORAGE_KEY) + ") || ''; }"
            "catch (e) { return ''; }"
            "})()"
        )
        raw = await ui.run_javascript(script)
        if not raw:
            return _empty_project_store()
        try:
            store = json.loads(raw)
        except (TypeError, ValueError):
            return _empty_project_store()
        if not isinstance(store, dict):
            return _empty_project_store()
        if not isinstance(store.get("projects"), list):
            store["projects"] = []
        if not isinstance(store.get("currentProjectId"), str):
            store["currentProjectId"] = ""
        store["version"] = 1
        return store

    async def _write_project_store(store: Dict[str, Any]) -> None:
        payload = json.dumps(store, separators=(",", ":"))
        script = (
            "(() => {"
            "try { localStorage.setItem(" + json.dumps(LOCAL_PROJECTS_STORAGE_KEY) + ", " + json.dumps(payload) + "); }"
            "catch (e) {}"
            "})()"
        )
        await ui.run_javascript(script)

    ui.colors(
        primary="#2563eb",
        secondary="#64748b",
        accent="#0f766e",
        positive="#16a34a",
        negative="#dc2626",
        warning="#d97706",
        info="#0284c7",
    )

    ui.add_head_html(
        """
        <style>
          body {
            background: radial-gradient(circle at 20% 20%, #f8fbff 0%, #eef3ff 45%, #f7f8fa 100%);
          }

          .app-shell .q-card {
            border-radius: 14px;
          }
        </style>
        """
    )

    with ui.header(elevated=False).classes("bg-white border-b border-slate-200 px-6 py-3"):
        with ui.row().classes("w-full max-w-[1600px] mx-auto items-center justify-between"):
            with ui.column().classes("gap-0"):
                ui.label("Panelo ").classes("text-2xl md:text-3xl font-bold text-slate-800")
                ui.label("Cut sheets into panels").classes("text-sm text-slate-600")

    with ui.column().classes("w-full max-w-[1600px] mx-auto p-4 md:p-6 gap-4 app-shell"):

        with ui.row().classes("w-full gap-4 flex-wrap lg:flex-nowrap items-start"):
            with ui.column().classes("w-full lg:w-[430px] shrink-0 gap-4"):
                with ui.card().classes("w-full"):
                    ui.label("Project").classes("text-lg font-semibold")
                    project_name_input = ui.input("Project Name", value=state.current_project_name).classes("w-full")
                    project_select = ui.select(options={}, label="Saved Projects").classes("w-full")
                    with ui.row().classes("w-full gap-2"):
                        new_project_button = ui.button("New Project").props("color=secondary")
                        delete_project_button = ui.button("Delete Project").props("color=warning")

                with ui.card().classes("w-full"):
                    ui.label("Stock Sheets").classes("text-lg font-semibold")
                    with ui.row().classes("w-full gap-3"):
                        sheet_width_input = ui.number("Sheet Width (mm)", value=state.sheet_width, min=1).classes("w-36")
                        sheet_height_input = ui.number("Sheet Height (mm)", value=state.sheet_height, min=1).classes("w-36")
                        kerf_input = ui.number("Kerf (mm)", value=state.kerf, min=0, step=0.1).classes("w-28")

                    with ui.expansion("Preferences", icon="settings").classes("w-full"):
                        with ui.column().classes("w-full gap-3"):
                            algo_select = ui.select(
                                options=["guillotine", "first-fit", "maxrect"],
                                value=state.algorithm,
                                label="Algorithm",
                            ).classes("w-full")
                            with ui.row().classes("w-full gap-3"):
                                svg_title_font_input = ui.number("SVG Title Font", value=state.svg_title_font_size, min=6).classes("w-40")
                                svg_label_font_input = ui.number("SVG Label Font", value=state.svg_label_font_size, min=6).classes("w-40")
                                svg_dimension_font_input = ui.number("SVG Dimension Font", value=state.svg_dimension_font_size, min=6).classes("w-40")
                            ui.label("JSON/ASCII are still generated for Downloads.").classes("text-xs text-slate-500")

                with ui.card().classes("w-full"):
                    ui.label("Cut Inputs").classes("text-lg font-semibold")

                    grid = ui.aggrid(
                        {
                            "columnDefs": [
                                {"headerName": "Width", "field": "width", "editable": True, "type": "numericColumn"},
                                {"headerName": "Length", "field": "length", "editable": True, "type": "numericColumn"},
                                {"headerName": "Qty", "field": "qty", "editable": True, "type": "numericColumn"},
                                {"headerName": "Label", "field": "label", "editable": True},
                            ],
                            "rowData": state.rows,
                            "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
                            "stopEditingWhenCellsLoseFocus": True,
                            "animateRows": True,
                        }
                    ).classes("w-full h-72")

                    with ui.row().classes("gap-2 pt-2"):
                        async def _load_live_rows() -> List[Dict[str, Any]]:
                            live_rows = await grid.get_client_data(timeout=2)
                            return list(live_rows) if live_rows else list(state.rows)

                        def _refresh_input_grid() -> None:
                            grid.options["rowData"] = state.rows
                            grid.update()

                        async def add_row() -> None:
                            state.rows = await _load_live_rows()
                            state.rows.append({"width": 600, "length": 400, "qty": 1, "label": ""})
                            _refresh_input_grid()
                            await _save_current_project()

                        async def remove_last_row() -> None:
                            state.rows = await _load_live_rows()
                            if state.rows:
                                state.rows.pop()
                            if not state.rows:
                                state.rows = [{"width": 600, "length": 400, "qty": 1, "label": ""}]
                            _refresh_input_grid()
                            await _save_current_project()

                        async def clear_reset() -> None:
                            state.rows = [{"width": "", "length": "", "qty": "", "label": ""}]
                            _refresh_input_grid()
                            state.notes = ""
                            notes_input.set_value("")
                            state.current_run_id = ""
                            state.latest_run_summary = {}
                            summary_box.set_content("No runs yet.")
                            cut_grid.options["rowData"] = []
                            cut_grid.update()
                            layouts_container.clear()
                            with layouts_container:
                                ui.label("No layout yet.").classes("text-slate-500")
                            downloads_container.clear()
                            with downloads_container:
                                ui.label("No files yet.").classes("text-slate-500")
                            await _save_current_project()
                            ui.notify("Reset to one blank row.", type="info")

                        async def import_csv_upload(e) -> None:
                            try:
                                uploaded = e.content.read()
                                state.rows = _import_csv_bytes_replace(uploaded)
                                grid.rows = state.rows
                                grid.update()
                                await _save_current_project()
                                message = f"Imported {len(state.rows)} rows from uploaded CSV"
                                ui.notify(message, type="positive")
                            except Exception as exc:
                                message = f"Import error: {exc}"
                                ui.notify(message, type="negative", multi_line=True)

                        csv_uploader = ui.upload(
                            on_upload=import_csv_upload,
                            auto_upload=True,
                        ).props('accept=.csv').style('display:none')

                        def open_csv_picker() -> None:
                            ui.run_javascript(
                                f'document.querySelector("#c{csv_uploader.id} input[type=file]").click()'
                            )

                        ui.button("Add Row", on_click=add_row).props("color=primary")
                        ui.button("Remove Row", on_click=remove_last_row).props("color=warning")
                        ui.button("Reset", on_click=clear_reset).props("color=warning")
                        ui.button("CSV", on_click=open_csv_picker).props("color=secondary")

                with ui.row().classes("w-full"):
                    run_button = ui.button("Let's Cut!").props("color=primary size=lg")

                with ui.card().classes("w-full"):
                    ui.label("Notes").classes("text-lg font-semibold")
                    notes_input = ui.textarea(
                        label="",
                        value=state.notes,
                        placeholder="",
                    ).classes("w-full")
                    notes_input.props("rows=5")

                
            with ui.column().classes("w-full flex-1 min-w-[360px] gap-4"):
                with ui.tabs().classes("w-full") as tabs:
                    summary_tab = ui.tab("Cut List")
                    layouts_tab = ui.tab("Layouts")
                    downloads_tab = ui.tab("Downloads")

                with ui.tab_panels(tabs, value=summary_tab).classes("w-full"):
                    with ui.tab_panel(summary_tab):
                        summary_box = ui.markdown("No runs yet.")
                        cut_grid = ui.aggrid(
                            {
                                "columnDefs": [
                                    {"headerName": "Sheet", "field": "sheet"},
                                    {"headerName": "#", "field": "panel_number"},
                                    {"headerName": "Label", "field": "label"},
                                    {"headerName": "Size (mm)", "field": "size"},
                                    {"headerName": "Position", "field": "position"},
                                ],
                                "rowData": [],
                                "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
                                "domLayout": "autoHeight",
                                "animateRows": True,
                            }
                        ).classes("w-full").style("height: auto;")
                    with ui.tab_panel(layouts_tab):
                        layouts_container = ui.column().classes("w-full gap-4")
                        with layouts_container:
                            ui.label("No layout yet.").classes("text-slate-500")
                    with ui.tab_panel(downloads_tab):
                        downloads_container = ui.column().classes("w-full gap-2")
                        with downloads_container:
                            ui.label("No files yet.").classes("text-slate-500")

        def _project_options(store: Dict[str, Any]) -> Dict[str, str]:
            options: Dict[str, str] = {}
            for project in store.get("projects", []):
                project_id = str(project.get("id", "")).strip()
                if not project_id:
                    continue
                options[project_id] = str(project.get("name", "Untitled Project")).strip() or "Untitled Project"
            return options

        async def _get_normalized_rows() -> List[Dict[str, Any]]:
            live_rows = await grid.get_client_data(timeout=2)
            if not live_rows:
                live_rows = state.rows
            return [_parse_row(r, i) for i, r in enumerate(live_rows, start=1)]

        def _apply_project_to_controls(project: Dict[str, Any]) -> None:
            inputs = project.get("inputs", {})
            state.current_project_id = project["id"]
            state.current_project_name = project["name"]
            state.rows = list(inputs.get("rows", state.rows))
            state.sheet_width = int(inputs.get("sheet_width", state.sheet_width))
            state.sheet_height = int(inputs.get("sheet_height", state.sheet_height))
            state.kerf = float(inputs.get("kerf", state.kerf))
            state.algorithm = str(inputs.get("algorithm", state.algorithm))
            state.svg_title_font_size = int(inputs.get("svg_title_font_size", state.svg_title_font_size))
            state.svg_label_font_size = int(inputs.get("svg_label_font_size", state.svg_label_font_size))
            state.svg_dimension_font_size = int(inputs.get("svg_dimension_font_size", state.svg_dimension_font_size))
            state.notes = str(inputs.get("notes", state.notes))
            state.latest_run_summary = dict(project.get("latest_run", {}))

            project_name_input.set_value(state.current_project_name)
            sheet_width_input.set_value(state.sheet_width)
            sheet_height_input.set_value(state.sheet_height)
            kerf_input.set_value(state.kerf)
            algo_select.set_value(state.algorithm)
            svg_title_font_input.set_value(state.svg_title_font_size)
            svg_label_font_input.set_value(state.svg_label_font_size)
            svg_dimension_font_input.set_value(state.svg_dimension_font_size)
            notes_input.set_value(state.notes)
            grid.options["rowData"] = state.rows
            grid.update()

            latest = state.latest_run_summary
            if latest:
                summary_box.set_content(
                    "\n".join(
                        [
                            "**Last Saved Run**",
                            f"- Run ID: {latest.get('run_id', '-')}",
                            f"- Panels expanded: {latest.get('panels_expanded', '-')}",
                            f"- Sheets: {latest.get('sheet_count', '-')}",
                            f"- Utilization avg: {latest.get('avg_utilization_percent', '-')}",
                        ]
                    )
                )
            else:
                summary_box.set_content("No runs yet.")

        async def _load_saved_run_for_current_project() -> None:
            latest = state.latest_run_summary or {}
            run_id = str(latest.get("run_id", "")).strip()
            if not run_id:
                state.current_run_id = ""
                state.last_file_paths = []
                cut_grid.options["rowData"] = []
                cut_grid.update()
                layouts_container.clear()
                with layouts_container:
                    ui.label("No layout yet.").classes("text-slate-500")
                downloads_container.clear()
                with downloads_container:
                    ui.label("No files yet.").classes("text-slate-500")
                return

            run_dir = RUNS_ROOT / run_id
            state.current_run_id = run_id

            generated_files = latest.get("generated_files", [])
            candidate_files: List[Path] = []
            if isinstance(generated_files, list) and generated_files:
                for filename in generated_files:
                    path = run_dir / str(filename)
                    if path.exists():
                        candidate_files.append(path)

            if not candidate_files and run_dir.exists():
                fallback_patterns = ["plan.txt", "plan.csv", "plan.json", "plan.ascii.txt", "plan.pdf", "plan.svg", "plan_sheet*.svg"]
                for pattern in fallback_patterns:
                    candidate_files.extend(sorted(run_dir.glob(pattern)))

            state.last_file_paths = [str(path) for path in candidate_files]

            json_path = run_dir / "plan.json"
            cut_rows: List[Dict[str, Any]] = []
            if json_path.exists():
                try:
                    data = json.loads(json_path.read_text(encoding="utf-8"))
                    for sheet in data.get("sheets", []):
                        sheet_num = sheet.get("sheet_number", "-")
                        for panel in sheet.get("panels", []):
                            cut_rows.append(
                                {
                                    "sheet": sheet_num,
                                    "panel_number": panel.get("panel_number", "-"),
                                    "label": "-",
                                    "size": f"{panel.get('width', '-')} x {panel.get('height', '-')}",
                                    "position": f"({panel.get('x', '-')}, {panel.get('y', '-')})",
                                }
                            )
                except Exception:
                    cut_rows = []

            cut_grid.options["rowData"] = cut_rows
            cut_grid.update()

            layouts_container.clear()
            svg_sheet_paths = sorted(run_dir.glob("plan_sheet*.svg"))
            if svg_sheet_paths:
                for i, svg_file in enumerate(svg_sheet_paths, start=1):
                    with layouts_container:
                        ui.label(f"Sheet {i}").classes("font-semibold text-slate-700")
                        ui.html(_svg_for_web(svg_file.read_text(encoding="utf-8"))).classes("w-full")
            else:
                svg_path = run_dir / "plan.svg"
                if svg_path.exists():
                    with layouts_container:
                        ui.html(_svg_for_web(svg_path.read_text(encoding="utf-8"))).classes("w-full")
                else:
                    with layouts_container:
                        ui.label("No layout file found for this project run.").classes("text-slate-500")

            downloads_container.clear()
            with downloads_container:
                ui.label("Downloads").classes("text-lg font-semibold text-slate-700")
                ui.label("View opens in new tab. Right-click there to save directly.").classes("text-xs text-slate-500")

                if not state.last_file_paths:
                    ui.label("No files found for this saved run.").classes("text-slate-500")
                else:
                    with ui.column().classes("w-full gap-0"):
                        pdf_paths = [fp for fp in state.last_file_paths if fp.endswith(".pdf")]
                        other_paths = [fp for fp in state.last_file_paths if not fp.endswith(".pdf")]
                        for file_path in pdf_paths + other_paths:
                            p = Path(file_path)
                            is_pdf = p.suffix.lower() == ".pdf"
                            file_url = f"{RUNS_ROUTE}/{state.current_run_id}/{p.name}"
                            row_classes = "w-full items-center justify-between gap-3 py-1.5 border-b border-slate-200"
                            if is_pdf:
                                row_classes += " bg-slate-50"
                            with ui.row().classes(row_classes):
                                link_classes = "text-sm break-all " + ("font-bold text-slate-900" if is_pdf else "text-slate-600")
                                ui.link(p.name, file_url, new_tab=True).classes(link_classes)

            if run_dir.exists():
                summary_box.set_content(
                    "\n".join(
                        [
                            "**Loaded Saved Run**",
                            f"- Run ID: {run_id}",
                            f"- Panels expanded: {latest.get('panels_expanded', '-')}",
                            f"- Sheets: {latest.get('sheet_count', '-')}",
                            f"- Utilization avg: {latest.get('avg_utilization_percent', '-')}",
                        ]
                    )
                )
            else:
                summary_box.set_content(
                    "\n".join(
                        [
                            "**Saved Run Not Found**",
                            f"- Run ID: {run_id}",
                            "- Files may have been cleaned up from server storage.",
                        ]
                    )
                )

        async def _save_current_project(latest_run: Optional[Dict[str, Any]] = None) -> None:
            try:
                rows = await _get_normalized_rows()
            except Exception:
                rows = state.rows

            state.rows = [
                {
                    "width": int(round(float(r["width"]))),
                    "length": int(round(float(r["length"]))),
                    "qty": int(r["qty"]),
                    "label": str(r.get("label", "")),
                }
                for r in rows
            ]
            state.sheet_width = int(sheet_width_input.value)
            state.sheet_height = int(sheet_height_input.value)
            state.kerf = float(kerf_input.value)
            state.algorithm = str(algo_select.value)
            state.svg_title_font_size = int(svg_title_font_input.value)
            state.svg_label_font_size = int(svg_label_font_input.value)
            state.svg_dimension_font_size = int(svg_dimension_font_input.value)
            state.notes = str(notes_input.value or "").strip()
            state.current_project_name = str(project_name_input.value or "Untitled Project").strip() or "Untitled Project"

            if latest_run is not None:
                state.latest_run_summary = dict(latest_run)

            store = await _read_project_store()
            projects = list(store.get("projects", []))
            now_ts = int(time.time())
            project_id = state.current_project_id or uuid4().hex[:12]
            project = {
                "id": project_id,
                "name": state.current_project_name,
                "updated_at": now_ts,
                "inputs": {
                    "rows": state.rows,
                    "sheet_width": state.sheet_width,
                    "sheet_height": state.sheet_height,
                    "kerf": state.kerf,
                    "algorithm": state.algorithm,
                    "svg_title_font_size": state.svg_title_font_size,
                    "svg_label_font_size": state.svg_label_font_size,
                    "svg_dimension_font_size": state.svg_dimension_font_size,
                    "notes": state.notes,
                },
                "latest_run": state.latest_run_summary,
            }

            projects = [p for p in projects if str(p.get("id", "")) != project_id]
            projects.append(project)
            projects.sort(key=lambda p: int(p.get("updated_at", 0)), reverse=True)
            projects = projects[:LOCAL_PROJECTS_MAX]

            store["projects"] = projects
            store["currentProjectId"] = project_id
            await _write_project_store(store)

            state.current_project_id = project_id
            project_select.options = _project_options(store)
            project_select.set_value(project_id)

        async def _new_project() -> None:
            state.current_project_id = ""
            state.current_project_name = "Untitled Project"
            state.rows = _load_default_rows()
            state.sheet_width = 2400
            state.sheet_height = 1200
            state.kerf = 4.0
            state.algorithm = "guillotine"
            state.svg_title_font_size = 40
            state.svg_label_font_size = 30
            state.svg_dimension_font_size = 16
            state.notes = ""
            state.latest_run_summary = {}

            project_name_input.set_value(state.current_project_name)
            sheet_width_input.set_value(state.sheet_width)
            sheet_height_input.set_value(state.sheet_height)
            kerf_input.set_value(state.kerf)
            algo_select.set_value(state.algorithm)
            svg_title_font_input.set_value(state.svg_title_font_size)
            svg_label_font_input.set_value(state.svg_label_font_size)
            svg_dimension_font_input.set_value(state.svg_dimension_font_size)
            notes_input.set_value("")
            grid.options["rowData"] = state.rows
            grid.update()
            summary_box.set_content("No runs yet.")
            await _save_current_project()
            ui.notify("Created new local project", type="positive")

        async def _delete_project() -> None:
            if not state.current_project_id:
                return
            store = await _read_project_store()
            projects = [
                p for p in store.get("projects", [])
                if str(p.get("id", "")) != state.current_project_id
            ]
            store["projects"] = projects

            if projects:
                projects.sort(key=lambda p: int(p.get("updated_at", 0)), reverse=True)
                selected = projects[0]
                store["currentProjectId"] = selected["id"]
                await _write_project_store(store)
                _apply_project_to_controls(selected)
                project_select.options = _project_options(store)
                project_select.set_value(selected["id"])
            else:
                store["currentProjectId"] = ""
                await _write_project_store(store)
                await _new_project()
            ui.notify("Deleted local project", type="info")

        async def _switch_project() -> None:
            selected_id = str(project_select.value or "").strip()
            if not selected_id:
                return
            store = await _read_project_store()
            project = next((p for p in store.get("projects", []) if str(p.get("id", "")) == selected_id), None)
            if not project:
                return
            _apply_project_to_controls(project)
            store["currentProjectId"] = selected_id
            await _write_project_store(store)
            await _load_saved_run_for_current_project()
            ui.notify(f"Loaded project: {state.current_project_name}", type="positive")

        async def _initialize_projects() -> None:
            store = await _read_project_store()
            projects = list(store.get("projects", []))

            if not projects:
                await _new_project()
                return

            project_select.options = _project_options(store)
            selected_id = str(store.get("currentProjectId", "")).strip()
            project = next((p for p in projects if str(p.get("id", "")) == selected_id), None)
            if not project:
                projects.sort(key=lambda p: int(p.get("updated_at", 0)), reverse=True)
                project = projects[0]
            _apply_project_to_controls(project)
            project_select.set_value(project["id"])
            await _load_saved_run_for_current_project()

        async def _autosave_from_controls() -> None:
            await _save_current_project()

        new_project_button.on_click(_new_project)
        delete_project_button.on_click(_delete_project)
        project_select.on_value_change(_switch_project)
        project_name_input.on_value_change(_autosave_from_controls)
        sheet_width_input.on_value_change(_autosave_from_controls)
        sheet_height_input.on_value_change(_autosave_from_controls)
        kerf_input.on_value_change(_autosave_from_controls)
        algo_select.on_value_change(_autosave_from_controls)
        svg_title_font_input.on_value_change(_autosave_from_controls)
        svg_label_font_input.on_value_change(_autosave_from_controls)
        svg_dimension_font_input.on_value_change(_autosave_from_controls)
        notes_input.on_value_change(_autosave_from_controls)

        ui.timer(0.1, _initialize_projects, once=True)

        async def run_pipeline() -> None:
            client_id = ui.context.client.id

            if not can_submit(client_id):
                ui.notify('Please wait before submitting again.', type='warning')
                return
            # Add depl
            try:
                # Pull latest editable grid rows from browser state.
                live_rows = await grid.get_client_data(timeout=2)
                if not live_rows:
                    live_rows = state.rows
                normalized_rows = [_parse_row(r, i) for i, r in enumerate(live_rows, start=1)]

                state.sheet_width = int(sheet_width_input.value)
                state.sheet_height = int(sheet_height_input.value)
                state.kerf = float(kerf_input.value)
                state.algorithm = str(algo_select.value)
                state.svg_title_font_size = int(svg_title_font_input.value)
                state.svg_label_font_size = int(svg_label_font_input.value)
                state.svg_dimension_font_size = int(svg_dimension_font_input.value)
                state.notes = str(notes_input.value or "").strip()

                panels = []
                for row in normalized_rows:
                    for _ in range(row["qty"]):
                        panels.append(Panel(row["width"], row["length"], label=row["label"]))

                sheets = pack_panels(
                    panels,
                    sheet_width=state.sheet_width,
                    sheet_height=state.sheet_height,
                    algorithm=state.algorithm,
                    kerf=state.kerf,
                )

                run_id, run_dir = _new_run_dir()
                base = run_dir / "plan"
                state.current_run_id = run_id

                txt_path = base.with_suffix(".txt")
                csv_path = base.with_suffix(".csv")
                json_path = base.with_suffix(".json")
                svg_path = base.with_suffix(".svg")
                pdf_path = base.with_suffix(".pdf")
                ascii_path = Path(f"{base}.ascii.txt")

                text_output = output_formatters.to_text(sheets)
                csv_output = output_formatters.to_csv(sheets)
                json_output = output_formatters.to_json(sheets)
                ascii_output = output_formatters.to_ascii(sheets)
                svg_preview = output_formatters.to_svg(
                    sheets,
                    title_font_size=state.svg_title_font_size,
                    label_font_size=state.svg_label_font_size,
                    dimension_font_size=state.svg_dimension_font_size,
                )

                txt_path.write_text(text_output, encoding="utf-8")
                csv_path.write_text(csv_output, encoding="utf-8")
                json_path.write_text(json_output, encoding="utf-8")
                ascii_path.write_text(ascii_output, encoding="utf-8")
                output_formatters.to_svg(
                    sheets,
                    filename=str(svg_path),
                    title_font_size=state.svg_title_font_size,
                    label_font_size=state.svg_label_font_size,
                    dimension_font_size=state.svg_dimension_font_size,
                )
                output_formatters.to_pdf(
                    sheets,
                    filename=str(pdf_path),
                    input_panels=panels,
                    panels_file="table_input",
                    sheet_width=state.sheet_width,
                    sheet_height=state.sheet_height,
                    algorithm=state.algorithm,
                    kerf=state.kerf,
                    notes=state.notes,
                    svg_dimension_font_size=state.svg_dimension_font_size,
                )

                generated = [
                    str(txt_path),
                    str(csv_path),
                    str(json_path),
                    str(ascii_path),
                    str(pdf_path),
                ]
                svg_sheet_files = sorted(base.parent.glob(f"{base.stem}_sheet*.svg"))
                if svg_sheet_files:
                    generated.extend(str(p) for p in svg_sheet_files)
                else:
                    generated.append(str(svg_path))

                state.rows = [
                    {
                        "width": int(round(r["width"])),
                        "length": int(round(r["length"])),
                        "qty": r["qty"],
                        "label": r["label"],
                    }
                    for r in normalized_rows
                ]
                state.last_file_paths = generated
                state.text_output = text_output
                state.csv_output = csv_output
                state.json_output = json_output
                state.ascii_output = ascii_output
                state.svg_preview = svg_preview
                state.latest_run_summary = {
                    "run_id": state.current_run_id,
                    "panels_expanded": len(panels),
                    "sheet_count": len(sheets),
                    "avg_utilization_percent": round(
                        (sum(sheet.get_utilization() for sheet in sheets) / len(sheets)) if sheets else 0.0,
                        2,
                    ),
                    "generated_files": [Path(p).name for p in generated],
                    "saved_at": int(time.time()),
                }

                cut_rows = []
                for sheet_index, sheet in enumerate(sheets, start=1):
                    for panel_index, panel in enumerate(sheet.panels, start=1):
                        cut_rows.append(
                            {
                                "sheet": sheet_index,
                                "panel_number": panel_index,
                                "label": panel.label or "-",
                                "size": f"{int(round(panel.width))} x {int(round(panel.height))}",
                                "position": f"({int(round(panel.x))}, {int(round(panel.y))})",
                            }
                        )

                summary_box.set_content(
                    "\n".join(
                        [
                            "**Run Complete**",
                            f"- Run ID: {state.current_run_id}",
                            f"- Rows: {len(state.rows)}",
                            f"- Panels expanded: {len(panels)}",
                            f"- Sheets: {len(sheets)}",
                            f"- Output base: {base}",
                        ]
                    )
                )

                await _save_current_project(latest_run=state.latest_run_summary)

                cut_grid.options["rowData"] = cut_rows
                cut_grid.update()

                layouts_container.clear()
                svg_sheet_paths = sorted(base.parent.glob(f"{base.stem}_sheet*.svg"))
                if svg_sheet_paths:
                    for i, svg_file in enumerate(svg_sheet_paths, start=1):
                        with layouts_container:
                            ui.label(f"Sheet {i}").classes("font-semibold text-slate-700")
                            ui.html(_svg_for_web(svg_file.read_text(encoding="utf-8"))).classes("w-full")
                else:
                    with layouts_container:
                        ui.html(_svg_for_web(state.svg_preview)).classes("w-full")

                downloads_container.clear()
                with downloads_container:
                    ui.label("Downloads").classes("text-lg font-semibold text-slate-700")
                    ui.label("View opens in new tab. Right-click there to save directly.").classes("text-xs text-slate-500")

                    with ui.column().classes("w-full gap-0"):
                        # PDF first, then the rest in original order
                        pdf_paths = [fp for fp in state.last_file_paths if fp.endswith(".pdf")]
                        other_paths = [fp for fp in state.last_file_paths if not fp.endswith(".pdf")]
                        for file_path in pdf_paths + other_paths:
                            p = Path(file_path)
                            is_pdf = p.suffix.lower() == ".pdf"
                            file_url = f"{RUNS_ROUTE}/{state.current_run_id}/{p.name}"
                            row_classes = "w-full items-center justify-between gap-3 py-1.5 border-b border-slate-200"
                            if is_pdf:
                                row_classes += " bg-slate-50"
                            with ui.row().classes(row_classes):
                                link_classes = "text-sm break-all " + ("font-bold text-slate-900" if is_pdf else "text-slate-600")
                                ui.link(p.name, file_url, new_tab=True).classes(link_classes)
                message = f"Done. Wrote {len(state.last_file_paths)} files."
                ui.notify(message, type="positive")
            except Exception as exc:
                message = f"Run error: {exc}"
                ui.notify(message, type="negative", multi_line=True)

        run_button.on_click(run_pipeline)


if APP_BASE_PATH and APP_ROUTE != "/":
    ui.page(APP_ROUTE)(main_page)


def run() -> None:
    """Run the NiceGUI app server."""
    ui.run(
        title="Panelo Web",
        reload=False,
        show=False,
        host=APP_HOST,
        port=APP_PORT,
    )


if __name__ in {"__main__", "__mp_main__"}:
    run()
