import yaml
from pathlib import Path

p = Path(r"C:\Users\ADMIN\AppData\Local\hermes\config.yaml")
data = yaml.safe_load(p.read_text(encoding="utf-8"))

data["model"]["default"] = "google/gemini-2.5-flash"
data["fallback_providers"] = [
    {"provider": "openrouter", "model": "google/gemini-2.5-flash-lite"},
    {"provider": "openrouter", "model": "openai/gpt-4o-mini"}
]

p.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("✅ Updated config.yaml successfully with fallback chain!")
