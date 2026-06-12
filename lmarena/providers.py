"""LLM provider abstraction - unified interface for different backends."""

import json
import urllib.request
from typing import Dict, List, Optional


class Provider:
    """Base provider interface."""

    def __init__(self, name: str, **kwargs):
        self.name = name

    def generate(self, prompt: str, model: str, system: str = "",
                 temperature: float = 0.7, max_tokens: int = 2048) -> Dict:
        """Generate a response. Returns {"text": str, "tokens": int, "latency": float}."""
        raise NotImplementedError

    def list_models(self) -> List[str]:
        """List available models."""
        raise NotImplementedError


class OllamaProvider(Provider):
    """Ollama local inference."""

    def __init__(self, base_url: str = "http://localhost:11434", **kwargs):
        super().__init__("ollama", **kwargs)
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt: str, model: str, system: str = "",
                 temperature: float = 0.7, max_tokens: int = 2048) -> Dict:
        import time
        start = time.time()

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        try:
            resp = urllib.request.urlopen(req, timeout=300)
            result = json.loads(resp.read().decode())
            latency = time.time() - start

            return {
                "text": result.get("response", ""),
                "tokens": result.get("eval_count", 0),
                "latency": latency,
                "model": model,
                "provider": self.name,
            }
        except Exception as e:
            return {
                "text": f"[ERROR: {e}]",
                "tokens": 0,
                "latency": time.time() - start,
                "model": model,
                "provider": self.name,
                "error": str(e),
            }

    def list_models(self) -> List[str]:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read().decode())
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []


class OpenAICompatibleProvider(Provider):
    """OpenAI-compatible API (OpenAI, DeepSeek, vLLM, etc.)."""

    def __init__(self, base_url: str = "https://api.openai.com/v1",
                 api_key: str = "", **kwargs):
        super().__init__("openai", **kwargs)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def generate(self, prompt: str, model: str, system: str = "",
                 temperature: float = 0.7, max_tokens: int = 2048) -> Dict:
        import time
        start = time.time()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        data = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers=headers,
        )

        try:
            resp = urllib.request.urlopen(req, timeout=300)
            result = json.loads(resp.read().decode())
            latency = time.time() - start

            text = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})
            tokens = usage.get("completion_tokens", 0)

            return {
                "text": text,
                "tokens": tokens,
                "latency": latency,
                "model": model,
                "provider": self.name,
            }
        except Exception as e:
            return {
                "text": f"[ERROR: {e}]",
                "tokens": 0,
                "latency": time.time() - start,
                "model": model,
                "provider": self.name,
                "error": str(e),
            }

    def list_models(self) -> List[str]:
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            req = urllib.request.Request(
                f"{self.base_url}/models", headers=headers
            )
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read().decode())
            return [m["id"] for m in data.get("data", [])]
        except Exception:
            return []


class MiMoProvider(OpenAICompatibleProvider):
    """MiMo (Xiaomi) provider - OpenAI compatible."""

    def __init__(self, api_key: str = "", **kwargs):
        super().__init__(
            base_url="https://api.mimo.xiaomi.com/v1",
            api_key=api_key,
            **kwargs,
        )
        self.name = "mimo"


# ── Provider Registry ───────────────────────────────────────────────────

PROVIDERS = {
    "ollama": OllamaProvider,
    "openai": OpenAICompatibleProvider,
    "mimo": MiMoProvider,
}


def get_provider(name: str, **kwargs) -> Provider:
    """Get a provider by name."""
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
    return PROVIDERS[name](**kwargs)


def register_provider(name: str, cls: type):
    """Register a custom provider."""
    PROVIDERS[name] = cls
