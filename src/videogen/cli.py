"""Interface de linha de comando do videogen."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import typer
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table

from videogen.config import SETTINGS
from videogen.script import generate_script, script_from_text
from videogen.stock import fetch_backgrounds
from videogen.tts import cues_to_srt, list_voices, synthesize
from videogen.upload import upload_to_tiktok
from videogen.video import build_video

app = typer.Typer(
    add_completion=False,
    help="Gerador de vídeos verticais com narração IA + uploader pro TikTok.",
)


def _slugify(value: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in value)[:50].strip("_") or "video"


def _create_video(
    *,
    theme: str | None,
    script_file: Path | None,
    title: str | None,
    output: Path | None,
    voice: str | None,
    duration: int,
    query: str | None,
    use_videos: bool,
    local_bg: Path | None,
    music: Path | None,
    words_per_caption: int,
) -> Path:
    """Lógica compartilhada por `create` e `auto`. Retorna o caminho do .mp4 gerado."""
    if not theme and not script_file:
        rprint("[red]Erro:[/] forneça --tema ou --script-file")
        raise typer.Exit(2)

    if script_file:
        body = Path(script_file).read_text(encoding="utf-8")
        script = script_from_text(body, title=title or theme)
    else:
        assert theme is not None
        rprint(Panel(f"Gerando roteiro para: [bold]{theme}[/]", style="cyan"))
        script = generate_script(theme, duration_seconds=duration)

    final_title = title or script.title
    rprint(Panel(script.body, title=f"[bold]{final_title}[/]", style="green"))

    voice_name = voice or SETTINGS.voice
    audio_path = SETTINGS.cache_dir / f"narration_{abs(hash(script.body)) % 10**10}.mp3"
    rprint(f"[cyan]Gerando narração com voz [bold]{voice_name}[/]...")
    narration = synthesize(script.body, voice_name, audio_path)
    rprint(f"  duração: {narration.duration:.2f}s, palavras: {len(narration.cues)}")

    rprint("[cyan]Buscando fundos...")
    bg_query = query or theme or final_title
    backgrounds = fetch_backgrounds(
        bg_query,
        count=max(3, int(narration.duration / 4)),
        prefer_videos=use_videos,
        local_dir=local_bg,
    )
    rprint(f"  {len(backgrounds)} clipes ({sum(1 for c in backgrounds if c.is_video)} vídeos)")

    if output is None:
        output = SETTINGS.output_dir / f"{_slugify(final_title)}.mp4"

    rprint(f"[cyan]Renderizando vídeo em [bold]{output}[/]...")
    build_video(
        narration=narration,
        backgrounds=backgrounds,
        out_path=output,
        title=final_title,
        music_path=music,
        words_per_caption=words_per_caption,
    )

    srt_path = output.with_suffix(".srt")
    srt_path.write_text(cues_to_srt(narration.cues), encoding="utf-8")

    meta_path = output.with_suffix(".json")
    meta_path.write_text(
        json.dumps(
            {
                "title": final_title,
                "caption": script.caption,
                "hashtags": script.hashtags,
                "duration": narration.duration,
                "voice": voice_name,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    rprint(f"[green]Pronto![/] vídeo: {output}")
    rprint(f"  legendas: {srt_path}")
    rprint(f"  metadata: {meta_path}")
    return output


@app.command()
def create(
    theme: str | None = typer.Option(
        None,
        "--tema",
        "-t",
        help="Tema do vídeo (ex: 'curiosidades sobre o espaço'). Roteiro gerado por IA.",
    ),
    script_file: Path | None = typer.Option(
        None,
        "--script-file",
        "-s",
        help="Arquivo de texto com o roteiro pronto (alternativa a --tema).",
    ),
    title: str | None = typer.Option(
        None, "--titulo", help="Título mostrado no início do vídeo."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Caminho do .mp4 de saída. Default: output/<slug>.mp4."
    ),
    voice: str | None = typer.Option(
        None, "--voice", "-v", help="Voz do edge-tts. Default do .env."
    ),
    duration: int = typer.Option(45, "--duracao", "-d", help="Duração alvo em segundos."),
    query: str | None = typer.Option(
        None, "--bg-query", help="Termo de busca pra fundos. Default: usa o tema."
    ),
    use_videos: bool = typer.Option(
        False, "--bg-videos", help="Usar vídeos de fundo do Pexels (em vez de imagens)."
    ),
    local_bg: Path | None = typer.Option(
        None, "--local-bg", help="Pasta local com imagens/vídeos pra usar de fundo."
    ),
    music: Path | None = typer.Option(
        None, "--music", help="Mp3 de música de fundo (volume baixo)."
    ),
    words_per_caption: int = typer.Option(3, "--wpc", help="Palavras por legenda na tela."),
) -> None:
    """Gera um vídeo vertical 9:16 com narração e legendas a partir de um tema ou roteiro."""
    _create_video(
        theme=theme,
        script_file=script_file,
        title=title,
        output=output,
        voice=voice,
        duration=duration,
        query=query,
        use_videos=use_videos,
        local_bg=local_bg,
        music=music,
        words_per_caption=words_per_caption,
    )


@app.command()
def upload(
    video: Path = typer.Argument(..., help="Caminho do .mp4 a subir."),
    caption: str | None = typer.Option(None, "--caption", "-c", help="Legenda do post."),
    cookies: Path = typer.Option(
        Path("cookies.txt"),
        "--cookies",
        help="Arquivo cookies.txt do TikTok no formato Netscape.",
    ),
    headless: bool = typer.Option(
        True, "--headless/--no-headless", help="Roda navegador headless."
    ),
):
    """Sobe um vídeo no TikTok usando cookies de sessão (método não-oficial)."""
    if caption is None:
        meta_path = video.with_suffix(".json")
        if meta_path.exists():
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            caption = data.get("caption") or data.get("title") or ""
        else:
            caption = ""

    rprint(f"[cyan]Subindo {video.name} no TikTok...")
    ok = upload_to_tiktok(
        video_path=video,
        caption=caption,
        cookies_file=cookies,
        headless=headless,
    )
    if ok:
        rprint("[green]Upload concluído.[/]")
    else:
        rprint("[red]Upload falhou — verifique cookies e tente --no-headless pra debugar.[/]")
        raise typer.Exit(1)


@app.command(name="auto")
def auto(
    theme: str = typer.Option(..., "--tema", "-t", help="Tema do vídeo."),
    cookies: Path = typer.Option(Path("cookies.txt"), "--cookies"),
    duration: int = typer.Option(45, "--duracao", "-d"),
    voice: str | None = typer.Option(None, "--voice", "-v"),
    use_videos: bool = typer.Option(
        False, "--bg-videos", help="Usar vídeos de fundo do Pexels."
    ),
    headless: bool = typer.Option(True, "--headless/--no-headless"),
) -> None:
    """Pipeline completo: gera vídeo a partir de tema + sobe no TikTok."""
    output = _create_video(
        theme=theme,
        script_file=None,
        title=None,
        output=None,
        voice=voice,
        duration=duration,
        query=None,
        use_videos=use_videos,
        local_bg=None,
        music=None,
        words_per_caption=3,
    )
    upload(video=output, caption=None, cookies=cookies, headless=headless)


@app.command()
def voices(
    language: str = typer.Option("pt", "--lang", help="Filtra por prefixo de locale."),
):
    """Lista vozes disponíveis no edge-tts."""
    items = asyncio.run(list_voices(language=language))
    table = Table("Nome", "Locale", "Gênero", "Categorias")
    for v in items:
        table.add_row(
            v["ShortName"],
            v["Locale"],
            v.get("Gender", ""),
            ", ".join(v.get("VoiceTag", {}).get("ContentCategories", [])),
        )
    rprint(table)


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", help="Endereço de bind do servidor."),
    port: int = typer.Option(8000, "--port", "-p", help="Porta HTTP."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload (dev)."),
) -> None:
    """Sobe a interface web (filtros bonitos no navegador) em http://host:port."""
    from videogen.web.server import run as run_web

    rprint(
        Panel(
            f"Interface web em [bold]http://{host}:{port}[/]\n"
            "Abra esse endereço no navegador para usar os filtros.",
            style="cyan",
        )
    )
    run_web(host=host, port=port, reload=reload)


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
