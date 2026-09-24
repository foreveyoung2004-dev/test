import asyncio
import logging

import aiohttp

from config import USER_AGENT
from epic_store import get_epic
from models import Giveaway
from steam_store import get_steam

log = logging.getLogger('free-games-bot.stores')


def dedupe(items: list[Giveaway]) -> list[Giveaway]:
    out, keys = [], set()
    for item in items:
        if item.key not in keys:
            keys.add(item.key)
            out.append(item)
    return out


async def collect_all() -> tuple[list[Giveaway], list[str]]:
    errors = []
    headers = {'User-Agent': USER_AGENT, 'Accept-Language': 'ru,en;q=0.8'}
    async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as session:
        async def safe(name, coro):
            try:
                return await coro
            except Exception as exc:
                log.exception('%s checker failed', name)
                errors.append(f'{name}: {type(exc).__name__}')
                return []
        steam, epic = await asyncio.gather(
            safe('Steam', get_steam(session)), safe('Epic', get_epic(session))
        )
    return dedupe([*steam, *epic]), errors
