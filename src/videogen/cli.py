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
):
    """Gera um vídeo vertical 9:16 com narração e legendas a partir de um tema ou roteiro."""
    if not theme and not script_file:
        rprint("[red]Erro:[/] forneça --tema ou --script-file")
        raise typer.Exit(2)

    if theme and not script_file:
        rprint(Panel(f"Gerando roteiro para: [bold]{theme}[/]", style="cyan"))
        script = generate_script(theme, duration_seconds=duration)
    else:
        assert script_file is not None
        body = Path(script_file).read_text(encoding="utf-8")
        script = script_from_text(body, title=title or theme)

    title = title or script.title
    rprint(Panel(script.body, title=f"[bold]{title}[/]", style="green"))

    voice_name = voice or SETTINGS.voice
    audio_path = SETTINGS.cache_dir / f"narration_{abs(hash(script.body)) % 10**10}.mp3"
    rprint(f"[cyan]Gerando narração com voz [bold]{voice_name}[/]...")
    narration = synthesize(script.body, voice_name, audio_path)
    rprint(f"  duração: {narration.duration:.2f}s, palavras: {len(narration.cues)}")

    rprint("[cyan]Buscando fundos...")
    bg_query = query or theme or title
    backgrounds = fetch_backgrounds(
        bg_query,
        count=max(3, int(narration.duration / 4)),
        prefer_videos=use_videos,
        local_dir=local_bg,
    )
    rprint(f"  {len(backgrounds)} clipes ({sum(1 for c in backgrounds if c.is_video)} vídeos)")

    if output is None:
        slug = "".join(c if c.isalnum() else "_" for c in (title or "video"))[:50].strip("_")
        output = SETTINGS.output_dir / f"{slug}.mp4"

    rprint(f"[cyan]Renderizando vídeo em [bold]{output}[/]...")
    build_video(
        narration=narration,
        backgrounds=backgrounds,
        out_path=output,
        title=title,
        music_path=music,
        words_per_caption=words_per_caption,
    )

    srt_path = output.with_suffix(".srt")
    srt_path.write_text(cues_to_srt(narration.cues), encoding="utf-8")

    meta_path = output.with_suffix(".json")
    meta_path.write_text(
        json.dumps(
            {
                "title": title,
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
    headless: bool = typer.Option(True, "--headless/--no-headless"),
):
    """Pipeline completo: gera vídeo a partir de tema + sobe no TikTok."""
    create(
        theme=theme,
        script_file=None,
        title=None,
        output=None,
        voice=voice,
        duration=duration,
        query=None,
        use_videos=False,
        local_bg=None,
        music=None,
        words_per_caption=3,
    )

    slug = "".join(c if c.isalnum() else "_" for c in theme)[:50].strip("_")
    output = SETTINGS.output_dir / f"{slug}.mp4"
    if not output.exists():
        rprint(f"[red]Não encontrei o vídeo gerado em {output}[/]")
        raise typer.Exit(1)
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


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
