"""Gerenciador de jobs de geração de vídeo em background.

Mantém o estado de cada job em memória (thread-safe) e executa o pipeline pesado
num executor separado para não travar o event loop do FastAPI.
"""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from videogen.config import SETTINGS
from videogen.script import Script, generate_script, script_from_text
from videogen.stock import fetch_backgrounds
from videogen.tts import cues_to_srt, synthesize
from videogen.video import build_video

JobStatus = Literal["queued", "running", "done", "error"]


@dataclass
class JobLog:
    timestamp: float
    message: str


@dataclass
class Job:
    id: str
    theme: str | None
    script_text: str | None
    title: str | None
    voice: str
    duration: int
    bg_query: str | None
    use_videos: bool
    local_bg: Path | None
    music: Path | None
    words_per_caption: int
    status: JobStatus = "queued"
    progress: int = 0
    logs: list[JobLog] = field(default_factory=list)
    error: str | None = None
    video_path: Path | None = None
    srt_path: Path | None = None
    meta_path: Path | None = None
    final_title: str | None = None
    caption: str | None = None
    hashtags: list[str] = field(default_factory=list)
    audio_duration: float | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None


class JobManager:
    """Singleton thread-safe que armazena e executa jobs de geração."""

    def __init__(self, max_workers: int = 1) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="videogen")

    def submit(self, job: Job) -> Job:
        with self._lock:
            self._jobs[job.id] = job
        self._executor.submit(self._run, job.id)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def _log(self, job: Job, message: str, progress: int | None = None) -> None:
        with self._lock:
            job.logs.append(JobLog(timestamp=time.time(), message=message))
            if progress is not None:
                job.progress = progress

    def _run(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None:
            return
        try:
            with self._lock:
                job.status = "running"
            self._execute(job)
            with self._lock:
                job.status = "done"
                job.progress = 100
                job.finished_at = time.time()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                job.status = "error"
                job.error = f"{type(exc).__name__}: {exc}"
                job.finished_at = time.time()
                job.logs.append(
                    JobLog(timestamp=time.time(), message=f"ERRO: {job.error}")
                )
                job.logs.append(
                    JobLog(timestamp=time.time(), message=traceback.format_exc())
                )

    def _execute(self, job: Job) -> None:
        self._log(job, "Preparando roteiro...", progress=5)
        script: Script
        if job.script_text:
            script = script_from_text(job.script_text, title=job.title or job.theme)
        else:
            assert job.theme, "theme ou script_text obrigatório"
            script = generate_script(job.theme, duration_seconds=job.duration)
        final_title = job.title or script.title
        with self._lock:
            job.final_title = final_title
            job.caption = script.caption
            job.hashtags = script.hashtags
        self._log(job, f"Roteiro pronto: '{final_title}'", progress=20)

        self._log(job, f"Gerando narração ({job.voice})...", progress=30)
        audio_path = SETTINGS.cache_dir / f"narration_{job.id}.mp3"
        narration = synthesize(script.body, job.voice, audio_path)
        with self._lock:
            job.audio_duration = narration.duration
        self._log(
            job,
            f"Narração: {narration.duration:.1f}s · {len(narration.cues)} palavras",
            progress=50,
        )

        self._log(job, "Buscando fundos...", progress=60)
        bg_query = job.bg_query or job.theme or final_title
        assert bg_query is not None
        backgrounds = fetch_backgrounds(
            bg_query,
            count=max(3, int(narration.duration / 4)),
            prefer_videos=job.use_videos,
            local_dir=job.local_bg,
        )
        videos_count = sum(1 for c in backgrounds if c.is_video)
        self._log(
            job,
            f"Fundos: {len(backgrounds)} clipes ({videos_count} vídeos)",
            progress=70,
        )

        out_path = SETTINGS.output_dir / f"{_slugify(final_title)}_{job.id[:8]}.mp4"
        self._log(job, f"Renderizando vídeo → {out_path.name}", progress=75)
        build_video(
            narration=narration,
            backgrounds=backgrounds,
            out_path=out_path,
            title=final_title,
            music_path=job.music,
            words_per_caption=job.words_per_caption,
        )

        srt_path = out_path.with_suffix(".srt")
        srt_path.write_text(cues_to_srt(narration.cues), encoding="utf-8")

        meta_path = out_path.with_suffix(".json")
        import json

        meta_path.write_text(
            json.dumps(
                {
                    "title": final_title,
                    "caption": script.caption,
                    "hashtags": script.hashtags,
                    "duration": narration.duration,
                    "voice": job.voice,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        with self._lock:
            job.video_path = out_path
            job.srt_path = srt_path
            job.meta_path = meta_path
        self._log(job, "Concluído!", progress=100)


def _slugify(value: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in value)[:50].strip("_") or "video"


# Singleton compartilhado pelo app.
_default_manager: JobManager | None = None


def get_manager() -> JobManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = JobManager()
    return _default_manager


def new_job_id() -> str:
    return uuid.uuid4().hex
