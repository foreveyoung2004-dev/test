import html
import logging
import re
from datetime import datetime, timezone

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

from config import BOT_TOKEN, CHECK_INTERVAL_MINUTES, EPIC_COUNTRY, STEAM_COUNTRY
from database import (
    claimed_rows, is_claimed, is_seen, mark_claimed, mark_reminder_sent,
    mark_seen, reminder_sent, set_enabled, subscribe, subscribers,
)
from models import Giveaway
from stores import collect_all
from ui import keyboard, send_giveaway

logging.basicConfig(format='%(asctime)s | %(levelname)s | %(name)s | %(message)s', level=logging.INFO)
log = logging.getLogger('free-games-bot')


async def check_and_notify(context: ContextTypes.DEFAULT_TYPE) -> None:
    items, errors = await collect_all()
    log.info('Found %d active giveaways; errors=%s', len(items), errors or 'none')
    for g in [x for x in items if not is_seen(x)]:
        sent = False
        for chat_id in subscribers():
            try:
                await send_giveaway(context.bot, chat_id, g)
                sent = True
            except Exception:
                log.exception('Failed sending %s to %s', g.title, chat_id)
        if sent:
            mark_seen(g)


async def check_deadlines(context: ContextTypes.DEFAULT_TYPE) -> None:
    items, _ = await collect_all()
    now = datetime.now(timezone.utc)
    for g in items:
        if not g.end_at:
            continue
        left = (g.end_at - now).total_seconds()
        if left <= 0 or left > 6 * 3600:
            continue
        for chat_id in subscribers():
            if is_claimed(chat_id, g) or reminder_sent(chat_id, g, '6h'):
                continue
            hours = max(1, int((left + 3599) // 3600))
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        '⚠️ <b>РАЗДАЧА СКОРО ЗАКОНЧИТСЯ</b>\n\n'
                        f'🎮 <b>{html.escape(g.title)}</b>\n🏪 {html.escape(g.source)}\n'
                        f'⏳ Осталось примерно: <b>{hours} ч.</b>\n\n'
                        'Ты ещё не отметил эту игру как полученную.'
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard(g, False),
                )
                mark_reminder_sent(chat_id, g, '6h')
            except Exception:
                log.exception('Failed reminder %s to %s', g.title, chat_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    subscribe(chat_id)
    await update.effective_message.reply_text(
        '✅ <b>Уведомления включены.</b>\n\n'
        'Отслеживаю временно бесплатные платные игры в Steam и Epic Games Store для региона BY.\n'
        'Free-to-play, демо, DLC и бесплатные выходные исключаются.\n\n'
        f'Проверка каждые <b>{CHECK_INTERVAL_MINUTES} мин.</b>\n\n'
        '/now — проверить сейчас\n/status — статус\n/collection — полученные игры\n'
        '/mute — выключить уведомления\n/resume — включить уведомления',
        parse_mode=ParseMode.HTML,
    )
    items, errors = await collect_all()
    if not items:
        msg = 'Сейчас активных раздач платных игр не найдено.'
        if errors:
            msg += '\n\n⚠️ Ошибки проверки: ' + ', '.join(errors)
        await update.effective_message.reply_text(msg)
        return
    for g in items:
        await send_giveaway(context.bot, chat_id, g)
        mark_seen(g)


async def now_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat:
        return
    await update.effective_message.reply_text('🔎 Проверяю Steam и Epic для BY…')
    items, errors = await collect_all()
    if not items:
        msg = 'Активных временно бесплатных платных игр сейчас не найдено.'
        if errors:
            msg += '\n\n⚠️ Ошибки проверки: ' + ', '.join(errors)
        await update.effective_message.reply_text(msg)
        return
    for g in items:
        await send_giveaway(context.bot, update.effective_chat.id, g)


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f'🟢 <b>Бот работает</b>\n🇧🇾 Steam: {STEAM_COUNTRY}\n🇧🇾 Epic: {EPIC_COUNTRY}\n'
        f'⏱ Интервал: {CHECK_INTERVAL_MINUTES} мин.\n🎮 Только платная игра → временно бесплатно',
        parse_mode=ParseMode.HTML,
    )


async def mute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat:
        set_enabled(update.effective_chat.id, False)
    await update.effective_message.reply_text('🔕 Автоматические уведомления отключены.')


async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat:
        set_enabled(update.effective_chat.id, True)
    await update.effective_message.reply_text('🔔 Автоматические уведомления включены.')


async def collection_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat:
        return
    rows = claimed_rows(update.effective_chat.id)
    if not rows:
        await update.effective_message.reply_text('📚 Ты пока не отметил ни одной игры как полученную.')
        return
    lines = ['📚 <b>Твоя отмеченная коллекция:</b>', '']
    for i, row in enumerate(rows[:100], 1):
        lines.append(f"{i}. ✅ <b>{html.escape(row['title'])}</b> — {html.escape(row['source'])}")
    if len(rows) > 100:
        lines.append(f'\n…и ещё {len(rows) - 100}')
    await update.effective_message.reply_text('\n'.join(lines), parse_mode=ParseMode.HTML)


async def claim_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q:
        return
    await q.answer()
    if q.data == 'noop' or not (q.data or '').startswith('claim|'):
        return
    try:
        _, source, item_id = q.data.split('|', 2)
    except ValueError:
        return
    items, _ = await collect_all()
    g = next((x for x in items if x.source == source and x.item_id == item_id), None)
    if g is None:
        title = 'Игра'
        if q.message and q.message.caption:
            lines = q.message.caption.splitlines()
            if len(lines) >= 3:
                title = re.sub(r'<[^>]+>', '', lines[2]).strip() or title
        g = Giveaway(
            source, item_id, title,
            'https://store.steampowered.com/' if source == 'Steam' else 'https://store.epicgames.com/free-games',
            None, None, None, STEAM_COUNTRY if source == 'Steam' else EPIC_COUNTRY,
        )
    chat_id = q.message.chat_id if q.message else update.effective_chat.id
    mark_claimed(chat_id, g)
    try:
        await q.edit_message_reply_markup(reply_markup=keyboard(g, True))
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=chat_id,
        text=f'✅ <b>{html.escape(g.title)}</b> отмечена как полученная.',
        parse_mode=ParseMode.HTML,
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception('Telegram update error', exc_info=context.error)


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit('BOT_TOKEN не задан. Создай .env и вставь токен от @BotFather.')
    app: Application = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('now', now_cmd))
    app.add_handler(CommandHandler('status', status_cmd))
    app.add_handler(CommandHandler('mute', mute_cmd))
    app.add_handler(CommandHandler('resume', resume_cmd))
    app.add_handler(CommandHandler('collection', collection_cmd))
    app.add_handler(CallbackQueryHandler(claim_callback, pattern=r'^(?:claim\|.*|noop)$'))
    app.add_handler(CommandHandler('help', start))
    app.add_error_handler(error_handler)
    if app.job_queue is None:
        raise SystemExit('JobQueue недоступен. Установи зависимости из requirements.txt')
    app.job_queue.run_repeating(check_and_notify, interval=CHECK_INTERVAL_MINUTES * 60, first=20)
    app.job_queue.run_repeating(check_deadlines, interval=30 * 60, first=60)
    app.run_polling(drop_pending_updates=False)


if __name__ == '__main__':
    main()
