"""Matplotlib renderer for the first Open Figure Lab demo loop."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from open_figure_lab.figure_spec import load_figure_spec
from open_figure_lab.journal_presets import get_preset


SUPPORTED_FORMATS = ("svg", "pdf", "png")


def render_project(project: str | Path, formats: tuple[str, ...] = SUPPORTED_FORMATS) -> list[Path]:
    project_path = Path(project)
    spec = load_figure_spec(project_path / "spec" / "figure.yaml")
    figure_spec = spec["figure"]
    preset = get_preset(figure_spec["journal_preset"])

    apply_matplotlib_defaults(preset, figure_spec)
    fig, axes = build_canvas(figure_spec)
    flat_axes = list(axes.flatten()) if hasattr(axes, "flatten") else [axes]

    panels = figure_spec.get("panels", [])
    for index, panel in enumerate(panels):
        if index >= len(flat_axes):
            break
        render_panel(flat_axes[index], project_path, panel)

    for index in range(len(panels), len(flat_axes)):
        flat_axes[index].axis("off")

    fig.tight_layout(pad=1.0)
    outputs = write_outputs(fig, project_path, formats)
    plt.close(fig)
    return outputs


def apply_matplotlib_defaults(preset: dict[str, Any], figure_spec: dict[str, Any]) -> None:
    font = figure_spec.get("typography", {})
    matplotlib_defaults = preset.get("matplotlib", {})
    plt.rcParams.update(
        {
            "font.family": font.get("font_family", preset["font"]["family"]),
            "font.size": font.get("base_size_pt", preset["font"]["normal_size_pt"]),
            "axes.linewidth": preset["line_width_pt"]["axis"],
            "lines.linewidth": preset["line_width_pt"]["data"],
            "pdf.fonttype": matplotlib_defaults.get("pdf.fonttype", 42),
            "ps.fonttype": matplotlib_defaults.get("ps.fonttype", 42),
            "svg.fonttype": matplotlib_defaults.get("svg.fonttype", "none"),
        }
    )


def build_canvas(figure_spec: dict[str, Any]):
    canvas = figure_spec["canvas"]
    layout = figure_spec["layout"]
    width_in = canvas["width_mm"] / 25.4
    height_in = canvas["height_mm"] / 25.4
    return plt.subplots(
        layout["rows"],
        layout["cols"],
        figsize=(width_in, height_in),
        squeeze=False,
    )


def render_panel(axis, project_path: Path, panel: dict[str, Any]) -> None:
    panel_type = panel["type"]
    rows = read_panel_rows(project_path, panel)

    if panel_type == "correlation_lollipop":
        render_lollipop(axis, rows, panel)
    elif panel_type == "auc_dotplot":
        render_dotplot(axis, rows, panel)
    elif panel_type == "precision_lift":
        render_line(axis, rows, panel, marker="o")
    elif panel_type == "decile_curve":
        render_line(axis, rows, panel, marker="s")
    else:
        raise ValueError(f"Unsupported panel type: {panel_type}")

    style_panel(axis, panel)


def read_panel_rows(project_path: Path, panel: dict[str, Any]) -> list[dict[str, str]]:
    data_path = project_path / "data" / panel["data"]
    with data_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def render_lollipop(axis, rows: list[dict[str, str]], panel: dict[str, Any]) -> None:
    x_field = panel["x"]
    y_field = panel["y"]
    labels = [row[y_field] for row in rows]
    values = [float(row[x_field]) for row in rows]
    positions = list(range(len(rows)))
    color = panel.get("color", "#2F5D8C")

    axis.hlines(positions, 0, values, color="#B8C3CE", linewidth=0.8)
    axis.plot(values, positions, "o", color=color, markersize=4)
    axis.axvline(float(panel.get("reference_line", 0)), color="#4D4D4D", linewidth=0.6)
    axis.set_yticks(positions, labels)
    axis.invert_yaxis()
    axis.set_xlabel(panel.get("x_label", x_field))


def render_dotplot(axis, rows: list[dict[str, str]], panel: dict[str, Any]) -> None:
    x_field = panel["x"]
    y_field = panel["y"]
    labels = [row[y_field] for row in rows]
    values = [float(row[x_field]) for row in rows]
    positions = list(range(len(rows)))
    color = panel.get("color", "#2F5D8C")

    baseline = panel.get("baseline")
    if baseline is not None:
        axis.axvline(float(baseline), color="#4D4D4D", linestyle="--", linewidth=0.6)
    axis.plot(values, positions, "o", color=color, markersize=4)
    axis.set_yticks(positions, labels)
    axis.invert_yaxis()
    axis.set_xlabel(panel.get("x_label", x_field))


def render_line(axis, rows: list[dict[str, str]], panel: dict[str, Any], marker: str) -> None:
    x_field = panel["x"]
    y_field = panel["y"]
    x_values = [float(row[x_field]) for row in rows]
    y_values = [float(row[y_field]) for row in rows]
    color = panel.get("color", "#4C8A62")

    axis.plot(x_values, y_values, marker=marker, color=color, markersize=3)
    axis.set_xlabel(panel.get("x_label", x_field))
    axis.set_ylabel(panel.get("y_label", y_field))


def style_panel(axis, panel: dict[str, Any]) -> None:
    panel_id = panel.get("id", "")
    title = panel.get("title", "")
    axis.set_title(title, loc="left", fontsize=8, pad=6)
    axis.text(
        -0.12,
        1.08,
        panel_id,
        transform=axis.transAxes,
        fontsize=9,
        fontweight="bold",
        va="top",
        ha="left",
    )
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.grid(axis="x", color="#E6E6E6", linewidth=0.4)
    axis.tick_params(axis="both", labelsize=6, width=0.5, length=2.5)


def write_outputs(fig, project_path: Path, formats: tuple[str, ...]) -> list[Path]:
    output_dir = project_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_id = project_path.name
    outputs: list[Path] = []
    for output_format in formats:
        if output_format not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported output format: {output_format}")
        output_path = output_dir / f"{figure_id}.{output_format}"
        save_kwargs: dict[str, Any] = {"bbox_inches": "tight"}
        if output_format == "png":
            save_kwargs["dpi"] = 600
        fig.savefig(output_path, **save_kwargs)
        outputs.append(output_path)
    return outputs

