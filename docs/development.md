# Development

## Local Environment

Current baseline:

- Python 3.11 or newer
- Git
- GitHub CLI
- Node/npm only when the web UI lane starts

No third-party runtime dependencies are installed in the foundation phase.

## Bootstrap

From repository root:

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -e .
ofl doctor
```

Without editable install:

```powershell
$env:PYTHONPATH = "src"
python -m open_figure_lab.cli doctor
```

## Test Policy

Until a test runner is added, use standard library `unittest` for dependency-free checks.

Future test layers:

- CLI unit tests
- figure spec validation fixtures
- renderer golden-file smoke tests
- QA report fixtures
- web UI browser verification

## First Demo Loop

The first real product loop lives in `examples/soc_proxy_fig2`.

```powershell
$env:PYTHONPATH = "src"
python -m open_figure_lab.cli validate examples/soc_proxy_fig2
python -m open_figure_lab.cli render examples/soc_proxy_fig2
python -m open_figure_lab.cli qa examples/soc_proxy_fig2
```

Expected generated outputs:

- `examples/soc_proxy_fig2/outputs/soc_proxy_fig2.svg`
- `examples/soc_proxy_fig2/outputs/soc_proxy_fig2.pdf`
- `examples/soc_proxy_fig2/outputs/soc_proxy_fig2.png`
- `examples/soc_proxy_fig2/outputs/qa_report.md`
