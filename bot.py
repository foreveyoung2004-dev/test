from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatAction, ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from ai_client import ask_ai, model_is_available
from config import settings, validate_settings
from db import add_message, clear_history, get_history, init_db
from utils import split_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("aiai-120b-bot")

dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "🤖 Привет! Я Telegram-ассистент на GPT OSS 120B через AIAI.BY.\n\n"
        "Просто отправь сообщение — я отвечу с учётом истории диалога.\n\n"
        "Команды:\n"
        "/new — начать новый диалог\n"
        "/model — показать текущую модель\n"
        "/status — проверить доступность модели\n"
        "/help — помощь"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Отправь мне любой текст. История сохраняется отдельно для каждого пользователя.\n\n"
        "В группе бот отвечает, если его упомянуть @username или ответить на его сообщение. "
        "Для чтения обычных сообщений в группах может потребоваться отключить Privacy Mode у BotFather."
    )


@dp.message(Command("new"))
async def cmd_new(message: Message) -> None:
    if not message.from_user:
        return
    await clear_history(message.chat.id, message.from_user.id)
    await message.answer("🧹 Контекст очищен. Начинаем новый диалог.")


@dp.message(Command("model"))
async def cmd_model(message: Message) -> None:
    await message.answer(f"Текущая модель: {settings.aiai_model}")


@dp.message(Command("status"))
async def cmd_status(message: Message) -> None:
    try:
        ok, model = await model_is_available()
        if ok:
            await message.answer(f"✅ AIAI.BY доступен. Модель {model} найдена в /v1/models.")
        else:
            await message.answer(
                f"⚠️ API отвечает, но модель {model} не найдена в текущем списке. "
                "Проверь AIAI_MODEL в .env."
            )
    except Exception as exc:
        logger.exception("Model status check failed")
        await message.answer(f"❌ Ошибка проверки API: {type(exc).__name__}: {exc}")


async def should_answer_in_group(message: Message, bot: Bot) -> bool:
    if message.chat.type == ChatType.PRIVATE:
        return True
    if not message.text:
        return False

    me = await bot.get_me()
    username = (me.username or "").lower()
    text = message.text.lower()

    mentioned = bool(username and f"@{username}" in text)
    replied_to_bot = bool(
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == me.id
    )
    return mentioned or replied_to_bot


@dp.message(F.text)
async def handle_text(message: Message, bot: Bot) -> None:
    if not message.from_user or not message.text:
        return
    if message.text.startswith("/"):
        return
    if not await should_answer_in_group(message, bot):
        return

    text = message.text.strip()
    if message.chat.type != ChatType.PRIVATE:
        me = await bot.get_me()
        if me.username:
            text = text.replace(f"@{me.username}", "").strip()
        if not text:
            return

    chat_id = message.chat.id
    user_id = message.from_user.id

    try:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        history = await get_history(chat_id, user_id)
        answer = await ask_ai(history, text)

        await add_message(chat_id, user_id, "user", text)
        await add_message(chat_id, user_id, "assistant", answer)

        for part in split_text(answer):
            try:
                await message.answer(part)
            except TelegramBadRequest:
                await message.answer(part[:3900])
    except Exception as exc:
        logger.exception("AI request failed")
        await message.answer(
            "❌ Не удалось получить ответ от нейросети.\n"
            f"Ошибка: {type(exc).__name__}: {exc}"
        )


async def main() -> None:
    validate_settings()
    await init_db()
    bot = Bot(token=settings.telegram_token)
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot starting with model=%s base_url=%s", settings.aiai_model, settings.aiai_base_url)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
