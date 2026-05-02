"""Montagem do vídeo final 9:16 com narração, fundo e legendas estilo TikTok."""

from __future__ import annotations

from pathlib import Path

from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)

from videogen.config import SETTINGS
from videogen.stock import StockClip
from videogen.tts import Narration, WordCue


def build_video(
    *,
    narration: Narration,
    backgrounds: list[StockClip],
    out_path: Path,
    title: str | None = None,
    music_path: Path | None = None,
    music_volume: float = 0.10,
    words_per_caption: int = 3,
) -> Path:
    """Monta o vídeo final 9:16 e grava em out_path."""
    width = SETTINGS.width
    height = SETTINGS.height
    fps = SETTINGS.fps
    duration = narration.duration

    if duration <= 0:
        raise ValueError("Narração tem duração 0; verifique o roteiro.")

    background = _make_background(backgrounds, duration, width, height)

    layers: list = [background]

    if title:
        layers.append(_title_clip(title, width, height, duration))

    layers.extend(_caption_clips(narration.cues, width, height, words_per_caption))

    final = CompositeVideoClip(layers, size=(width, height)).with_duration(duration)

    audio = AudioFileClip(str(narration.audio_path)).with_duration(duration)
    if music_path and music_path.exists():
        try:
            from moviepy import CompositeAudioClip

            music = (
                AudioFileClip(str(music_path))
                .with_duration(duration)
                .with_volume_scaled(music_volume)
            )
            audio = CompositeAudioClip([music, audio])
        except Exception as exc:  # noqa: BLE001
            print(f"[video] não foi possível mixar música ({exc}), seguindo sem música.")

    final = final.with_audio(audio)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(out_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
    )
    return out_path


def _make_background(clips: list[StockClip], duration: float, width: int, height: int):
    if not clips:
        return ColorClip(size=(width, height), color=(20, 20, 40)).with_duration(duration)

    per_clip = max(2.5, duration / len(clips))
    rendered = []
    for clip in clips:
        if clip.is_video:
            rendered.append(_video_clip(clip.path, per_clip, width, height))
        else:
            rendered.append(_image_clip(clip.path, per_clip, width, height))

    seq = concatenate_videoclips(rendered, method="chain")
    if seq.duration < duration:
        seq = seq.with_duration(duration)
    else:
        seq = seq.subclipped(0, duration)
    return seq


def _image_clip(path: Path, duration: float, width: int, height: int):
    """Imagem com efeito Ken Burns (zoom suave)."""
    base = ImageClip(str(path)).with_duration(duration)
    base = _cover_resize(base, width, height)

    def make_frame(t):
        zoom = 1.05 + 0.05 * (t / duration)
        frame = base.resized(zoom).get_frame(t)
        return frame

    from moviepy import VideoClip

    return VideoClip(make_frame, duration=duration).with_duration(duration)


def _video_clip(path: Path, duration: float, width: int, height: int):
    clip = VideoFileClip(str(path))
    if clip.duration < duration:
        clip = clip.with_effects([])
    clip = clip.subclipped(0, min(duration, clip.duration))
    clip = _cover_resize(clip, width, height)
    if clip.duration < duration:
        clip = clip.with_duration(duration)
    return clip.without_audio()


def _cover_resize(clip, target_w: int, target_h: int):
    """Resize 'cover' style: enche o frame mantendo proporção, cortando excessos."""
    w, h = clip.size
    scale = max(target_w / w, target_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    clip = clip.resized((new_w, new_h))
    x_off = (new_w - target_w) // 2
    y_off = (new_h - target_h) // 2
    return clip.cropped(x1=x_off, y1=y_off, x2=x_off + target_w, y2=y_off + target_h)


def _caption_clips(
    cues: list[WordCue], width: int, height: int, words_per_caption: int
):
    """Cria TextClips estilo TikTok para grupos de palavras."""
    if not cues:
        return []

    out = []
    font_size = int(height * 0.045)
    y_pos = int(height * 0.62)

    for chunk_start in range(0, len(cues), words_per_caption):
        group = cues[chunk_start : chunk_start + words_per_caption]
        if not group:
            continue
        start = group[0].start
        end = group[-1].end
        text = " ".join(c.text for c in group).upper()
        try:
            txt = TextClip(
                text=text,
                font_size=font_size,
                color="white",
                stroke_color="black",
                stroke_width=6,
                method="caption",
                size=(int(width * 0.85), None),
                text_align="center",
            )
        except Exception:
            txt = TextClip(text=text, font_size=font_size, color="white")
        txt = (
            txt.with_start(start)
            .with_end(end)
            .with_position(("center", y_pos))
        )
        out.append(txt)
    return out


def _title_clip(title: str, width: int, height: int, duration: float):
    try:
        clip = TextClip(
            text=title,
            font_size=int(height * 0.055),
            color="white",
            stroke_color="black",
            stroke_width=8,
            method="caption",
            size=(int(width * 0.9), None),
            text_align="center",
        )
    except Exception:
        clip = TextClip(text=title, font_size=int(height * 0.05), color="white")
    return (
        clip.with_start(0)
        .with_end(min(3.0, duration))
        .with_position(("center", int(height * 0.12)))
    )
