"""Geração de roteiros (scripts) para vídeos curtos de curiosidades / stories.

Usa Google Gemini 2.5 Flash (grátis no AI Studio).
Get API key: https://aistudio.google.com/app/apikey
"""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass

from videogen.config import SETTINGS

DEFAULT_MODEL = "gemini-2.5-flash"

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


def generate_script(
    theme: str, *, duration_seconds: int = 45, model: str = DEFAULT_MODEL
) -> Script:
    """Usa Google Gemini para gerar roteiro a partir de um tema."""
    if not SETTINGS.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não definido. Pegue uma chave grátis em "
            "https://aistudio.google.com/app/apikey e configure em .env, "
            "ou use --script-file para fornecer o texto manualmente."
        )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=SETTINGS.gemini_api_key)

    user_prompt = (
        f"Tema: {theme}\n"
        f"Duração alvo: ~{duration_seconds} segundos (~{duration_seconds * 2.5:.0f} palavras)."
    )

    response_schema = {
        "type": "object",
        "properties": {
            "titulo": {
                "type": "string",
                "description": "Título chamativo até 80 caracteres.",
            },
            "roteiro": {
                "type": "string",
                "description": "Roteiro completo em parágrafos curtos, sem markdown.",
            },
            "hashtags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "5 hashtags em português, sem o caractere '#'.",
            },
        },
        "required": ["titulo", "roteiro", "hashtags"],
    }

    resp = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.85,
            response_mime_type="application/json",
            response_schema=response_schema,
        ),
    )
    raw = (resp.text or "").strip()
    if not raw:
        raise RuntimeError("Gemini retornou resposta vazia.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: parser de texto livre se Gemini ignorar JSON.
        return _parse_script_legacy(raw, fallback_title=theme)

    title = str(data.get("titulo") or theme).strip()[:80]
    body = str(data.get("roteiro") or "").strip()
    raw_tags = data.get("hashtags") or []
    hashtags = [str(t).lstrip("#").strip() for t in raw_tags if str(t).strip()]
    return Script(title=title, body=body, hashtags=hashtags)


def script_from_text(
    body: str, *, title: str | None = None, hashtags: list[str] | None = None
) -> Script:
    return Script(
        title=title or body.split(".")[0][:80].strip(),
        body=body.strip(),
        hashtags=hashtags or [],
    )


def _parse_script_legacy(raw: str, fallback_title: str) -> Script:
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
