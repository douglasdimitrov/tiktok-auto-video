"""Servidor FastAPI da interface web do videogen."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from videogen.config import SETTINGS
from videogen.tts import list_voices
from videogen.web.jobs import Job, JobManager, get_manager, new_job_id

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def create_app(manager: JobManager | None = None) -> FastAPI:
    """Cria o app FastAPI. `manager` permite injetar JobManager nos testes."""
    app = FastAPI(
        title="videogen — gerador de vídeos verticais",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
    )

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    jobs = manager or get_manager()

    DEFAULT_VOICES = [
        {"id": "pt-BR-FranciscaNeural", "label": "Francisca (feminina, natural)"},
        {"id": "pt-BR-AntonioNeural", "label": "Antônio (masculina)"},
        {
            "id": "pt-BR-ThalitaMultilingualNeural",
            "label": "Thalita (feminina, multilíngue, mais expressiva)",
        },
    ]

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        gemini_ok = bool(SETTINGS.gemini_api_key)
        stock_provider = (
            "Pexels"
            if SETTINGS.pexels_api_key
            else ("Pixabay" if SETTINGS.pixabay_api_key else None)
        )
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "default_voice": SETTINGS.voice,
                "voices": DEFAULT_VOICES,
                "gemini_ok": gemini_ok,
                "stock_provider": stock_provider,
            },
        )

    @app.get("/api/voices")
    async def voices_api(lang: str = "pt"):
        try:
            items = await list_voices(language=lang)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                {"error": f"Não foi possível listar vozes: {exc}", "voices": DEFAULT_VOICES},
                status_code=200,
            )
        slim = [
            {
                "id": v["ShortName"],
                "label": f"{v['ShortName']} · {v.get('Gender', '')} · {v['Locale']}",
            }
            for v in items
        ]
        return {"voices": slim or DEFAULT_VOICES}

    @app.post("/api/jobs")
    async def create_job(
        tema: str | None = Form(None),
        script_text: str | None = Form(None),
        titulo: str | None = Form(None),
        voice: str | None = Form(None),
        duracao: int = Form(45),
        bg_query: str | None = Form(None),
        bg_videos: bool = Form(False),
        words_per_caption: int = Form(3),
    ):
        tema_clean = (tema or "").strip() or None
        script_clean = (script_text or "").strip() or None
        if not tema_clean and not script_clean:
            raise HTTPException(
                status_code=400,
                detail="Informe um tema OU um roteiro pronto.",
            )

        if not script_clean and not SETTINGS.gemini_api_key:
            raise HTTPException(
                status_code=400,
                detail=(
                    "GEMINI_API_KEY não configurado. Configure no .env ou cole um "
                    "roteiro pronto no campo 'Roteiro'."
                ),
            )

        job = Job(
            id=new_job_id(),
            theme=tema_clean,
            script_text=script_clean,
            title=(titulo or "").strip() or None,
            voice=(voice or SETTINGS.voice).strip(),
            duration=max(15, min(120, int(duracao))),
            bg_query=(bg_query or "").strip() or None,
            use_videos=bool(bg_videos),
            local_bg=None,
            music=None,
            words_per_caption=max(1, min(8, int(words_per_caption))),
        )
        jobs.submit(job)
        return {"id": job.id, "status": job.status}

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job não encontrado.")
        return _serialize_job(job)

    @app.get("/api/jobs")
    async def list_jobs(limit: int = 20):
        items = jobs.list()[:limit]
        return {"jobs": [_serialize_job(j, with_logs=False) for j in items]}

    @app.get("/api/jobs/{job_id}/video")
    async def download_video(job_id: str):
        job = jobs.get(job_id)
        if job is None or job.video_path is None or not job.video_path.exists():
            raise HTTPException(status_code=404, detail="Vídeo ainda não disponível.")
        return FileResponse(
            path=str(job.video_path),
            media_type="video/mp4",
            filename=job.video_path.name,
        )

    @app.get("/api/jobs/{job_id}/srt")
    async def download_srt(job_id: str):
        job = jobs.get(job_id)
        if job is None or job.srt_path is None or not job.srt_path.exists():
            raise HTTPException(status_code=404, detail="Legendas ainda não disponíveis.")
        return FileResponse(
            path=str(job.srt_path),
            media_type="text/plain",
            filename=job.srt_path.name,
        )

    @app.get("/health")
    async def health():
        return {
            "ok": True,
            "gemini": bool(SETTINGS.gemini_api_key),
            "pexels": bool(SETTINGS.pexels_api_key),
            "pixabay": bool(SETTINGS.pixabay_api_key),
        }

    return app


def _serialize_job(job: Job, *, with_logs: bool = True) -> dict:
    data: dict = {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "theme": job.theme,
        "title": job.final_title or job.title,
        "voice": job.voice,
        "duration": job.duration,
        "error": job.error,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "caption": job.caption,
        "hashtags": job.hashtags,
        "audio_duration": job.audio_duration,
        "video_url": f"/api/jobs/{job.id}/video" if job.video_path else None,
        "srt_url": f"/api/jobs/{job.id}/srt" if job.srt_path else None,
    }
    if with_logs:
        data["logs"] = [{"timestamp": log.timestamp, "message": log.message} for log in job.logs]
    return data


def run(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Atalho usado pelo comando `videogen web` na CLI."""
    import uvicorn

    if reload:
        uvicorn.run("videogen.web.server:create_app", host=host, port=port, factory=True, reload=True)
    else:
        uvicorn.run(create_app(), host=host, port=port)


# Garante que asyncio funciona quando o app é importado em contextos sem loop.
asyncio.get_event_loop_policy()
