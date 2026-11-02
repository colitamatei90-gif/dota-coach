"""Cai catre fisiere - functioneaza si ca script, si ca .exe (PyInstaller)."""
import json
import os
import sys

if getattr(sys, "frozen", False):           # rulam din .exe
    BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    APP_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = APP_DIR = os.path.dirname(os.path.abspath(__file__))

CACHE_DIR = os.path.join(APP_DIR, "cache")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
os.makedirs(CACHE_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "port": 3000,
    "stratz_token": "",          # gratuit de pe https://stratz.com/api
    "ai_provider": "",           # "gemini" (gratuit) sau "anthropic"; gol = automat
    "gemini_api_key": "",        # gratuit de pe https://aistudio.google.com/apikey
    "gemini_model": "",          # gol = aleg automat cel mai bun model Flash disponibil
    "anthropic_api_key": "",     # sau variabila de mediu ANTHROPIC_API_KEY
    "ai_model": "claude-opus-5-5",
    "position": "",              # "", POSITION_1 ... POSITION_5
    "bracket": "",               # "", HERALD_GUARDIAN, CRUSADER_ARCHON, LEGEND_ANCIENT, DIVINE_IMMORTAL
    "open_browser": True,
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        save_config(cfg)
    except Exception as e:
        print(f"[config] config.json invalid ({e}), folosesc valorile implicite")
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
