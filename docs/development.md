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

