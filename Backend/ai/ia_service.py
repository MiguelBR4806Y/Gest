import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

MODO = os.getenv("NICAGEST_IA_MODO", "groq")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


def construir_prompt(ventas: list) -> str:
    if not ventas:
        return "No hubo ventas hoy. Dame un mensaje breve motivacional para el negocio."

    total = sum(v.get("total", 0) for v in ventas)
    cantidad = len(ventas)

    return f"""Eres un asistente de negocios para una tienda nicaragüense.
Hoy se registraron {cantidad} ventas con un total de C$ {total:.2f}.
Ventas: {json.dumps(ventas, ensure_ascii=False, default=str)}

Dame un análisis breve (3-4 oraciones) con:
- Cómo estuvo el día
- Producto o cliente destacado si hay
- Una recomendación concreta para mañana
Responde en español, tono amigable y directo."""


async def analizar_con_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        return "Falta configurar GROQ_API_KEY en el archivo .env"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            respuesta = await client.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.7,
                },
            )
            data = respuesta.json()

            if "error" in data:
                return f"Error de Groq: {data['error'].get('message', 'desconocido')}"

            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error con Groq: {str(e)}"


async def analizar_con_ollama(prompt: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            respuesta = await client.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            })
            return respuesta.json().get("response", "Sin respuesta de Ollama")
    except Exception as e:
        return f"Error con Ollama: {str(e)}"


async def analizar_con_openai(prompt: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            respuesta = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300
                }
            )
            data = respuesta.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error con OpenAI: {str(e)}"


async def analizar_ventas(ventas: list) -> str:
    prompt = construir_prompt(ventas)
    if MODO == "groq":
        return await analizar_con_groq(prompt)
    elif MODO == "openai":
        return await analizar_con_openai(prompt)
    return await analizar_con_ollama(prompt)