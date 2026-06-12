"""Core arena logic - run battles between models."""

import random
from typing import Dict, List, Optional, Tuple

from lmarena.db import Database
from lmarena.providers import get_provider, Provider


class Arena:
    """LLM model arena for side-by-side comparison.

    Usage:
        arena = Arena()
        arena.add_model("qwen3.6", provider="ollama", model="qwen3.6:35b-a3b")
        arena.add_model("mimo", provider="mimo", model="mimo-v2.5-pro")
        results = arena.battle("Explain quantum entanglement")
        arena.rate(response_id=1, rating=9)
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db = Database(db_path)
        self._models = {}  # name -> (provider_name, model_name, provider_instance)
        self._experiment_id = None
        self._system_prompt = ""

    def add_model(self, name: str, provider: str, model: str, **provider_kwargs):
        """Register a model for comparison.

        Args:
            name: Display name for this model
            provider: Provider backend (ollama, openai, mimo)
            model: Model identifier in the provider
            **provider_kwargs: Extra args for provider (api_key, base_url, etc.)
        """
        if name not in self._models:
            prov = get_provider(provider, **provider_kwargs)
            self._models[name] = (provider, model, prov)

    def set_system(self, prompt: str):
        """Set system prompt for all battles."""
        self._system_prompt = prompt

    def start_experiment(self, name: str) -> int:
        """Start a new experiment session."""
        model_names = list(self._models.keys())
        self._experiment_id = self.db.create_experiment(
            name, model_names, self._system_prompt
        )
        return self._experiment_id

    def battle(self, prompt: str, models: Optional[List[str]] = None,
               temperature: float = 0.7, max_tokens: int = 2048,
               blind: bool = True) -> List[Dict]:
        """Run a battle: send the same prompt to multiple models.

        Args:
            prompt: The prompt to test
            models: Specific models to use (None = all registered)
            temperature: Generation temperature
            max_tokens: Max tokens to generate
            blind: Randomize model order to avoid position bias

        Returns:
            List of response dicts with model info, text, latency, etc.
        """
        if not self._experiment_id:
            self.start_experiment("auto")

        target_models = models or list(self._models.keys())
        battle_id = self.db.create_battle(self._experiment_id, prompt)

        # Shuffle for blind evaluation
        if blind:
            target_models = list(target_models)
            random.shuffle(target_models)

        results = []
        for model_name in target_models:
            if model_name not in self._models:
                results.append({
                    "model": model_name,
                    "text": f"[ERROR: model '{model_name}' not registered]",
                    "error": True,
                })
                continue

            provider_name, model_id, provider = self._models[model_name]
            response = provider.generate(
                prompt=prompt,
                model=model_id,
                system=self._system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            resp_id = self.db.save_response(
                battle_id=battle_id,
                model=model_name,
                provider=provider_name,
                response=response["text"],
                tokens=response.get("tokens", 0),
                latency=response.get("latency", 0),
            )

            results.append({
                "id": resp_id,
                "battle_id": battle_id,
                "model": model_name,
                "provider": provider_name,
                "text": response["text"],
                "tokens": response.get("tokens", 0),
                "latency": response.get("latency", 0),
                "error": "error" in response,
            })

        return results

    def rate(self, response_id: int, rating: int, notes: str = ""):
        """Rate a response (1-10 scale)."""
        self.db.rate_response(response_id, rating, notes)

    def leaderboard(self) -> List[Dict]:
        """Get leaderboard for current experiment."""
        if not self._experiment_id:
            return []
        return self.db.get_leaderboard(self._experiment_id)

    def batch_battle(self, prompts: List[str], **kwargs) -> List[List[Dict]]:
        """Run battles on multiple prompts."""
        results = []
        for i, prompt in enumerate(prompts):
            print(f"  Battle {i+1}/{len(prompts)}: {prompt[:60]}...")
            result = self.battle(prompt, **kwargs)
            results.append(result)
        return results

    def export_report(self, experiment_id: Optional[int] = None) -> str:
        """Export experiment results as markdown report."""
        exp_id = experiment_id or self._experiment_id
        if not exp_id:
            return "No experiment to export."

        exp = self.db.get_experiment(exp_id)
        battles = self.db.get_battles(exp_id)
        leaderboard = self.db.get_leaderboard(exp_id)

        lines = [
            f"# Arena Report: {exp['name']}",
            f"",
            f"**Models:** {', '.join(exp['models'])}",
            f"**Battles:** {len(battles)}",
            f"**System prompt:** {exp['system_prompt'] or '(none)'}",
            f"",
        ]

        # Leaderboard
        if leaderboard:
            lines.append("## Leaderboard")
            lines.append("")
            lines.append("| Model | Battles | Avg Rating | Avg Latency | Avg Tokens |")
            lines.append("|-------|---------|------------|-------------|------------|")
            for entry in leaderboard:
                lines.append(
                    f"| {entry['model']} | {entry['battles']} | "
                    f"{entry['avg_rating']:.1f} | "
                    f"{entry['avg_latency']:.1f}s | "
                    f"{entry['avg_tokens']:.0f} |"
                )
            lines.append("")

        # Battle details
        lines.append("## Battles")
        lines.append("")
        for battle in battles:
            lines.append(f"### Prompt")
            lines.append(f"```")
            lines.append(battle["prompt"][:500])
            lines.append(f"```")
            lines.append("")

            responses = self.db.get_battle_responses(battle["id"])
            for resp in responses:
                rating_str = f" ⭐ {resp['rating']}/10" if resp["rating"] else ""
                lines.append(f"**{resp['model']}** ({resp['latency']:.1f}s, {resp['tokens']} tokens){rating_str}")
                lines.append(f"")
                # Truncate long responses
                text = resp["response"]
                if len(text) > 1000:
                    text = text[:1000] + "..."
                lines.append(text)
                lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
