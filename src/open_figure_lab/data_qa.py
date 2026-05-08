"""Data integrity checks for figure projects."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from open_figure_lab.figure_spec import ValidationMessage, ValidationResult, load_figure_spec


PANEL_FIELD_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "correlation_lollipop": ("x", "y"),
    "auc_dotplot": ("x", "y"),
    "precision_lift": ("x", "y"),
    "decile_curve": ("x", "y"),
}


@dataclass
class DataQaResult:
    messages: list[ValidationMessage] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(message.level == "ERROR" for message in self.messages)

    def error(self, path: str, message: str) -> None:
        self.messages.append(ValidationMessage("ERROR", path, message))

    def warning(self, path: str, message: str) -> None:
        self.messages.append(ValidationMessage("WARNING", path, message))

    def pass_(self, path: str, message: str) -> None:
        self.messages.append(ValidationMessage("PASS", path, message))


def run_data_qa(project: str | Path) -> DataQaResult:
    project_path = Path(project)
    spec = load_figure_spec(project_path / "spec" / "figure.yaml")
    return validate_panel_data(project_path, spec)


def validate_panel_data(project_path: Path, spec: dict[str, Any]) -> DataQaResult:
    result = DataQaResult()
    figure = spec.get("figure", {})
    panels = figure.get("panels", [])
    if not isinstance(panels, list):
        result.error("figure.panels", "Cannot run data QA without a panel list.")
        return result

    for index, panel in enumerate(panels):
        panel_path = f"figure.panels[{index}]"
        if not isinstance(panel, dict):
            result.error(panel_path, "Panel must be a mapping.")
            continue

        panel_id = str(panel.get("id", index))
        panel_type = panel.get("type")
        data_name = panel.get("data")
        if not isinstance(data_name, str) or not data_name:
            result.warning(panel_path, f"Panel {panel_id} has no data source.")
            continue

        data_path = project_path / "data" / data_name
        if not data_path.exists():
            result.error(f"{panel_path}.data", f"Missing data file: data/{data_name}")
            continue

        try:
            fieldnames = read_csv_fieldnames(data_path)
        except csv.Error as exc:
            result.error(f"{panel_path}.data", f"CSV parse error: {exc}")
            continue

        result.pass_(f"{panel_path}.data", f"Found data/{data_name}")
        required_fields = PANEL_FIELD_REQUIREMENTS.get(str(panel_type), ())
        for key in required_fields:
            value = panel.get(key)
            if not isinstance(value, str) or not value:
                result.error(f"{panel_path}.{key}", f"Panel {panel_id} must declare field '{key}'.")
                continue
            if value not in fieldnames:
                result.error(f"{panel_path}.{key}", f"Field '{value}' not found in data/{data_name}.")
            else:
                result.pass_(f"{panel_path}.{key}", f"Field '{value}' exists in data/{data_name}")

    return result


def read_csv_fieldnames(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise csv.Error("CSV file has no header row")
        return reader.fieldnames


def format_data_qa_messages(result: DataQaResult) -> list[str]:
    if not result.messages:
        return ["PASS: no data-bound panels to check"]
    return [f"{message.level}: {message.path}: {message.message}" for message in result.messages]


def write_qa_report(project: str | Path, schema_result: ValidationResult, data_result: DataQaResult) -> Path:
    project_path = Path(project)
    report_path = project_path / "outputs" / "qa_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# QA Report",
        "",
        f"Project: `{project_path.name}`",
        "",
        "## Figure Spec",
        "",
    ]
    if schema_result.messages:
        lines.extend(f"- {message.level}: `{message.path}` - {message.message}" for message in schema_result.messages)
    else:
        lines.append("- PASS: figure spec schema is valid")

    lines.extend(["", "## Data Integrity", ""])
    if data_result.messages:
        lines.extend(f"- {message.level}: `{message.path}` - {message.message}" for message in data_result.messages)
    else:
        lines.append("- PASS: no data-bound panels to check")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path

