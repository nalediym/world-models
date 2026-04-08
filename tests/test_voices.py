from __future__ import annotations

from datetime import datetime

from life_world_model.pipeline.voices import VOICES, Voice, get_voice
from life_world_model.pipeline.generator import build_prompt, build_system_prompt
from life_world_model.types import LifeState


# ---------------------------------------------------------------------------
# Voice registry
# ---------------------------------------------------------------------------

EXPECTED_VOICES = {"tolkien", "clinical", "casual", "poetic", "coach", "data"}


def test_all_expected_voices_exist() -> None:
    assert set(VOICES.keys()) == EXPECTED_VOICES


def test_each_voice_has_required_fields() -> None:
    for name, voice in VOICES.items():
        assert isinstance(voice, Voice), f"{name} is not a Voice"
        assert voice.name == name
        assert len(voice.system_prompt) > 0
        assert len(voice.style_instructions) > 0
        lo, hi = voice.word_range
        assert 0 < lo < hi, f"{name} word_range invalid: {voice.word_range}"


def test_voice_is_frozen() -> None:
    v = get_voice("tolkien")
    try:
        v.name = "hacked"  # type: ignore[misc]
        assert False, "Voice should be frozen"
    except AttributeError:
        pass


# ---------------------------------------------------------------------------
# get_voice
# ---------------------------------------------------------------------------

def test_get_voice_returns_matching_voice() -> None:
    for name in EXPECTED_VOICES:
        voice = get_voice(name)
        assert voice.name == name


def test_get_voice_falls_back_to_tolkien_for_unknown() -> None:
    voice = get_voice("nonexistent_voice_xyz")
    assert voice.name == "tolkien"


def test_get_voice_falls_back_for_empty_string() -> None:
    voice = get_voice("")
    assert voice.name == "tolkien"


# ---------------------------------------------------------------------------
# build_prompt uses voice
# ---------------------------------------------------------------------------

def _sample_states() -> list[LifeState]:
    return [
        LifeState(
            datetime.fromisoformat("2026-04-06T09:00:00"),
            "coding",
            "github.com",
            "github.com",
            3,
            0.9,
        ),
    ]


def test_build_prompt_uses_voice_name() -> None:
    voice = get_voice("clinical")
    prompt = build_prompt(_sample_states(), voice)
    assert "'clinical'" in prompt


def test_build_prompt_defaults_to_tolkien() -> None:
    prompt = build_prompt(_sample_states())
    assert "'tolkien'" in prompt


def test_build_prompt_still_warns_against_hallucination() -> None:
    voice = get_voice("casual")
    prompt = build_prompt(_sample_states(), voice)
    assert "Do not invent major activities" in prompt


# ---------------------------------------------------------------------------
# build_system_prompt uses voice
# ---------------------------------------------------------------------------

def test_build_system_prompt_includes_voice_system_prompt() -> None:
    voice = get_voice("poetic")
    system = build_system_prompt(voice)
    assert "poet" in system.lower()


def test_build_system_prompt_includes_word_range() -> None:
    voice = get_voice("data")
    system = build_system_prompt(voice)
    lo, hi = voice.word_range
    assert str(lo) in system
    assert str(hi) in system


def test_build_system_prompt_includes_style_instructions() -> None:
    voice = get_voice("coach")
    system = build_system_prompt(voice)
    assert voice.style_instructions in system


def test_build_system_prompt_defaults_to_tolkien() -> None:
    system = build_system_prompt()
    assert "Tolkien" in system


# ---------------------------------------------------------------------------
# CLI --voice flag parsing
# ---------------------------------------------------------------------------

def test_cli_generate_parser_accepts_voice_flag() -> None:
    from life_world_model.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["generate", "--date", "2026-04-06", "--voice", "clinical"])
    assert args.voice == "clinical"


def test_cli_run_parser_accepts_voice_flag() -> None:
    from life_world_model.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["run", "--date", "2026-04-06", "--demo", "--voice", "casual"])
    assert args.voice == "casual"


def test_cli_generate_voice_defaults_to_none() -> None:
    from life_world_model.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["generate", "--date", "2026-04-06"])
    assert args.voice is None


def test_cli_voices_command_exists() -> None:
    from life_world_model.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["voices"])
    assert args.command == "voices"
