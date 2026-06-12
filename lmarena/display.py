"""Terminal display for arena results."""

from typing import Dict, List, Optional


def _truncate(text: str, max_len: int = 500) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def print_battle_results(results: List[Dict]):
    """Print battle results side-by-side."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        HAS_RICH = True
    except ImportError:
        HAS_RICH = False

    if HAS_RICH:
        _print_rich_battle(results)
    else:
        _print_plain_battle(results)


def _print_rich_battle(results: List[Dict]):
    from rich.console import Console
    from rich.panel import Panel
    from rich.columns import Columns

    console = Console()

    for i, r in enumerate(results):
        label = f"Model {chr(65+i)}"  # A, B, C, ...
        header = f"[bold]{label}[/bold]"

        if r.get("error"):
            header += " [red][ERROR][/red]"
        else:
            latency = r.get("latency", 0)
            tokens = r.get("tokens", 0)
            header += f" [dim]({latency:.1f}s, {tokens} tokens)[/dim]"

        text = _truncate(r.get("text", ""), 800)

        panel = Panel(
            text,
            title=header,
            border_style="blue" if not r.get("error") else "red",
            width=80,
        )
        console.print(panel)

    console.print()
    console.print("[dim]Models are shown in random order (blind mode). Rate each response 1-10.[/dim]")
    console.print()


def _print_plain_battle(results: List[Dict]):
    for i, r in enumerate(results):
        label = f"Model {chr(65+i)}"
        latency = r.get("latency", 0)
        tokens = r.get("tokens", 0)

        print(f"\n{'='*60}")
        print(f"  {label} ({latency:.1f}s, {tokens} tokens)")
        print(f"{'='*60}")
        print(_truncate(r.get("text", ""), 800))

    print(f"\n  Blind mode - rate each response 1-10\n")


def print_leaderboard(entries: List[Dict]):
    """Print leaderboard table."""
    try:
        from rich.console import Console
        from rich.table import Table
        HAS_RICH = True
    except ImportError:
        HAS_RICH = False

    if not entries:
        print("No rated battles yet.")
        return

    if HAS_RICH:
        console = Console()
        table = Table(title="🏆 Leaderboard")
        table.add_column("Rank", style="dim", width=4)
        table.add_column("Model", style="bold")
        table.add_column("Battles", justify="right")
        table.add_column("Avg Rating", justify="right", style="green")
        table.add_column("Avg Latency", justify="right")
        table.add_column("Avg Tokens", justify="right")

        for i, entry in enumerate(entries):
            table.add_row(
                str(i + 1),
                entry["model"],
                str(entry["battles"]),
                f"{entry['avg_rating']:.1f}",
                f"{entry['avg_latency']:.1f}s",
                f"{entry['avg_tokens']:.0f}",
            )
        console.print(table)
    else:
        print(f"\n{'Rank':<5} {'Model':<20} {'Battles':<8} {'Avg Rating':<12} {'Latency':<10}")
        print("-" * 55)
        for i, entry in enumerate(entries):
            print(f"{i+1:<5} {entry['model']:<20} {entry['battles']:<8} "
                  f"{entry['avg_rating']:<12.1f} {entry['avg_latency']:<10.1f}s")
        print()


def print_experiments(experiments: List[Dict]):
    """Print list of experiments."""
    if not experiments:
        print("No experiments yet.")
        return

    try:
        from rich.console import Console
        from rich.table import Table
        HAS_RICH = True
    except ImportError:
        HAS_RICH = False

    if HAS_RICH:
        console = Console()
        table = Table(title="Experiments")
        table.add_column("ID", style="dim")
        table.add_column("Name", style="bold")
        table.add_column("Models")
        table.add_column("Created")

        import time
        for exp in experiments:
            created = time.strftime("%Y-%m-%d %H:%M", time.localtime(exp["created_at"]))
            table.add_row(
                str(exp["id"]),
                exp["name"],
                ", ".join(exp["models"]),
                created,
            )
        console.print(table)
    else:
        for exp in experiments:
            import time
            created = time.strftime("%Y-%m-%d %H:%M", time.localtime(exp["created_at"]))
            print(f"  [{exp['id']}] {exp['name']} - {', '.join(exp['models'])} ({created})")
