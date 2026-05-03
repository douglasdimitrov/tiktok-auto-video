# tiktok-auto-video

Gerador de vídeos verticais (9:16) com **narração de IA**, **legendas estilo TikTok** e
**upload automático no TikTok**.

Use pra criar canais de stories / curiosidades automaticamente:

```bash
videogen auto --tema "5 curiosidades sobre o universo"
```

> **Aviso:** o upload usa um método **não-oficial** que automatiza um navegador com seus
> cookies de sessão do TikTok. Funciona, mas tecnicamente viola os Termos de Uso do
> TikTok — use por sua conta e risco. Para uso em produção, registre um app em
> [developers.tiktok.com](https://developers.tiktok.com/) e use a [Content Posting API](https://developers.tiktok.com/doc/content-posting-api-get-started).

## O que ele faz

1. **Gera o roteiro** a partir de um tema usando Google Gemini 2.0 Flash (grátis,
   ~1500 req/dia), com gancho forte, frases curtas e CTA — ou recebe um roteiro
   pronto via `--script-file`.
2. **Narra** o roteiro com `edge-tts` (vozes neurais grátis da Microsoft em PT-BR).
3. **Busca fundos** no Pexels/Pixabay (vídeos verticais ou fotos) ou usa imagens
   suas de uma pasta local. Sem API key, gera fundos gradiente como fallback.
4. **Monta o vídeo** 9:16 com efeito Ken Burns nas imagens, legendas sincronizadas
   palavra-a-palavra estilo TikTok, e opcional música de fundo.
5. **Sobe no TikTok** usando `tiktok-uploader` (Playwright + cookies).

## Setup

### 1. Pré-requisitos

- **Python 3.10+**
- **ffmpeg** (`sudo apt install ffmpeg` no Ubuntu, `brew install ffmpeg` no macOS)

### 2. Instalação

```bash
git clone <este-repo>
cd tiktok-auto-video

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
playwright install chromium  # necessário pra upload no TikTok
```

### 3. Configuração

Copie `.env.example` para `.env` e preencha:

```bash
cp .env.example .env
```

| Variável | Para quê | Como obter |
|---|---|---|
| `GEMINI_API_KEY` | Gerar roteiros automaticamente (grátis) | https://aistudio.google.com/app/apikey |
| `PEXELS_API_KEY` | Imagens/vídeos de fundo | https://www.pexels.com/api/ (grátis) |
| `PIXABAY_API_KEY` | Alternativa ao Pexels | https://pixabay.com/api/docs/ (grátis) |

Todas as chaves são opcionais — sem elas o app ainda funciona, mas com
limitações (você fornece o roteiro manualmente / fundos gradiente).

### 4. Cookies do TikTok (pro upload automático)

1. Faça login em [tiktok.com](https://www.tiktok.com) no Chrome
2. Instale a extensão **"Get cookies.txt LOCALLY"** ([link](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc))
3. Abra `tiktok.com`, clique na extensão, exporte cookies do site no formato
   **Netscape** e salve como `cookies.txt` na raiz do projeto

## Uso

### Gerar vídeo + subir tudo automaticamente

```bash
videogen auto --tema "5 mistérios não resolvidos do oceano"
```

### Apenas gerar o vídeo (revisar antes de subir)

```bash
# Tema → IA gera o roteiro
videogen create --tema "Curiosidades chocantes sobre o cérebro"

# Ou: roteiro próprio
videogen create --script-file meu_roteiro.txt --titulo "5 fatos surpreendentes"
```

Saída: `output/<slug>.mp4` + `<slug>.srt` (legendas) + `<slug>.json` (metadata).

### Subir um vídeo já gerado

```bash
videogen upload output/meu_video.mp4 --caption "Legenda aqui #curiosidades"
```

Se o `.mp4` tem um `.json` ao lado (gerado por `create`), a caption é pega de lá.

### Listar vozes disponíveis (PT-BR)

```bash
videogen voices --lang pt-BR
```

Boas opções pra PT-BR:
- `pt-BR-FranciscaNeural` (feminina, padrão, natural)
- `pt-BR-AntonioNeural` (masculina)
- `pt-BR-ThalitaMultilingualNeural` (feminina multilíngue, mais expressiva)

### Opções úteis

```bash
videogen create \
  --tema "Como o ouro é formado" \
  --duracao 50 \
  --voice pt-BR-AntonioNeural \
  --bg-videos \
  --bg-query "gold mining"          # busca fundos em inglês (Pexels tem mais resultados)
  --music assets/lofi.mp3 \
  --wpc 4
```

```bash
# Use suas próprias imagens em vez do Pexels:
videogen create --tema "..." --local-bg ./minhas_imagens/
```

## Estrutura do projeto

```
src/videogen/
├── cli.py        # Interface CLI (typer)
├── config.py     # Carrega .env
├── script.py     # Gera roteiro com Google Gemini
├── tts.py        # Narração com edge-tts + word boundaries
├── stock.py      # Pexels / Pixabay / fallback gradiente
├── video.py      # Monta vídeo 9:16 com moviepy
└── upload.py     # Upload TikTok via tiktok-uploader
```

## Disclaimer legal

- **Direitos autorais**: imagens/vídeos do Pexels/Pixabay são livres pra uso comercial.
  Música de fundo: use sons livres de royalties (a TikTok detecta áudio com copyright).
- **TikTok ToS**: o método de upload via cookies não é oficial. Sua conta pode ser
  suspensa se detectarem automação. Use moderadamente, intercale com posts manuais,
  e considere migrar pra API oficial quando o canal crescer.
- **Gemini**: você é responsável pelo conteúdo gerado. Revise antes de postar.
  A cota grátis do Google AI Studio inclui treinamento dos modelos com seus
  prompts — não use dados sensíveis. Pra uso comercial sem isso, ative billing.

## Licença

MIT
