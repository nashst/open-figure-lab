import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from open_figure_lab.cli import main
from open_figure_lab.figure_spec import load_figure_spec, parse_yaml_subset, validate_figure_spec
from open_figure_lab.journal_presets import get_preset, list_presets


class CliTests(unittest.TestCase):
    def test_init_creates_required_spec_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "fig_demo"
            self.assertEqual(main(["init", str(project)]), 0)

            self.assertTrue((project / "spec" / "figure.yaml").exists())
            self.assertTrue((project / "spec" / "data_manifest.yaml").exists())
            self.assertTrue((project / "spec" / "theme.yaml").exists())

    def test_qa_passes_for_initialized_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "fig_demo"
            self.assertEqual(main(["init", str(project)]), 0)
            self.assertEqual(main(["qa", str(project)]), 0)

    def test_validate_rejects_unknown_preset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "fig_demo"
            self.assertEqual(main(["init", str(project)]), 0)
            spec_path = project / "spec" / "figure.yaml"
            spec_path.write_text(spec_path.read_text(encoding="utf-8").replace("journal_preset: nature", "journal_preset: unknown"), encoding="utf-8")

            self.assertEqual(main(["validate", str(project)]), 1)

    def test_parser_supports_panel_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "figure.yaml"
            spec_path.write_text(
                """figure:
  id: fig2_proxy_validity
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
  panels:
    - id: A
      type: correlation_lollipop
      data: proxy_validity_correlations.csv
      x: spearman_rho
      y: proxy
    - id: B
      type: auc_dotplot
      data: proxy_validity_auc.csv
""",
                encoding="utf-8",
            )

            result = validate_figure_spec(load_figure_spec(spec_path))
            self.assertTrue(result.ok, [message.message for message in result.messages])

    def test_nature_preset_is_available(self) -> None:
        self.assertIn("nature", list_presets())
        preset = get_preset("nature")
        self.assertEqual(preset["figure_width_mm"]["double_column"], 183)
        self.assertEqual(preset["matplotlib"]["pdf.fonttype"], 42)

    def test_parser_preserves_hash_inside_quotes(self) -> None:
        parsed = parse_yaml_subset('theme:\n  color: "#2F5D8C"\n')
        self.assertEqual(parsed["theme"]["color"], "#2F5D8C")

    def test_example_soc_fig2_validates_and_renders_png(self) -> None:
        example = Path(__file__).resolve().parents[1] / "examples" / "soc_proxy_fig2"
        self.assertEqual(main(["validate", str(example)]), 0)
        self.assertEqual(main(["qa", str(example)]), 0)
        self.assertEqual(main(["render", str(example), "--format", "png"]), 0)
        self.assertTrue((example / "outputs" / "soc_proxy_fig2.png").exists())
        self.assertTrue((example / "outputs" / "qa_report.md").exists())

    def test_qa_fails_when_panel_field_is_missing_from_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "broken"
            self.assertEqual(main(["init", str(project)]), 0)
            data_dir = project / "data"
            data_dir.mkdir(exist_ok=True)
            (data_dir / "bad.csv").write_text("proxy,value\nNDVI,0.1\n", encoding="utf-8")
            figure_yaml = project / "spec" / "figure.yaml"
            figure_yaml.write_text(
                """figure:
  id: broken
  journal_preset: nature
  canvas:
    width_mm: 183
    height_mm: 125
  typography:
    font_family: Arial
    base_size_pt: 6.5
  layout:
    type: grid
    rows: 1
    cols: 1
  panels:
    - id: A
      type: correlation_lollipop
      data: bad.csv
      x: spearman_rho
      y: proxy
""",
                encoding="utf-8",
            )

            self.assertEqual(main(["qa", str(project)]), 1)

    def test_render_rejects_invalid_spec_before_writing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "invalid"
            self.assertEqual(main(["init", str(project)]), 0)
            spec_path = project / "spec" / "figure.yaml"
            spec_path.write_text(spec_path.read_text(encoding="utf-8").replace("rows: 2", "rows: 0"), encoding="utf-8")

            with patch("open_figure_lab.cli.render_project") as render_project:
                self.assertEqual(main(["render", str(project), "--format", "png"]), 1)
                render_project.assert_not_called()


if __name__ == "__main__":
    unittest.main()
