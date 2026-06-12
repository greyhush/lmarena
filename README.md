# lmarena

LLM model arena. Same prompt, multiple models, side-by-side comparison. Blind evaluation. Track results.

No cloud. No accounts. Local SQLite. Works with Ollama, OpenAI-compatible APIs, and more.

## Install

```bash
pip install -e .

# With Rich terminal UI:
pip install -e ".[rich]"
```

## Quick Start

```bash
# Add models
lmarena add qwen3.6 --provider ollama --model qwen3.6:35b-a3b
lmarena add mimo --provider mimo --model mimo-v2.5-pro --api-key YOUR_KEY
lmarena add deepseek --provider openai --model deepseek-chat --api-key YOUR_KEY --base-url https://api.deepseek.com/v1

# List configured models
lmarena models

# Run a battle (interactive prompt)
lmarena battle --name "physics-test"

# Battle with a specific prompt
lmarena battle --prompt "Explain quantum entanglement in simple terms"

# Battle from a file
lmarena battle --file prompt.txt --system "You are a physics professor"

# Batch battle from a file
lmarena run prompts.txt --name "reasoning-test"

# Show leaderboard
lmarena leaderboard

# List experiments
lmarena experiments

# Export report
lmarena report --experiment 1 --output report.md
```

## How It Works

1. **Configure models** - Add any number of LLMs (local Ollama, OpenAI API, DeepSeek, etc.)
2. **Run battles** - Same prompt sent to all models simultaneously
3. **Blind evaluation** - Model names hidden during rating to avoid bias
4. **Rate responses** - Score each response 1-10
5. **Track results** - All data stored in local SQLite
6. **Leaderboard** - See which model performs best across battles

## Commands

| Command | Description |
|---------|-------------|
| `lmarena add NAME` | Add a model to the config |
| `lmarena remove NAME` | Remove a model |
| `lmarena models` | List configured models |
| `lmarena battle` | Run a battle between models |
| `lmarena run FILE` | Batch battle from file |
| `lmarena leaderboard` | Show leaderboard |
| `lmarena experiments` | List experiments |
| `lmarena report` | Export markdown report |

## Python API

```python
from lmarena import Arena

arena = Arena()
arena.add_model("qwen", provider="ollama", model="qwen3.6:35b-a3b")
arena.add_model("mimo", provider="mimo", model="mimo-v2.5-pro", api_key="...")

arena.start_experiment("physics-test")
arena.set_system("You are a physics professor")

# Run a battle
results = arena.battle("Explain quantum entanglement")
for r in results:
    print(f"{r['model']}: {r['latency']:.1f}s")

# Rate
arena.rate(results[0]["id"], 8)
arena.rate(results[1]["id"], 9)

# Leaderboard
print(arena.leaderboard())
```

## Supported Providers

| Provider | Backend | Models |
|----------|---------|--------|
| `ollama` | Local Ollama | Any Ollama model |
| `openai` | OpenAI-compatible API | GPT-4, DeepSeek, vLLM, etc. |
| `mimo` | MiMo (Xiaomi) | mimo-v2.5-pro, etc. |

## Storage

All data in `~/.lmarena/lmarena.db` (SQLite). Config in `~/.lmarena/config.json`.

## License

MIT
