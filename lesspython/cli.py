from pathlib import Path
from typing import List

import typer

from lesspython.core import scan_folder
from lesspython.report import format_yaml_report


app = typer.Typer()


@app.command()
def main(
    folder: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True
    ),
    min_lines: int = typer.Option(
        5, "--min-lines", "-m", help="Minimum number of lines in a fragment"
    ),
    normalize_literals: bool = typer.Option(
        False,
        "--normalize-literals",
        help="Treat literal values as equal (e.g., strings/numbers)",
    ),
    exclude: List[Path] = typer.Option(
        [],
        "--exclude",
        "-e",
        help="Paths to exclude (relative to the scanned folder or absolute). Can be repeated.",
    ),
) -> None:
    """Find duplicated Python code fragments by hashing normalized AST subtrees."""
    report = scan_folder(
        folder,
        min_lines=min_lines,
        normalize_literals=normalize_literals,
        exclude_paths=exclude,
    )
    typer.echo(format_yaml_report(report))

    if report.python_files == 0:
        raise typer.Exit(code=1)
    if report.groups:
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()

