# Figure Spec

`figure.yaml` is the product-facing intermediate representation for Open Figure Lab.

The first schema is intentionally small and stable. It supports the CLI foundation, Nature preset validation, and future renderer work without requiring agents to invent a new contract.

## Required Shape

```yaml
figure:
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
```

## Current Validation Rules

- `figure.id` must be a non-empty string.
- `figure.journal_preset` must match a built-in preset.
- `figure.canvas.width_mm` and `figure.canvas.height_mm` must be positive numbers.
- `figure.typography.font_family` must be a non-empty string.
- `figure.typography.base_size_pt` must be a positive number.
- `figure.layout.type` must currently be `grid`.
- `figure.layout.rows` and `figure.layout.cols` must be positive integers.
- `figure.panels` must be a list.
- Each panel must have a unique non-empty `id`.
- Each panel must have a non-empty `type`.
- Panel `data`, when present, must be a string.

## Current Presets

- `nature`
- `nature_comm`

## Current Rendered Panel Types

- `correlation_lollipop`
- `auc_dotplot`
- `precision_lift`
- `decile_curve`

Each rendered panel must declare:

- `id`
- `type`
- `data`
- `x`
- `y`

Optional first-renderer fields:

- `title`
- `x_label`
- `y_label`
- `color`
- `baseline` for `auc_dotplot`
- `reference_line` for `correlation_lollipop`

Inspect presets with:

```powershell
$env:PYTHONPATH = "src"
python -m open_figure_lab.cli presets nature
```

Validate a project with:

```powershell
$env:PYTHONPATH = "src"
python -m open_figure_lab.cli validate path\to\figure_project
```

Render a project with:

```powershell
$env:PYTHONPATH = "src"
python -m open_figure_lab.cli render examples/soc_proxy_fig2
```

Run data QA with:

```powershell
$env:PYTHONPATH = "src"
python -m open_figure_lab.cli qa examples/soc_proxy_fig2
```

## Parser Boundary

The foundation parser supports the subset used by project specs: nested mappings, lists of mappings, inline empty lists, quoted strings, numbers, booleans, and nulls.

When the renderer lane starts, introduce PyYAML or another structured parser only through an explicit dependency decision.
