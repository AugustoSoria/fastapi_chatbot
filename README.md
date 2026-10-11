# FastAPI Chatbot

Un chatbot simple construido con FastAPI y Groq API que responde preguntas utilizando el modelo GPT-OSS 20B.

## Características

- API REST con FastAPI
- Integración con Groq (Llama 3.3 70B)
- Soporte para historial de conversación
- Configuración CORS para frontend
- Manejo de errores básico

## Requisitos

- Python 3.8+
- Cuenta de Groq con API key

## Instalación

1. Clonar el repositorio:
```bash
git clone <repository-url>
cd fastapi_chatbot
```

2. Crear entorno virtual:
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

3. Instalar dependencias:
```bash
pip install fastapi uvicorn groq python-dotenv
```

## Configuración

1. Crear archivo `.env` en la carpeta `app/`:
```
API_KEY=tu_api_key_de_groq
```

2. Obtener tu API key desde [Groq Console](https://console.groq.com/)

## Uso

### Iniciar el servidor:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Endpoints:

#### GET `/`
Respuesta simple de prueba.

#### POST `/ask/`
Envía preguntas al chatbot.

**Request body:**
```json
{
  "historial": [
    {
      "role": "user", 
      "content": "Tu pregunta aquí"
    }
  ]
}
```

**Response:**
```json
"Respuesta del chatbot..."
```

## Estructura del Proyecto

```
fastapi_chatbot/
├── app/
│   ├── main.py          # Aplicación FastAPI principal
│   ├── routes/
│   │   └── ask_routes.py # Rutas del chatbot
│   └── .env             # Variables de entorno
├── .gitignore           # Archivos ignorados por Git
└── README.md           # Este archivo
```

## Notas

- El origen CORS está configurado para `http://127.0.0.1:61039` - ajustar según sea necesario
- El modelo utilizado es `openai/gpt-oss-20b`
- La temperatura está configurada en 0.1 para respuestas más consistentes
