"""Prompts del tutor de inglés (Clippy) para la app CineEars.

La regla anti-spoiler se aplica en dos capas:
1. El texto original del clip solo llega al modelo si el clip está "desbloqueado"
   (el usuario ya hizo un intento o abrió el transcript).
2. Las acciones que necesitan el texto se responden sin LLM si el clip está bloqueado.
"""

import difflib
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

Accion = Literal["pista", "explicar", "frase"]


class ClipContext(BaseModel):
    clipId: str = Field(max_length=100)
    movie: str = Field(default="", max_length=200)
    difficulty: Optional[int] = Field(default=None, ge=1, le=3)
    duration: str = Field(default="", max_length=20)
    unlocked: bool = False
    original: Optional[str] = Field(default=None, max_length=1000)
    attempt: Optional[str] = Field(default=None, max_length=1000)
    score: Optional[int] = Field(default=None, ge=0, le=5)


BASE_PROMPT = """Eres Clippy, el tutor de inglés de CineEars, una app para practicar comprensión auditiva \
(listening) con clips cortos de películas. El usuario mira un clip, escribe lo que escucha y un evaluador \
automático le da un puntaje de 0 a 5 (5 = perfecto).

Tu trabajo:
- Ayudar a entender por qué ciertas partes son difíciles de oír: connected speech, reducciones \
(gonna, wanna, gotta, kinda), contracciones, linking entre palabras, elisión de sonidos, vocales débiles \
(schwa), velocidad, acentos.
- Explicar el significado de frases, modismos, expresiones coloquiales y gramática de los clips.
- Dar consejos prácticos de escucha.

Estilo:
- Respondé en el idioma del usuario (por defecto, español). Las palabras en inglés quedan en inglés.
- Hablale directamente al usuario en segunda persona ("escribiste", "te faltó"), nunca "el usuario".
- Sé breve, amable y concreto: como máximo 120 palabras, salvo que el usuario pida más detalle. \
Es un chat chico al lado de la pantalla: las listas tienen como máximo 3 puntos.
- Formato: texto plano con saltos de línea. Usá **negrita** solo para resaltar palabras o frases en inglés. \
No uses títulos, tablas, separadores (---) ni bloques de código.
- No uses transcripciones fonéticas (IPA). Para mostrar cómo suena algo, usá una aproximación simple \
con letras comunes, por ejemplo: "going to" suena como **"gonna"**.
- Si te preguntan algo que no tiene que ver con aprender inglés o con la app, redirigí amablemente la charla.
"""

NO_CLIP = "\nContexto: el usuario está viendo la lista de clips y no tiene ningún clip abierto."

LOCKED_CLIP = """
Contexto: el usuario tiene abierto un clip de "{movie}" (dificultad {difficulty}/3, duración {duration}).
El usuario TODAVÍA NO intentó transcribir este clip y vos NO conocés su texto. Si pregunta qué dice el clip, \
qué significa la frase o pide la respuesta, decile que primero intente transcribirlo y que después lo ayudás \
con gusto. Podés dar consejos generales de escucha."""

UNLOCKED_CLIP = """
Contexto: el usuario tiene abierto un clip de "{movie}" (dificultad {difficulty}/3, duración {duration}).
Texto original del clip: <<{original}>>"""

ATTEMPT = """
Lo que escribió el usuario: <<{attempt}>>
Puntaje del evaluador: {score}/5
Diferencias palabra por palabra (calculadas automáticamente, ignorando mayúsculas y puntuación; \
usalas como fuente de verdad sobre dónde se equivocó):
{diff}"""

NO_ATTEMPT = "\nEl usuario no hizo ningún intento: vio el transcript directamente."

ACCIONES: dict[str, str] = {
    "pista": """
TAREA: el usuario pidió una PISTA para volver a intentarlo.
- NO escribas el texto original, ni las palabras que le faltaron o escribió mal, ni sus traducciones, \
ni su transcripción fonética (IPA), ni las deletrees, ni des sinónimos o rimas que las delaten.
- Basate en las diferencias calculadas. Las palabras que el usuario escribió bien no son el problema: \
no las menciones.
- Decí en qué parte está el problema (al principio, en el medio o al final, y cuántas palabras son, más o menos) \
y qué fenómeno de pronunciación lo hace difícil.
- Sugerile escuchar de nuevo esa parte. Como máximo 3 oraciones.""",
    "explicar": """
TAREA: explicá qué pasó en el intento del usuario comparándolo con el texto original.
- Hablá solo de las diferencias de la lista calculada: mayúsculas, puntuación y guiones no son errores.
- Para cada diferencia importante (máximo 3): qué dice el original, qué escribiste y por qué en el audio \
se oye parecido a lo que escribiste (el fenómeno de pronunciación: linking, reducción, elisión, etc.). \
Si una parte simplemente faltó, decí que faltó y qué la hace fácil de perder. Una o dos oraciones por diferencia.
- Si el intento es perfecto, felicitalo en una oración.
- Terminá ofreciendo explicar el significado de la frase.""",
    "frase": """
TAREA: explicá la frase del clip.
- Dá una traducción natural al español.
- Explicá los modismos, expresiones coloquiales o la gramática interesante que tenga, y en qué situación se usa.
- Si la frase no tiene nada especial, decilo en una oración y dá solo la traducción.""",
}

LOCKED_REPLY = (
    "¡Todavía no! 😉 Primero intentá transcribir el clip y, cuando tengas tu puntaje, te ayudo con gusto."
)


_CONTRACTIONS = {
    "i'm": "i am", "you're": "you are", "we're": "we are", "they're": "they are",
    "it's": "it is", "that's": "that is", "what's": "what is", "there's": "there is",
    "he's": "he is", "she's": "she is", "let's": "let us", "i've": "i have",
    "you've": "you have", "we've": "we have", "i'll": "i will", "you'll": "you will",
    "we'll": "we will", "i'd": "i would", "you'd": "you would", "don't": "do not",
    "doesn't": "does not", "didn't": "did not", "can't": "can not", "cannot": "can not",
    "won't": "will not", "isn't": "is not", "aren't": "are not", "wasn't": "was not",
    "weren't": "were not", "haven't": "have not", "hasn't": "has not",
    "couldn't": "could not", "shouldn't": "should not", "wouldn't": "would not",
}


def _tokens(text: str) -> list[str]:
    text = text.lower().replace("’", "'")
    words = re.findall(r"[a-z0-9']+", text)
    out: list[str] = []
    for w in words:
        w = w.strip("'")
        if w:
            out.extend(_CONTRACTIONS.get(w, w).split())
    return out


def _opcodes(a: list[str], b: list[str]):
    return difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()


# Palabras tan comunes que mencionarlas en una pista no revela nada
_STOPWORDS = {
    "a", "an", "the", "to", "of", "in", "on", "at", "for", "and", "or", "but", "is", "are",
    "am", "be", "it", "i", "you", "we", "he", "she", "they", "do", "not", "oh", "so",
}


def spoiler_words(original: str, attempt: str) -> set[str]:
    """Palabras del original que el usuario no escribió bien (las que una pista no puede revelar)."""
    a, b = _tokens(original), _tokens(attempt)
    hidden = {w for op, i1, i2, _, _ in _opcodes(a, b) if op in ("replace", "delete") for w in a[i1:i2]}
    return hidden - _STOPWORDS - set(b)


def leaks(reply: str, words: set[str]) -> bool:
    return bool(words & set(_tokens(reply)))


def fallback_hint(original: str, attempt: str) -> str:
    """Pista armada sin LLM, para cuando el modelo insiste en revelar palabras."""
    a, b = _tokens(original), _tokens(attempt)
    parts = []
    for op, i1, i2, _, _ in _opcodes(a, b):
        if op in ("replace", "delete"):
            pos = "al principio" if i1 < len(a) / 3 else "en el medio" if i1 < 2 * len(a) / 3 else "al final"
            n = i2 - i1
            parts.append(f"{pos} ({n} palabra{'s' if n > 1 else ''})")
    if not parts:
        return "¡Tu transcripción ya coincide con el original! 🎉"
    return (
        f"Fijate {', '.join(parts)}: ahí hay algo que no coincide. "
        "Volvé a escuchar esa parte prestando atención a cómo se pegan las palabras entre sí."
    )


def word_diff(original: str, attempt: str) -> str:
    """Describe en líneas legibles qué palabras faltan, sobran o están mal."""
    a, b = _tokens(original), _tokens(attempt)
    lines: list[str] = []
    for op, i1, i2, j1, j2 in _opcodes(a, b):
        if op == "equal":
            continue
        pos = "principio" if i1 < len(a) / 3 else "medio" if i1 < 2 * len(a) / 3 else "final"
        orig, user = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        if op == "replace":
            lines.append(f'- ({pos}) el original dice "{orig}" y el usuario escribió "{user}"')
        elif op == "delete":
            lines.append(f'- ({pos}) al usuario le faltó "{orig}"')
        else:
            lines.append(f'- ({pos}) el usuario agregó "{user}", que no está en el original')
    return "\n".join(lines) or "- Ninguna: la transcripción coincide con el original."


def build_system_prompt(context: Optional[ClipContext], accion: Optional[Accion]) -> str:
    if context is None:
        return BASE_PROMPT + NO_CLIP

    fields = {
        "movie": context.movie or "una película",
        "difficulty": context.difficulty or "?",
        "duration": context.duration or "?",
    }

    if not (context.unlocked and context.original):
        return BASE_PROMPT + LOCKED_CLIP.format(**fields)

    prompt = BASE_PROMPT + UNLOCKED_CLIP.format(**fields, original=context.original)
    if context.attempt:
        score = context.score if context.score is not None else "?"
        diff = word_diff(context.original, context.attempt)
        prompt += ATTEMPT.format(attempt=context.attempt, score=score, diff=diff)
    else:
        prompt += NO_ATTEMPT

    if accion:
        prompt += ACCIONES[accion]
    return prompt


def is_locked(context: Optional[ClipContext]) -> bool:
    return context is None or not (context.unlocked and context.original)
