"""Upload de vídeos no TikTok via cookies (não-oficial).

AVISO: O método não-oficial usa automação de browser e seus cookies de sessão. Funciona
mas tecnicamente viola os Termos de Uso do TikTok. Use por sua conta e risco. Para uso
em produção, registre um app oficial em https://developers.tiktok.com/ e use a Content
Posting API.
"""

from __future__ import annotations

from pathlib import Path


def upload_to_tiktok(
    video_path: Path,
    *,
    caption: str,
    cookies_file: Path,
    headless: bool = True,
) -> bool:
    """Sobe o vídeo no TikTok usando tiktok-uploader (Playwright) com cookies salvos.

    Como obter o `cookies.txt`:
    1. Faça login no https://tiktok.com pelo Chrome
    2. Instale a extensão "Get cookies.txt LOCALLY" (ou similar) e exporte cookies do
       domínio tiktok.com no formato Netscape para um arquivo `cookies.txt`
    3. Aponte --cookies para esse arquivo

    Retorna True em sucesso.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Vídeo não encontrado: {video_path}")
    if not cookies_file.exists():
        raise FileNotFoundError(
            f"Arquivo de cookies não encontrado: {cookies_file}\n"
            "Veja o README para instruções de como exportar."
        )

    from tiktok_uploader.upload import upload_video

    failed = upload_video(
        filename=str(video_path),
        description=caption,
        cookies=str(cookies_file),
        headless=headless,
    )

    if failed:
        print(f"[upload] Falha ao subir: {failed}")
        return False
    return True
