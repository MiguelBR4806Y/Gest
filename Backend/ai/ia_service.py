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

Dame un análisis breve (2-3 oraciones) con:
- Cómo estuvo el día
- Producto o cliente destacado si hay
- Una recomendación concreta para mañana
-Producto más movido del día
Responde en español, tono directo, sin saludos ni frases de cortesía."""


def construir_prompt_chat(pregunta: str, contexto: dict) -> str:
    return f"""Eres un asistente de negocios para una tienda nicaragüense llamada "{contexto.get('nombre_negocio', 'el negocio')}".

REGLAS ESTRICTAS DE RESPUESTA:
- Responde SOLO con la información solicitada.
- Sin saludos, sin despedidas, sin frases como "claro", "por supuesto", "con gusto", "espero que esto te ayude".
- Sin explicaciones innecesarias. Solo datos concretos.
- Formato directo: si te piden el cliente con más compras, responde exactamente eso, y las compras desglosadas en productos y cantidades y total que ha hecho dicho cliente.
- Si no tienes suficiente información para responder, di únicamente: "No hay datos suficientes."
- Usa moneda nicaragüense (C$) para valores monetarios.
- Responde siempre en español.
-Todas las cantidades separalas siempre por miles utilizandso la coma: ','.

=== INVENTARIO ACTUAL ===
{json.dumps(contexto.get('productos', []), ensure_ascii=False, default=str)}

=== CLIENTES REGISTRADOS ===
{json.dumps(contexto.get('clientes', []), ensure_ascii=False, default=str)}

=== HISTORIAL COMPLETO DE VENTAS ===
{json.dumps(contexto.get('ventas', []), ensure_ascii=False, default=str)}

=== MOVIMIENTOS DE INVENTARIO ===
{json.dumps(contexto.get('movimientos', []), ensure_ascii=False, default=str)}

Pregunta: {pregunta}"""


async def _llamar_groq(prompt: str, max_tokens: int = 300) -> str:
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
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                },
            )
            data = respuesta.json()

            if "error" in data:
                return f"Error de Groq: {data['error'].get('message', 'desconocido')}"

            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error con Groq: {str(e)}"


async def analizar_con_groq(prompt: str) -> str:
    return await _llamar_groq(prompt, max_tokens=300)


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


async def responder_pregunta(pregunta: str, contexto: dict) -> str:
    prompt = construir_prompt_chat(pregunta, contexto)
    if MODO == "groq":
        return await _llamar_groq(prompt, max_tokens=500)
    elif MODO == "openai":
        return await analizar_con_openai(prompt)
    return await analizar_con_ollama(prompt)