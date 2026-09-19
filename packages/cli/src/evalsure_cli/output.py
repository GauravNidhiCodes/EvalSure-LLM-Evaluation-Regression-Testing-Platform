"""CLI output helpers — never print credentials."""

from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


def print_json(data: Any) -> None:
    console.print_json(json.dumps(data, default=str))


def print_error(message: str) -> None:
    err_console.print(f"[red]Error:[/red] {message}")


def model_dump(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [model_dump(item) for item in obj]
    return obj


def print_table(title: str, columns: list[str], rows: list[list[Any]]) -> None:
    table = Table(title=title, show_header=True, header_style="bold")
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(cell) if cell is not None else "" for cell in row])
    console.print(table)


def print_kv(title: str, mapping: dict[str, Any]) -> None:
    console.print(f"[bold]{title}[/bold]")
    for key, value in mapping.items():
        console.print(f"  {key}: {value}")


def exit_api_error(exc: Exception) -> None:
    print_error(str(exc))
    raise typer.Exit(code=1) from None
