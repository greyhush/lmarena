#!/usr/bin/env python3
"""lmarena CLI - LLM model arena for side-by-side comparison."""

import argparse
import json
import sys


def _load_config():
    """Load config from ~/.lmarena/config.json."""
    from pathlib import Path
    config_path = Path.home() / ".lmarena" / "config.json"
    if config_path.exists():
        return json.loads(config_path.read_text())
    return {}


def _save_config(config):
    from pathlib import Path
    config_path = Path.home() / ".lmarena" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2))


def cmd_add(args):
    """Add a model to the config."""
    config = _load_config()
    if "models" not in config:
        config["models"] = {}

    config["models"][args.name] = {
        "provider": args.provider,
        "model": args.model,
    }
    if args.api_key:
        config["models"][args.name]["api_key"] = args.api_key
    if args.base_url:
        config["models"][args.name]["base_url"] = args.base_url

    _save_config(config)
    print(f"Added model '{args.name}' ({args.provider}/{args.model})")


def cmd_remove(args):
    """Remove a model from config."""
    config = _load_config()
    if "models" in config and args.name in config["models"]:
        del config["models"][args.name]
        _save_config(config)
        print(f"Removed model '{args.name}'")
    else:
        print(f"Model '{args.name}' not found")


def cmd_models(args):
    """List configured models."""
    config = _load_config()
    models = config.get("models", {})
    if not models:
        print("No models configured. Use 'lmarena add' to add models.")
        return

    print(f"\n  Configured Models:")
    print(f"  {'='*50}")
    for name, info in models.items():
        print(f"  {name:<20} {info['provider']}/{info['model']}")
    print()


def cmd_battle(args):
    """Run a battle between models."""
    from lmarena.arena import Arena
    from lmarena.display import print_battle_results

    config = _load_config()
    models_config = config.get("models", {})

    if not models_config:
        print("No models configured. Use 'lmarena add' first.")
        return

    # Determine which models to use
    if args.models:
        target_models = [m.strip() for m in args.models.split(",")]
    else:
        target_models = list(models_config.keys())

    if len(target_models) < 2:
        print("Need at least 2 models for a battle.")
        return

    # Setup arena
    arena = Arena(args.db)
    for name in target_models:
        if name not in models_config:
            print(f"Warning: model '{name}' not in config, skipping")
            continue
        info = models_config[name]
        kwargs = {}
        if "api_key" in info:
            kwargs["api_key"] = info["api_key"]
        if "base_url" in info:
            kwargs["base_url"] = info["base_url"]
        arena.add_model(name, provider=info["provider"], model=info["model"], **kwargs)

    if args.system:
        arena.set_system(args.system)

    if not args.continue_exp:
        exp_id = arena.start_experiment(args.name or "battle")
        print(f"Started experiment #{exp_id}")
    else:
        arena._experiment_id = args.continue_exp

    # Get prompt
    if args.prompt:
        prompt = args.prompt
    elif args.file:
        from pathlib import Path
        prompt = Path(args.file).read_text(encoding="utf-8")
    else:
        print("Enter prompt (Ctrl+D to finish):")
        try:
            prompt = sys.stdin.read().strip()
        except KeyboardInterrupt:
            return

    if not prompt:
        print("Empty prompt, aborting.")
        return

    # Run battle
    print(f"\nRunning battle with {len(target_models)} models...")
    results = arena.battle(
        prompt,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        blind=not args.no_blind,
    )

    print_battle_results(results)

    # Interactive rating
    if not args.no_rate:
        print("Rate each response (1-10, Enter to skip, 'q' to quit):")
        for i, r in enumerate(results):
            if r.get("error"):
                continue
            label = f"Model {chr(65+i)}"
            try:
                rating_str = input(f"  {label} (id={r['id']}): ").strip()
                if rating_str.lower() == 'q':
                    break
                if rating_str:
                    rating = int(rating_str)
                    if 1 <= rating <= 10:
                        arena.rate(r["id"], rating)
                        print(f"    → Rated {rating}/10")
                    else:
                        print(f"    → Skipped (use 1-10)")
            except (ValueError, EOFError, KeyboardInterrupt):
                pass

    arena.close()
    print("\nDone!")


def cmd_leaderboard(args):
    """Show leaderboard."""
    from lmarena.db import Database
    from lmarena.display import print_leaderboard

    db = Database(args.db)

    if args.experiment:
        entries = db.get_leaderboard(args.experiment)
    else:
        # Show overall stats
        experiments = db.list_experiments()
        if not experiments:
            print("No experiments yet.")
            return
        entries = db.get_leaderboard(experiments[0]["id"])

    print_leaderboard(entries)
    db.close()


def cmd_experiments(args):
    """List experiments."""
    from lmarena.db import Database
    from lmarena.display import print_experiments

    db = Database(args.db)
    exps = db.list_experiments(limit=args.limit)
    print_experiments(exps)
    db.close()


def cmd_report(args):
    """Export experiment report."""
    from lmarena.arena import Arena

    arena = Arena(args.db)
    report = arena.export_report(args.experiment)

    if args.output:
        from pathlib import Path
        Path(args.output).write_text(report)
        print(f"Report saved to: {args.output}")
    else:
        print(report)
    arena.close()


def cmd_run(args):
    """Run a batch of prompts from a file."""
    from pathlib import Path
    from lmarena.arena import Arena
    from lmarena.display import print_battle_results, print_leaderboard

    config = _load_config()
    models_config = config.get("models", {})

    if args.models:
        target_models = [m.strip() for m in args.models.split(",")]
    else:
        target_models = list(models_config.keys())

    arena = Arena(args.db)
    for name in target_models:
        info = models_config[name]
        kwargs = {}
        if "api_key" in info:
            kwargs["api_key"] = info["api_key"]
        if "base_url" in info:
            kwargs["base_url"] = info["base_url"]
        arena.add_model(name, provider=info["provider"], model=info["model"], **kwargs)

    if args.system:
        arena.set_system(args.system)

    arena.start_experiment(args.name or "batch")

    # Load prompts
    prompt_file = Path(args.file)
    if prompt_file.suffix == ".json":
        prompts = json.loads(prompt_file.read_text())
        if isinstance(prompts, list) and isinstance(prompts[0], dict):
            prompts = [p.get("prompt", p.get("question", str(p))) for p in prompts]
    else:
        prompts = [line.strip() for line in prompt_file.read_text().split("\n") if line.strip()]

    print(f"Running {len(prompts)} prompts...")
    all_results = arena.batch_battle(prompts, temperature=args.temperature)

    print(f"\n{'='*50}")
    print("Results:")
    for i, results in enumerate(all_results):
        for r in results:
            if not r.get("error"):
                print(f"  Prompt {i+1} | {r['model']}: {r['latency']:.1f}s, {r['tokens']} tokens")

    print(f"\nRate responses in interactive mode with 'lmarena battle --continue-exp {arena._experiment_id}'")
    arena.close()


def main():
    parser = argparse.ArgumentParser(
        prog="lmarena",
        description="LLM model arena - compare models side-by-side"
    )
    parser.add_argument("--db", default=None, help="Database path")

    sub = parser.add_subparsers(dest="command")

    # add
    p = sub.add_parser("add", help="Add a model")
    p.add_argument("name", help="Model display name")
    p.add_argument("--provider", "-p", required=True, choices=["ollama", "openai", "mimo"],
                   help="Provider backend")
    p.add_argument("--model", "-m", required=True, help="Model identifier")
    p.add_argument("--api-key", default=None, help="API key")
    p.add_argument("--base-url", default=None, help="API base URL")

    # remove
    p = sub.add_parser("remove", help="Remove a model")
    p.add_argument("name", help="Model name")

    # models
    sub.add_parser("models", help="List configured models")

    # battle
    p = sub.add_parser("battle", help="Run a battle")
    p.add_argument("--prompt", default=None, help="Prompt text")
    p.add_argument("--file", "-f", default=None, help="Prompt from file")
    p.add_argument("--models", default=None, help="Comma-separated model names")
    p.add_argument("--system", "-s", default=None, help="System prompt")
    p.add_argument("--name", "-n", default=None, help="Experiment name")
    p.add_argument("--temperature", "-t", type=float, default=0.7)
    p.add_argument("--max-tokens", type=int, default=2048)
    p.add_argument("--no-blind", action="store_true", help="Show model names")
    p.add_argument("--no-rate", action="store_true", help="Skip rating")
    p.add_argument("--continue-exp", type=int, default=None, help="Continue experiment")

    # leaderboard
    p = sub.add_parser("leaderboard", help="Show leaderboard")
    p.add_argument("--experiment", "-e", type=int, default=None, help="Experiment ID")

    # experiments
    p = sub.add_parser("experiments", help="List experiments")
    p.add_argument("--limit", "-l", type=int, default=20)

    # report
    p = sub.add_parser("report", help="Export report")
    p.add_argument("--experiment", "-e", type=int, required=True, help="Experiment ID")
    p.add_argument("--output", "-o", default=None, help="Output file")

    # run (batch)
    p = sub.add_parser("run", help="Batch battle from file")
    p.add_argument("file", help="Prompts file (txt or json)")
    p.add_argument("--name", "-n", default=None, help="Experiment name")
    p.add_argument("--models", default=None, help="Comma-separated model names")
    p.add_argument("--system", "-s", default=None, help="System prompt")
    p.add_argument("--temperature", "-t", type=float, default=0.7)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "add": cmd_add,
        "remove": cmd_remove,
        "models": cmd_models,
        "battle": cmd_battle,
        "leaderboard": cmd_leaderboard,
        "experiments": cmd_experiments,
        "report": cmd_report,
        "run": cmd_run,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
