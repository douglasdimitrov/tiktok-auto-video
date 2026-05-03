"""Testes de fumaça — verificam que módulos importam e funções básicas funcionam."""

from __future__ import annotations

from videogen.script import script_from_text
from videogen.tts import WordCue, cues_to_srt


def test_script_from_text_uses_first_sentence_as_title():
    s = script_from_text("Você sabia que o sol é grande. Outra frase.")
    assert s.title.startswith("Você sabia")
    assert "Outra frase" in s.body


def test_script_from_text_respects_explicit_title():
    s = script_from_text("Texto qualquer.", title="Meu título")
    assert s.title == "Meu título"


def test_cues_to_srt_groups_words():
    cues = [
        WordCue(text="oi", start=0.0, end=0.3),
        WordCue(text="mundo", start=0.3, end=0.7),
        WordCue(text="feliz", start=0.7, end=1.2),
        WordCue(text="hoje", start=1.2, end=1.6),
    ]
    srt = cues_to_srt(cues, words_per_cue=2)
    assert "oi mundo" in srt
    assert "feliz hoje" in srt
    assert "00:00:00,000 --> 00:00:00,700" in srt


def test_cues_to_srt_empty():
    assert cues_to_srt([]) == ""


def test_imports():
    import videogen.cli  # noqa: F401
    import videogen.config  # noqa: F401
    import videogen.script  # noqa: F401
    import videogen.stock  # noqa: F401
    import videogen.tts  # noqa: F401
    import videogen.upload  # noqa: F401
    import videogen.video  # noqa: F401
