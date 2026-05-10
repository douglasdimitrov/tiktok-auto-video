"""Interface web (FastAPI) que expõe o pipeline de geração de vídeo via navegador."""

from videogen.web.server import create_app, run

__all__ = ["create_app", "run"]
