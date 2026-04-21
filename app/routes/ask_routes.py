from fastapi import APIRouter
from pydantic import BaseModel

from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("API_KEY"))

class Message(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    historial: list[Message]

router = APIRouter()

model="llama-3.3-70b-versatile"
system_prompt = """
    Eres un asistente útil que responde preguntas basándose en el contexto proporcionado.
    Sé amigable, claro y conciso.
    Si no sabes algo, admítelo.
    Responde en el lenguaje que el usuario use.
"""
primer_prompt = {"role": "system", "content": system_prompt}
historial = [primer_prompt]

@router.post("/")
async def ask(request: AskRequest):
    if(len(request.historial) == 0):
        assistant_message = {"role": "assistant", "content": "En qué puedo ayudarte?"}
        return assistant_message
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=request.historial,
            temperature=0.1
        )

        print("---------- response ----------")
        answer = response.choices[0].message.content
        print(answer)
        return answer
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}