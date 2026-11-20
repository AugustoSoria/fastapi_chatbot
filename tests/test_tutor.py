import pytest

from app.tutor import (
    ACCIONES,
    NO_ATTEMPT,
    NO_CLIP,
    ClipContext,
    _tokens,
    build_system_prompt,
    fallback_hint,
    is_locked,
    leaks,
    spoiler_words,
    word_diff,
)

ORIGINAL = "We need to talk about your future"


def ctx(**kwargs) -> ClipContext:
    base = {"clipId": "c1", "movie": "Back to the Future", "difficulty": 2, "duration": "0:05"}
    return ClipContext(**{**base, **kwargs})


# --- _tokens ---------------------------------------------------------------


def test_tokens_lowercases_and_strips_punctuation():
    assert _tokens("Hello, World!") == ["hello", "world"]


def test_tokens_expands_contractions():
    assert _tokens("I'm sure you can't") == ["i", "am", "sure", "you", "can", "not"]


def test_tokens_handles_curly_apostrophe():
    assert _tokens("Don’t") == ["do", "not"]


def test_tokens_empty():
    assert _tokens("") == []


# --- spoiler_words ---------------------------------------------------------


def test_spoiler_words_returns_wrong_words():
    assert spoiler_words(ORIGINAL, "We need to talk about your feature") == {"future"}


def test_spoiler_words_returns_missing_words():
    assert spoiler_words(ORIGINAL, "We need to talk about") == {"your", "future"}


def test_spoiler_words_ignores_stopwords():
    # "to" falta pero es stopword: nombrarla no revela nada
    assert spoiler_words(ORIGINAL, "We need talk about your future") == set()


def test_spoiler_words_excludes_words_the_user_wrote_elsewhere():
    # "need" está mal ubicada pero el usuario ya la escribió: no es un spoiler
    assert "need" not in spoiler_words(ORIGINAL, "We to talk need about your future")


def test_spoiler_words_perfect_attempt():
    assert spoiler_words(ORIGINAL, "we need to talk about your future.") == set()


# --- leaks -----------------------------------------------------------------


def test_leaks_detects_word_case_and_punctuation_insensitive():
    assert leaks("Pensá en el **FUTURE**!", {"future"})


def test_leaks_false_when_no_banned_word():
    assert not leaks("Prestá atención al final de la frase.", {"future"})


def test_leaks_does_not_match_substrings():
    # "future" es substring de "futures", pero no es la misma palabra
    assert not leaks("Pensá en tus futures", {"future"})


# --- word_diff -------------------------------------------------------------


def test_word_diff_replace():
    diff = word_diff(ORIGINAL, "We need to talk about your feature")
    assert diff == '- (final) el original dice "future" y el usuario escribió "feature"'


def test_word_diff_delete():
    diff = word_diff(ORIGINAL, "need to talk about your future")
    assert diff == '- (principio) al usuario le faltó "we"'


def test_word_diff_insert():
    diff = word_diff(ORIGINAL, "We need to talk about your future now")
    assert diff == '- (final) el usuario agregó "now", que no está en el original'


def test_word_diff_middle_position():
    diff = word_diff(ORIGINAL, "We need to walk about your future")
    assert "(medio)" in diff


def test_word_diff_identical():
    assert word_diff(ORIGINAL, ORIGINAL) == "- Ninguna: la transcripción coincide con el original."


# --- fallback_hint ---------------------------------------------------------


@pytest.mark.parametrize(
    "attempt",
    [
        "We need to talk about your feature",
        "We need to talk about",
        "We need to walk about your future",
        "",
    ],
)
def test_fallback_hint_never_reveals_spoilers(attempt):
    hidden = spoiler_words(ORIGINAL, attempt)
    assert not leaks(fallback_hint(ORIGINAL, attempt), hidden)


def test_fallback_hint_singular():
    hint = fallback_hint(ORIGINAL, "We need to talk about your feature")
    assert "al final (1 palabra)" in hint


@pytest.mark.parametrize(
    "attempt, expected",
    [
        ("need to talk about your future", "al principio (1 palabra)"),
        ("We need to walk about your future", "en el medio (1 palabra)"),
        ("We need to talk about your feature", "al final (1 palabra)"),
    ],
)
def test_fallback_hint_positions(attempt, expected):
    assert f"Fijate {expected}:" in fallback_hint(ORIGINAL, attempt)


def test_fallback_hint_plural():
    hint = fallback_hint(ORIGINAL, "We need to talk about")
    assert "al final (2 palabras)" in hint


def test_fallback_hint_perfect_attempt():
    assert "coincide" in fallback_hint(ORIGINAL, ORIGINAL)


@pytest.mark.xfail(strict=True, reason="Bug conocido: fallback_hint ignora las palabras agregadas (insert)")
def test_fallback_hint_extra_words_is_not_a_match():
    assert "coincide" not in fallback_hint(ORIGINAL, ORIGINAL + " right now")


# --- is_locked / build_system_prompt ---------------------------------------


@pytest.mark.parametrize(
    "context, locked",
    [
        (None, True),
        (ctx(unlocked=False, original=ORIGINAL), True),
        (ctx(unlocked=True, original=None), True),
        (ctx(unlocked=True, original=""), True),
        (ctx(unlocked=True, original=ORIGINAL), False),
    ],
)
def test_is_locked(context, locked):
    assert is_locked(context) is locked


def test_prompt_without_context():
    assert build_system_prompt(None, None).endswith(NO_CLIP)


@pytest.mark.parametrize("accion", [None, "pista", "explicar", "frase"])
def test_prompt_locked_clip_never_contains_original(accion):
    prompt = build_system_prompt(ctx(unlocked=False, original=ORIGINAL, attempt="We need"), accion)
    assert ORIGINAL not in prompt
    assert "TODAVÍA NO" in prompt


def test_prompt_locked_clip_defaults():
    prompt = build_system_prompt(ClipContext(clipId="c1"), None)
    assert '"una película"' in prompt
    assert "dificultad ?/3" in prompt


def test_prompt_unlocked_with_attempt():
    attempt = "We need to talk about your feature"
    prompt = build_system_prompt(ctx(unlocked=True, original=ORIGINAL, attempt=attempt, score=4), None)
    assert f"<<{ORIGINAL}>>" in prompt
    assert f"<<{attempt}>>" in prompt
    assert "4/5" in prompt
    assert word_diff(ORIGINAL, attempt) in prompt


def test_prompt_unlocked_attempt_score_zero():
    prompt = build_system_prompt(ctx(unlocked=True, original=ORIGINAL, attempt="Hello", score=0), None)
    assert "0/5" in prompt


def test_prompt_unlocked_attempt_without_score():
    prompt = build_system_prompt(ctx(unlocked=True, original=ORIGINAL, attempt="We need"), None)
    assert "?/5" in prompt


def test_prompt_unlocked_without_attempt():
    prompt = build_system_prompt(ctx(unlocked=True, original=ORIGINAL), None)
    assert f"<<{ORIGINAL}>>" in prompt
    assert NO_ATTEMPT in prompt


@pytest.mark.parametrize("accion", ["pista", "explicar", "frase"])
def test_prompt_appends_action(accion):
    prompt = build_system_prompt(ctx(unlocked=True, original=ORIGINAL), accion)
    assert prompt.endswith(ACCIONES[accion])
