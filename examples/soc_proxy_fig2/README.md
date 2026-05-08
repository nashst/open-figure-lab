# SOC Proxy Fig. 2 Demo

This is the first end-to-end Open Figure Lab demo package.

It exercises the MVP loop:

```text
CSV data -> figure.yaml -> matplotlib renderer -> SVG/PDF/PNG -> QA report
```

Run from repository root:

```powershell
$env:PYTHONPATH = "src"
python -m open_figure_lab.cli validate examples/soc_proxy_fig2
python -m open_figure_lab.cli render examples/soc_proxy_fig2
python -m open_figure_lab.cli qa examples/soc_proxy_fig2
```

Outputs are written to `examples/soc_proxy_fig2/outputs/`.

