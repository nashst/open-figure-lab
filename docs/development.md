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

## Web UI

The Web UI provides an OpenDesign-like workbench interface.

### Start the server

```powershell
cd "D:\Acodeproject\Open Figure Lab"
python app/start.py
```

Open `http://localhost:8080` in your browser.

### Features

- **Command Panel** (left): Run validate, render, QA commands
- **Figure Preview** (center): View rendered figure outputs
- **Inspector** (right): View figure.yaml, data manifest, QA report
- **Run Log** (bottom): Command execution history

### API Endpoints

- `GET /api/project` - Project information
- `GET /api/spec` - Figure spec content
- `GET /api/data-manifest` - Data manifest content
- `GET /api/qa-report` - QA report content
- `POST /api/validate` - Run validation
- `POST /api/render` - Run rendering
- `POST /api/qa` - Run QA check
- `GET /outputs/<filename>` - Serve output files
