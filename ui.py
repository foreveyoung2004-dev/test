import html
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from database import is_claimed
from models import Giveaway


def fmt_end(dt: datetime | None) -> str:
    return 'срок не указан магазином' if not dt else dt.astimezone().strftime('%d.%m.%Y %H:%M %Z')


def caption(g: Giveaway) -> str:
    icon = '🟦' if g.source == 'Steam' else '⬛'
    return (
        f'{icon} <b>НОВАЯ БЕСПЛАТНАЯ РАЗДАЧА</b>\n\n'
        f'🎮 <b>{html.escape(g.title)}</b>\n'
        f'🏪 {html.escape(g.source)}\n'
        f'🇧🇾 Проверено для региона: <b>{html.escape(g.region)}</b>\n'
        f'💰 Было: <s>{html.escape(g.old_price or "платная игра")}</s>\n'
        '✅ Сейчас: <b>БЕСПЛАТНО НАВСЕГДА</b>\n'
        f'⏳ До: {html.escape(fmt_end(g.end_at))}\n\n'
        'После получения игра остаётся в библиотеке.'
    )


def keyboard(g: Giveaway, claimed: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton('🎁 Забрать игру', url=g.url)]]
    rows.append([InlineKeyboardButton(
        '✅ Уже забрал', callback_data='noop' if claimed else f'claim|{g.source}|{g.item_id}'
    )])
    return InlineKeyboardMarkup(rows)


async def send_giveaway(bot, chat_id: int, g: Giveaway) -> None:
    claimed = is_claimed(chat_id, g)
    try:
        if g.image:
            await bot.send_photo(
                chat_id=chat_id, photo=g.image, caption=caption(g),
                parse_mode=ParseMode.HTML, reply_markup=keyboard(g, claimed),
            )
            return
    except Exception:
        pass
    await bot.send_message(
        chat_id=chat_id, text=caption(g), parse_mode=ParseMode.HTML,
        disable_web_page_preview=False, reply_markup=keyboard(g, claimed),
    )
