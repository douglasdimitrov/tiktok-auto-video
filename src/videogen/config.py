"""Configuração global carregada de variáveis de ambiente / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    pexels_api_key: str | None
    pixabay_api_key: str | None
    voice: str
    width: int
    height: int
    fps: int
    output_dir: Path
    cache_dir: Path

    @classmethod
    def load(cls) -> Settings:
        output_dir = Path(os.getenv("VIDEOGEN_OUTPUT_DIR", ROOT / "output")).resolve()
        cache_dir = Path(os.getenv("VIDEOGEN_CACHE_DIR", ROOT / "assets" / "cache")).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            pexels_api_key=os.getenv("PEXELS_API_KEY") or None,
            pixabay_api_key=os.getenv("PIXABAY_API_KEY") or None,
            voice=os.getenv("VIDEOGEN_VOICE", "pt-BR-FranciscaNeural"),
            width=int(os.getenv("VIDEOGEN_WIDTH", "1080")),
            height=int(os.getenv("VIDEOGEN_HEIGHT", "1920")),
            fps=int(os.getenv("VIDEOGEN_FPS", "30")),
            output_dir=output_dir,
            cache_dir=cache_dir,
        )


SETTINGS = Settings.load()
