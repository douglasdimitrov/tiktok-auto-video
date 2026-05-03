"""Geração de narração via edge-tts (Microsoft TTS) com legendas word-level."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import edge_tts


@dataclass
class WordCue:
    """Um trecho falado e o intervalo de tempo (em segundos) em que aparece."""

    text: str
    start: float
    end: float


@dataclass
class Narration:
    audio_path: Path
    duration: float
    cues: list[WordCue]


async def _synthesize(text: str, voice: str, audio_path: Path) -> list[WordCue]:
    communicate = edge_tts.Communicate(text=text, voice=voice, boundary="WordBoundary")
    cues: list[WordCue] = []
    with audio_path.open("wb") as f:
        async for chunk in communicate.stream():
            ctype = chunk["type"]
            if ctype == "audio":
                f.write(chunk["data"])
            elif ctype in ("WordBoundary", "SentenceBoundary"):
                start = chunk["offset"] / 10_000_000  # 100ns -> s
                duration = chunk["duration"] / 10_000_000
                cues.append(
                    WordCue(text=chunk["text"], start=start, end=start + duration)
                )
    return cues


def synthesize(text: str, voice: str, out_path: Path) -> Narration:
    """Sintetiza voz salvando MP3 e retornando metadados das palavras."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cues = asyncio.run(_synthesize(text, voice, out_path))
    duration = cues[-1].end if cues else 0.0
    return Narration(audio_path=out_path, duration=duration, cues=cues)


def cues_to_srt(cues: list[WordCue], words_per_cue: int = 4) -> str:
    """Agrupa palavras em legendas curtas estilo TikTok (3-5 palavras por linha)."""
    if not cues:
        return ""
    blocks: list[str] = []
    idx = 1
    for chunk_start in range(0, len(cues), words_per_cue):
        group = cues[chunk_start : chunk_start + words_per_cue]
        if not group:
            continue
        start = group[0].start
        end = group[-1].end
        text = " ".join(c.text for c in group)
        blocks.append(
            f"{idx}\n{_fmt_ts(start)} --> {_fmt_ts(end)}\n{text}\n"
        )
        idx += 1
    return "\n".join(blocks)


def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


async def list_voices(language: str | None = None) -> list[dict]:
    """Lista vozes disponíveis (útil pra usuário escolher)."""
    voices: list[dict] = [dict(v) for v in await edge_tts.list_voices()]
    if language:
        voices = [v for v in voices if v["Locale"].startswith(language)]
    return voices
