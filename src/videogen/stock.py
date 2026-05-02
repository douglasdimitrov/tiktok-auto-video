"""Busca de imagens/vídeos de fundo para o vídeo (Pexels / Pixabay / pasta local)."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from pathlib import Path

import requests

from videogen.config import SETTINGS


@dataclass
class StockClip:
    path: Path
    is_video: bool


def fetch_backgrounds(
    query: str,
    *,
    count: int = 5,
    prefer_videos: bool = False,
    local_dir: Path | None = None,
) -> list[StockClip]:
    """Retorna uma lista de clipes de fundo. Tenta nesta ordem:

    1. Diretório local (se fornecido) — usa imagens/vídeos do usuário
    2. Pexels (se PEXELS_API_KEY definido)
    3. Pixabay (se PIXABAY_API_KEY definido)
    4. Fundo gradiente gerado proceduralmente (fallback sempre disponível)
    """
    if local_dir and local_dir.exists():
        clips = _from_local(local_dir, count)
        if clips:
            return clips

    if SETTINGS.pexels_api_key:
        try:
            return _from_pexels(query, count, prefer_videos)
        except Exception as exc:  # noqa: BLE001
            print(f"[stock] Pexels falhou ({exc}), tentando próximo...")

    if SETTINGS.pixabay_api_key:
        try:
            return _from_pixabay(query, count, prefer_videos)
        except Exception as exc:  # noqa: BLE001
            print(f"[stock] Pixabay falhou ({exc}), usando gradiente...")

    return _gradient_fallback(count)


def _from_local(directory: Path, count: int) -> list[StockClip]:
    exts_img = {".jpg", ".jpeg", ".png", ".webp"}
    exts_vid = {".mp4", ".mov", ".webm", ".mkv"}
    files = [
        p
        for p in directory.iterdir()
        if p.is_file() and (p.suffix.lower() in exts_img or p.suffix.lower() in exts_vid)
    ]
    if not files:
        return []
    random.shuffle(files)
    chosen = (files * ((count // len(files)) + 1))[:count]
    return [StockClip(path=p, is_video=p.suffix.lower() in exts_vid) for p in chosen]


def _from_pexels(query: str, count: int, prefer_videos: bool) -> list[StockClip]:
    api_key = SETTINGS.pexels_api_key
    assert api_key
    headers = {"Authorization": api_key}

    if prefer_videos:
        url = "https://api.pexels.com/videos/search"
        params: dict[str, str] = {
            "query": query,
            "per_page": str(max(count, 5)),
            "orientation": "portrait",
            "size": "medium",
        }
        r = requests.get(url, headers=headers, params=params, timeout=20)
        r.raise_for_status()
        items = r.json().get("videos", [])
        out: list[StockClip] = []
        for item in items[:count]:
            files = item.get("video_files", [])
            files.sort(key=lambda f: abs(f.get("width", 0) - 1080))
            if not files:
                continue
            video_url = files[0]["link"]
            out.append(StockClip(path=_download(video_url, ".mp4"), is_video=True))
        if out:
            return out

    url = "https://api.pexels.com/v1/search"
    params = {
        "query": query,
        "per_page": str(max(count, 5)),
        "orientation": "portrait",
        "size": "large",
    }
    r = requests.get(url, headers=headers, params=params, timeout=20)
    r.raise_for_status()
    photos = r.json().get("photos", [])
    out = []
    for photo in photos[:count]:
        src = photo["src"]["large2x"]
        out.append(StockClip(path=_download(src, ".jpg"), is_video=False))
    return out


def _from_pixabay(query: str, count: int, prefer_videos: bool) -> list[StockClip]:
    api_key = SETTINGS.pixabay_api_key
    assert api_key
    if prefer_videos:
        r = requests.get(
            "https://pixabay.com/api/videos/",
            params={"key": api_key, "q": query, "per_page": str(max(count, 3))},
            timeout=20,
        )
        r.raise_for_status()
        hits = r.json().get("hits", [])
        out: list[StockClip] = []
        for hit in hits[:count]:
            video_url = hit["videos"]["medium"]["url"]
            out.append(StockClip(path=_download(video_url, ".mp4"), is_video=True))
        if out:
            return out

    r = requests.get(
        "https://pixabay.com/api/",
        params={
            "key": api_key,
            "q": query,
            "per_page": str(max(count, 3)),
            "image_type": "photo",
        },
        timeout=20,
    )
    r.raise_for_status()
    hits = r.json().get("hits", [])
    return [StockClip(path=_download(h["largeImageURL"], ".jpg"), is_video=False) for h in hits[:count]]


def _gradient_fallback(count: int) -> list[StockClip]:
    """Gera imagens de gradiente quando não há API key. Usado como último recurso."""
    from PIL import Image

    palettes = [
        ((10, 10, 40), (80, 0, 120)),
        ((0, 30, 60), (10, 100, 180)),
        ((40, 0, 60), (180, 30, 100)),
        ((20, 40, 0), (60, 180, 80)),
        ((50, 10, 0), (200, 80, 30)),
    ]
    out: list[StockClip] = []
    for i in range(count):
        color_a, color_b = palettes[i % len(palettes)]
        img = Image.new("RGB", (SETTINGS.width, SETTINGS.height))
        for y in range(SETTINGS.height):
            t = y / max(1, SETTINGS.height - 1)
            r = int(color_a[0] + (color_b[0] - color_a[0]) * t)
            g = int(color_a[1] + (color_b[1] - color_a[1]) * t)
            b = int(color_a[2] + (color_b[2] - color_a[2]) * t)
            for x in range(SETTINGS.width):
                img.putpixel((x, y), (r, g, b))
        path = SETTINGS.cache_dir / f"gradient_{i}_{color_a[0]}_{color_b[2]}.png"
        if not path.exists():
            img.save(path)
        out.append(StockClip(path=path, is_video=False))
    return out


def _download(url: str, suffix: str) -> Path:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    path = SETTINGS.cache_dir / f"{h}{suffix}"
    if path.exists() and path.stat().st_size > 0:
        return path
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                f.write(chunk)
    return path
