"""Dependency-light CLI bootstrap for Open Figure Lab."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path

from open_figure_lab.figure_spec import (
    format_validation_messages,
    load_figure_spec,
    validate_figure_spec,
)
from open_figure_lab.journal_presets import get_preset, list_presets
from open_figure_lab.data_qa import format_data_qa_messages, run_data_qa, write_qa_report
from open_figure_lab.renderers import SUPPORTED_FORMATS, render_project


PROJECT_DIRS = ("data", "spec", "src", "outputs", "history")


FIGURE_TEMPLATE = """figure:
  id: {project_name}
  journal_preset: nature
  canvas:
    width_mm: 183
    height_mm: 125
  typography:
    font_family: Arial
    base_size_pt: 6.5
  layout:
    type: grid
    rows: 2
    cols: 2
  panels: []
"""


DATA_MANIFEST_TEMPLATE = """data_manifest:
  project: {project_name}
  sources: []
  rules:
    - All plotted values must come from listed data sources or recorded computations.
    - Visual revisions must not modify data files.
"""


THEME_TEMPLATE = """theme:
  name: nature_minimal
  background: white
  font_family: Arial
  colors:
    primary: "#2F5D8C"
    secondary: "#4C8A62"
    neutral: "#4D4D4D"
  line_width_pt:
    axis: 0.5
    data: 0.7
"""


def cmd_doctor(_: argparse.Namespace) -> int:
    checks = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "git": shutil.which("git") or "missing",
        "gh": shutil.which("gh") or "missing",
        "node": shutil.which("node") or "missing",
        "npm": shutil.which("npm") or "missing",
    }

    print(json.dumps(checks, indent=2))
    missing = [name for name in ("git", "gh") if checks[name] == "missing"]
    if missing:
        print(f"Missing required tools: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.name)
    root.mkdir(parents=True, exist_ok=args.force)

    for dirname in PROJECT_DIRS:
        (root / dirname).mkdir(exist_ok=True)

    project_name = root.name
    write_once(root / "spec" / "figure.yaml", FIGURE_TEMPLATE.format(project_name=project_name), args.force)
    write_once(root / "spec" / "data_manifest.yaml", DATA_MANIFEST_TEMPLATE.format(project_name=project_name), args.force)
    write_once(root / "spec" / "theme.yaml", THEME_TEMPLATE, args.force)
    write_once(root / "src" / "render.py", render_template(project_name), args.force)
    write_once(root / "outputs" / "qa_report.md", f"# QA Report\n\nProject: `{project_name}`\n\nStatus: not run.\n", args.force)
    write_once(root / "history" / "README.md", "# Revision History\n\nRecord figure spec and rendering changes here.\n", args.force)

    print(f"Created figure project: {root}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    project = Path(args.project)
    figure_spec = project / "spec" / "figure.yaml"
    if not figure_spec.exists():
        print(f"Missing figure spec: {figure_spec}", file=sys.stderr)
        return 1

    result = validate_figure_spec(load_figure_spec(figure_spec))
    for line in format_validation_messages(result):
        print(line)
    if not result.ok:
        return 1

    formats = tuple(args.format or SUPPORTED_FORMATS)
    outputs = render_project(project, formats)
    for output in outputs:
        print(f"Wrote {output}")
    return 0


def cmd_qa(args: argparse.Namespace) -> int:
    project = Path(args.project)
    required = [
        project / "spec" / "figure.yaml",
        project / "spec" / "data_manifest.yaml",
        project / "spec" / "theme.yaml",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print("QA FAIL: missing required files", file=sys.stderr)
        for path in missing:
            print(f"- {path}", file=sys.stderr)
        return 1

    result = validate_figure_spec(load_figure_spec(project / "spec" / "figure.yaml"))
    for line in format_validation_messages(result):
        print(line)
    if not result.ok:
        return 1

    data_result = run_data_qa(project)
    for line in format_data_qa_messages(data_result):
        print(line)
    report_path = write_qa_report(project, result, data_result)
    print(f"QA report: {report_path}")
    if not data_result.ok:
        return 1

    print("QA PASS: required spec files exist")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.path)
    spec_path = path / "spec" / "figure.yaml" if path.is_dir() else path
    result = validate_figure_spec(load_figure_spec(spec_path))
    for line in format_validation_messages(result):
        print(line)
    return 0 if result.ok else 1


def cmd_presets(args: argparse.Namespace) -> int:
    if args.name:
        print(json.dumps(get_preset(args.name), indent=2))
    else:
        for name in list_presets():
            print(name)
    return 0


def write_once(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        return
    path.write_text(content, encoding="utf-8")


def render_template(project_name: str) -> str:
    return f'''"""Renderer entrypoint for {project_name}.

This placeholder intentionally avoids plotting dependencies during foundation setup.
"""


def main() -> None:
    print("Render pipeline is not implemented yet.")


if __name__ == "__main__":
    main()
'''


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ofl", description="Open Figure Lab CLI")
    subparsers = parser.add_subparsers(required=True)

    doctor = subparsers.add_parser("doctor", help="Check local tool availability")
    doctor.set_defaults(func=cmd_doctor)

    init = subparsers.add_parser("init", help="Create a figure project skeleton")
    init.add_argument("name", help="Project directory to create")
    init.add_argument("--force", action="store_true", help="Overwrite existing template files")
    init.set_defaults(func=cmd_init)

    render = subparsers.add_parser("render", help="Render a figure project")
    render.add_argument("project", help="Figure project directory")
    render.add_argument("--format", action="append", choices=SUPPORTED_FORMATS, help="Output format. Repeat to select multiple formats. Defaults to svg, pdf, and png.")
    render.set_defaults(func=cmd_render)

    qa = subparsers.add_parser("qa", help="Run basic QA on a figure project")
    qa.add_argument("project", help="Figure project directory")
    qa.set_defaults(func=cmd_qa)

    validate = subparsers.add_parser("validate", help="Validate a figure.yaml file or figure project")
    validate.add_argument("path", help="Figure project directory or figure.yaml path")
    validate.set_defaults(func=cmd_validate)

    presets = subparsers.add_parser("presets", help="List or inspect journal presets")
    presets.add_argument("name", nargs="?", help="Preset identifier to inspect")
    presets.set_defaults(func=cmd_presets)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
