#!/usr/bin/env python3
"""Export a notebook to a 12-point PDF without rendering saved warning streams.

Usage:
    .conda/bin/python export_notebook_pdf.py
    .conda/bin/python export_notebook_pdf.py --notebook final.ipynb --output final.pdf

This script does not alter the input notebook. It renders from an in-memory copy,
converts the DAG SVG to PDF, writes nbconvert's embedded figures beside the LaTeX
source, and runs XeLaTeX twice for stable references.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import warnings

# Keep optional plotting imports used by nbconvert away from a read-only home cache.
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-kickstarter")
warnings.filterwarnings("ignore", category=FutureWarning, module=r"seaborn\\.categorical")

import nbformat
from nbconvert import LatexExporter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", type=Path, default=Path("final.ipynb"))
    parser.add_argument("--output", type=Path, default=Path("final.pdf"))
    return parser.parse_args()


def remove_warning_streams(notebook: nbformat.NotebookNode) -> None:
    """Omit only saved stderr warning messages from the rendered copy."""
    for cell in notebook.cells:
        if cell.cell_type != "code":
            continue
        cell.outputs = [
            output
            for output in cell.get("outputs", [])
            if not (
                output.get("output_type") == "stream"
                and output.get("name") == "stderr"
                and "warning" in "".join(output.get("text", [])).lower()
            )
        ]


def escape_underscores_in_latex_text(body: str) -> str:
    """Fix PyMC's LaTeX model display, whose parameter names contain underscores."""

    def replace(match: re.Match[str]) -> str:
        return r"\text{" + match.group(1).replace("_", r"\_") + "}"

    return re.sub(r"\\text\{([^{}]*)\}", replace, body)


def main() -> None:
    args = parse_args()
    notebook_path = args.notebook.resolve()
    output_path = args.output.resolve()
    dag_path = notebook_path.parent / "category_goal_outcome_dag.svg"

    if not notebook_path.is_file():
        raise FileNotFoundError(f"Notebook not found: {notebook_path}")
    if not dag_path.is_file():
        raise FileNotFoundError(f"DAG SVG not found: {dag_path}")
    for executable in ("inkscape", "xelatex"):
        if shutil.which(executable) is None:
            raise RuntimeError(f"Required executable not found: {executable}")

    notebook = nbformat.read(notebook_path, as_version=4)
    remove_warning_streams(notebook)

    with tempfile.TemporaryDirectory(prefix="kickstarter-pdf-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        dag_pdf = temp_dir / "category-dag.pdf"
        subprocess.run(
            ["inkscape", str(dag_path), f"--export-filename={dag_pdf}"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        exporter = LatexExporter()
        # Keep the rendered PDF aligned with the notebook: both show code, prose,
        # and the selected outputs retained in the notebook.
        exporter.exclude_input = False
        exporter.exclude_input_prompt = True
        exporter.exclude_output_prompt = True
        latex, resources = exporter.from_notebook_node(notebook)
        latex = latex.replace(r"\documentclass[11pt]{article}", r"\documentclass[12pt]{article}")
        latex = latex.replace(r"\documentclass{article}", r"\documentclass[12pt]{article}")
        latex = latex.replace(
            r"\includesvg[keepaspectratio]{category_goal_outcome_dag.svg}",
            rf"\includegraphics[keepaspectratio,width=0.8\linewidth]{{{dag_pdf}}}",
        )
        latex = escape_underscores_in_latex_text(latex)
        if r"\documentclass[12pt]{article}" not in latex:
            raise RuntimeError("Could not apply the requested 12-point document font.")
        if r"\includesvg" in latex:
            raise RuntimeError("Could not replace the SVG DAG for LaTeX rendering.")

        tex_path = temp_dir / "notebook.tex"
        tex_path.write_text(latex, encoding="utf-8")
        for filename, data in resources.get("outputs", {}).items():
            resource_path = temp_dir / filename
            resource_path.parent.mkdir(parents=True, exist_ok=True)
            resource_path.write_bytes(data)

        latex_env = os.environ | {"TEXMFVAR": "/tmp/texmf-kickstarter"}
        for _ in range(2):
            subprocess.run(
                ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
                cwd=temp_dir,
                env=latex_env,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(temp_dir / "notebook.pdf", output_path)

    print(f"Created 12-point PDF: {output_path}")


if __name__ == "__main__":
    main()
