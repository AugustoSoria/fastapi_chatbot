import logging
import os
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from groq import Groq
from pydantic import BaseModel, Field

from app.tutor import (
    LOCKED_REPLY,
    Accion,
    ClipContext,
    build_system_prompt,
    fallback_hint,
    is_locked,
    leaks,
    spoiler_words,
)

load_dotenv()
client = Groq(api_key=os.getenv("API_KEY"))
logger = logging.getLogger(__name__)

MODEL = "openai/gpt-oss-120b"
MAX_HISTORY = 20  # solo se mandan al modelo los últimos N mensajes


class Message(BaseModel):
    # Solo user/assistant: el cliente no puede inyectar mensajes "system"
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class AskRequest(BaseModel):
    historial: list[Message] = Field(max_length=100)
    context: Optional[ClipContext] = None
    accion: Optional[Accion] = None


class AskResponse(BaseModel):
    reply: str


router = APIRouter()


@router.post("/", response_model=AskResponse)
async def ask(request: AskRequest):
    if not request.historial:
        return AskResponse(reply="¿En qué puedo ayudarte?")

    # Las acciones que necesitan el texto del clip no llegan al modelo si está bloqueado
    if request.accion and is_locked(request.context):
        return AskResponse(reply=LOCKED_REPLY)

    system_prompt = build_system_prompt(request.context, request.accion)
    history = [m.model_dump() for m in request.historial[-MAX_HISTORY:]]

    if request.accion != "pista":
        return AskResponse(reply=await complete(system_prompt, history))

    # Pista: si el modelo revela palabras que el usuario no acertó, se reintenta una vez
    # prohibiéndolas explícitamente, y si vuelve a pasar se usa una pista armada sin LLM.
    ctx = request.context
    hidden = spoiler_words(ctx.original, ctx.attempt or "")
    answer = await complete(system_prompt, history)
    if leaks(answer, hidden):
        banned = ", ".join(sorted(hidden))
        answer = await complete(
            system_prompt + f"\n- PROHIBIDO usar estas palabras en tu respuesta: {banned}.", history
        )
    if leaks(answer, hidden):
        answer = fallback_hint(ctx.original, ctx.attempt or "")
    return AskResponse(reply=answer)


async def complete(system_prompt: str, history: list[dict]) -> str:
    try:
        response = await run_in_threadpool(
            client.chat.completions.create,
            model=MODEL,
            messages=[{"role": "system", "content": system_prompt}, *history],
            temperature=0.3,
            reasoning_effort="low",
            max_completion_tokens=700,
        )
    except Exception:
        logger.exception("Error llamando a Groq")
        raise HTTPException(status_code=502, detail="No se pudo obtener respuesta del modelo")

    answer = (response.choices[0].message.content or "").strip()
    if not answer:
        raise HTTPException(status_code=502, detail="El modelo devolvió una respuesta vacía")
    return answer
