"""Figure spec loading and validation.

The project deliberately avoids a YAML dependency during foundation work. This
module implements the small YAML subset used by Open Figure Lab templates:
nested mappings, lists of mappings, inline empty lists, quoted strings, numbers,
booleans, and nulls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from open_figure_lab.journal_presets import PRESETS


@dataclass(frozen=True)
class ValidationMessage:
    level: str
    path: str
    message: str


@dataclass
class ValidationResult:
    messages: list[ValidationMessage] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(message.level == "ERROR" for message in self.messages)

    def error(self, path: str, message: str) -> None:
        self.messages.append(ValidationMessage("ERROR", path, message))

    def warning(self, path: str, message: str) -> None:
        self.messages.append(ValidationMessage("WARNING", path, message))


def load_figure_spec(path: str | Path) -> dict[str, Any]:
    """Load a figure spec file."""

    return parse_yaml_subset(Path(path).read_text(encoding="utf-8"))


def parse_yaml_subset(text: str) -> dict[str, Any]:
    """Parse the dependency-free YAML subset used by project specs."""

    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]

    lines = text.splitlines()
    for index, raw_line in enumerate(lines):
        line = strip_yaml_comment(raw_line).rstrip()
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent % 2 != 0:
            raise ValueError(f"Indentation must use multiples of two spaces: {raw_line!r}")

        item = line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()

        parent = stack[-1][1]
        if item.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError(f"List item has non-list parent: {raw_line!r}")
            value = item[2:].strip()
            if ":" in value:
                key, raw_value = split_key_value(value)
                entry: dict[str, Any] = {key: parse_scalar(raw_value)}
                parent.append(entry)
                if raw_value == "":
                    child: dict[str, Any] = {}
                    entry[key] = child
                    stack.append((indent + 2, child))
                else:
                    stack.append((indent, entry))
            else:
                parent.append(parse_scalar(value))
            continue

        key, raw_value = split_key_value(item)
        if not isinstance(parent, dict):
            raise ValueError(f"Mapping item has non-mapping parent: {raw_line!r}")

        if raw_value == "":
            child = [] if next_significant_line_is_list(lines, index) else {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = parse_scalar(raw_value)

    return root


def split_key_value(item: str) -> tuple[str, str]:
    key, separator, value = item.partition(":")
    if not separator:
        raise ValueError(f"Expected 'key: value' entry: {item!r}")
    key = key.strip()
    if not key:
        raise ValueError(f"Empty key in entry: {item!r}")
    return key, value.strip()


def strip_yaml_comment(line: str) -> str:
    """Strip comments while preserving # inside single or double quotes."""

    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
            continue
        if char == "#" and quote is None:
            return line[:index]
    return line


def next_significant_line_is_list(lines: list[str], current_index: int) -> bool:
    """Return whether the next nested content line starts a list."""

    current_line = lines[current_index]
    current_indent = len(current_line) - len(current_line.lstrip(" "))
    for line in lines[current_index + 1 :]:
        stripped = strip_yaml_comment(line).rstrip()
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        return indent > current_indent and stripped.strip().startswith("- ")
    return False


def parse_scalar(value: str) -> Any:
    if value == "":
        return ""
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",")]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def validate_figure_spec(spec: dict[str, Any]) -> ValidationResult:
    result = ValidationResult()

    figure = spec.get("figure")
    if not isinstance(figure, dict):
        result.error("figure", "Missing required mapping.")
        return result

    require_string(result, figure, "id", "figure.id")

    preset = figure.get("journal_preset")
    if not isinstance(preset, str) or not preset:
        result.error("figure.journal_preset", "Must be a non-empty string.")
    elif preset not in PRESETS:
        available = ", ".join(sorted(PRESETS))
        result.error("figure.journal_preset", f"Unknown preset '{preset}'. Available: {available}.")

    canvas = require_mapping(result, figure, "canvas", "figure.canvas")
    if canvas:
        require_positive_number(result, canvas, "width_mm", "figure.canvas.width_mm")
        require_positive_number(result, canvas, "height_mm", "figure.canvas.height_mm")

    typography = require_mapping(result, figure, "typography", "figure.typography")
    if typography:
        require_string(result, typography, "font_family", "figure.typography.font_family")
        require_positive_number(result, typography, "base_size_pt", "figure.typography.base_size_pt")

    layout = require_mapping(result, figure, "layout", "figure.layout")
    if layout:
        layout_type = layout.get("type")
        if layout_type != "grid":
            result.error("figure.layout.type", "Only 'grid' layout is supported in the current schema.")
        require_positive_int(result, layout, "rows", "figure.layout.rows")
        require_positive_int(result, layout, "cols", "figure.layout.cols")

    panels = figure.get("panels")
    if not isinstance(panels, list):
        result.error("figure.panels", "Must be a list.")
    else:
        validate_panels(result, panels)

    return result


def validate_panels(result: ValidationResult, panels: list[Any]) -> None:
    seen_ids: set[str] = set()
    for index, panel in enumerate(panels):
        path = f"figure.panels[{index}]"
        if not isinstance(panel, dict):
            result.error(path, "Panel must be a mapping.")
            continue
        panel_id = panel.get("id")
        if not isinstance(panel_id, str) or not panel_id:
            result.error(f"{path}.id", "Panel id must be a non-empty string.")
        elif panel_id in seen_ids:
            result.error(f"{path}.id", f"Duplicate panel id '{panel_id}'.")
        else:
            seen_ids.add(panel_id)

        require_string(result, panel, "type", f"{path}.type")
        data = panel.get("data")
        if data is not None and not isinstance(data, str):
            result.error(f"{path}.data", "Panel data source must be a string when provided.")


def require_mapping(result: ValidationResult, parent: dict[str, Any], key: str, path: str) -> dict[str, Any] | None:
    value = parent.get(key)
    if not isinstance(value, dict):
        result.error(path, "Missing required mapping.")
        return None
    return value


def require_string(result: ValidationResult, parent: dict[str, Any], key: str, path: str) -> str | None:
    value = parent.get(key)
    if not isinstance(value, str) or not value:
        result.error(path, "Must be a non-empty string.")
        return None
    return value


def require_positive_number(result: ValidationResult, parent: dict[str, Any], key: str, path: str) -> float | int | None:
    value = parent.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        result.error(path, "Must be a positive number.")
        return None
    return value


def require_positive_int(result: ValidationResult, parent: dict[str, Any], key: str, path: str) -> int | None:
    value = parent.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        result.error(path, "Must be a positive integer.")
        return None
    return value


def format_validation_messages(result: ValidationResult) -> list[str]:
    if not result.messages:
        return ["PASS: figure spec schema is valid"]
    return [f"{message.level}: {message.path}: {message.message}" for message in result.messages]
