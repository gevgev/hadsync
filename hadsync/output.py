from rich.console import Console

console = Console()
_err_console = Console(stderr=True)


def success(msg: str) -> None:
    console.print(f"[green]✔[/green]  {msg}")


def error(msg: str) -> None:
    _err_console.print(f"[red]✗[/red]  {msg}")


def warn(msg: str) -> None:
    console.print(f"[yellow]⚠[/yellow]  {msg}")


def info(msg: str) -> None:
    console.print(f"[dim]ℹ[/dim]  {msg}")
