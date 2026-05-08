import tempfile
import unittest
from pathlib import Path

from open_figure_lab.cli import main


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


if __name__ == "__main__":
    unittest.main()

