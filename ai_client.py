from __future__ import annotations

from openai import AsyncOpenAI
from config import settings


client = AsyncOpenAI(
    api_key=settings.aiai_api_key,
    base_url=settings.aiai_base_url,
    timeout=120.0,
    max_retries=2,
)


async def ask_ai(history: list[dict], user_text: str) -> str:
    messages = [
        {"role": "system", "content": settings.system_prompt},
        *history,
        {"role": "user", "content": user_text},
    ]

    response = await client.chat.completions.create(
        model=settings.aiai_model,
        messages=messages,
        temperature=0.7,
        max_tokens=settings.max_output_tokens,
    )

    content = response.choices[0].message.content
    if not content:
        return "Модель вернула пустой ответ. Попробуйте ещё раз."
    return content.strip()


async def model_is_available() -> tuple[bool, str]:
    models = await client.models.list()
    ids = {item.id for item in models.data}
    return settings.aiai_model in ids, settings.aiai_model
