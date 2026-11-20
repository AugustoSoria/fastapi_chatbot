# FastAPI Chatbot

Backend de **Clippy**, el tutor de inglés de CineEars. Construido con FastAPI y Groq, usa el modelo `openai/gpt-oss-120b`.

## Características

- Tutor con contexto del clip: explica errores de transcripción (connected speech, reducciones, linking), da pistas y explica frases y modismos
- Anti-spoiler: el texto del clip solo llega al modelo cuando el usuario ya lo intentó o abrió el transcript, y las pistas se filtran para que no revelen las palabras que el usuario no acertó
- Diff palabra por palabra (difflib) entre el original y el intento, para que el modelo no tenga que adivinar dónde estuvo el error
- Validación del request: solo roles `user`/`assistant`, largo máximo por mensaje y se usan los últimos 20 mensajes
- Errores con status HTTP real (502 si falla el modelo)

## Requisitos

- Python 3.8+
- Cuenta de Groq con API key

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

## Configuración

Crear `app/.env`:
```
API_KEY=tu_api_key_de_groq
ALLOWED_ORIGINS=
```

## Uso

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### POST `/ask/`

**Request:**
```json
{
  "historial": [{ "role": "user", "content": "Dame una pista" }],
  "context": {
    "clipId": "abdca312-...",
    "movie": "Monsters, Inc. (2001)",
    "difficulty": 2,
    "duration": "3.5s",
    "unlocked": true,
    "original": "-Can we get an autograph? -Oh, sure. No problem.",
    "attempt": "can we get a photograph oh sure",
    "score": 2
  },
  "accion": "pista"
}
```

- `context` (opcional): clip abierto. `original` solo se envía con `unlocked: true`. `attempt` y `score` (0-5) solo si hubo intento.
- `accion` (opcional): `pista` | `explicar` | `frase`. Si el clip está bloqueado, devuelve un mensaje fijo sin llamar al modelo.

**Response:**
```json
{ "reply": "Respuesta del tutor..." }
```

## Estructura

```
fastapi_chatbot/
├── app/
│   ├── main.py              # App FastAPI + CORS
│   ├── tutor.py             # Prompts, diff de palabras y reglas anti-spoiler
│   ├── routes/
│   │   └── ask_routes.py    # Endpoint /ask
│   └── .env
├── requirements.txt
└── README.md
```
