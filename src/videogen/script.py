"""Geração de roteiros (scripts) para vídeos curtos de curiosidades / stories."""

from __future__ import annotations

import textwrap
from dataclasses import dataclass

from videogen.config import SETTINGS

SYSTEM_PROMPT = textwrap.dedent(
    """
    Você é um roteirista de vídeos curtos para TikTok / Reels / Shorts em português brasileiro.
    Seu trabalho é escrever roteiros de 30 a 60 segundos com tom envolvente, ritmo rápido,
    voz coloquial e que prendem o espectador desde o primeiro segundo.

    Regras:
    - Comece SEMPRE com um gancho forte na primeira frase (curiosidade chocante, pergunta, fato bizarro).
    - Use frases curtas (máx. 12 palavras), uma ideia por frase.
    - Não use markdown, emojis, hashtags ou referências a fontes.
    - Não fale "olá pessoal" nem se apresente. Vá direto ao conteúdo.
    - Termine com um CTA simples: peça curtida, comentário ou seguir para mais.
    - O texto será lido por uma narração TTS, então escreva como fala, não como texto escrito.
    - Não use parênteses, asteriscos, marcadores. Só texto corrido em parágrafos curtos.

    Devolva APENAS o roteiro, sem nenhum texto adicional.
    """
).strip()


@dataclass
class Script:
    title: str
    body: str
    hashtags: list[str]

    @property
    def caption(self) -> str:
        tags = " ".join(f"#{t.lstrip('#')}" for t in self.hashtags) if self.hashtags else ""
        return f"{self.title}\n\n{tags}".strip()


def generate_script(theme: str, *, duration_seconds: int = 45) -> Script:
    """Usa OpenAI para gerar roteiro a partir de um tema."""
    if not SETTINGS.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY não definido. Configure em .env ou use --script-file para fornecer "
            "o texto manualmente."
        )

    from openai import OpenAI

    client = OpenAI(api_key=SETTINGS.openai_api_key)

    user_prompt = (
        f"Tema: {theme}\n"
        f"Duração alvo: ~{duration_seconds} segundos (~{duration_seconds * 2.5:.0f} palavras).\n\n"
        "Escreva o roteiro completo. Depois, em uma nova linha, escreva 'TITULO:' "
        "seguido por um título chamativo de até 80 caracteres. Em outra linha, "
        "escreva 'HASHTAGS:' seguido por 5 hashtags relevantes em português separadas por espaço."
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.85,
    )
    raw = resp.choices[0].message.content or ""
    return _parse_script(raw, fallback_title=theme)


def script_from_text(
    body: str, *, title: str | None = None, hashtags: list[str] | None = None
) -> Script:
    return Script(
        title=title or body.split(".")[0][:80].strip(),
        body=body.strip(),
        hashtags=hashtags or [],
    )


def _parse_script(raw: str, fallback_title: str) -> Script:
    body_lines: list[str] = []
    title = fallback_title
    hashtags: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("TITULO:") or stripped.upper().startswith("TÍTULO:"):
            title = stripped.split(":", 1)[1].strip() or title
        elif stripped.upper().startswith("HASHTAGS:"):
            tags_text = stripped.split(":", 1)[1].strip()
            hashtags = [t.lstrip("#") for t in tags_text.split() if t.strip()]
        else:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()
    return Script(title=title[:80], body=body, hashtags=hashtags)
