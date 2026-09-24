import logging

import aiohttp
from bs4 import BeautifulSoup

from config import LANG, STEAM_COUNTRY
from models import Giveaway

log = logging.getLogger('free-games-bot.steam')
STEAM_SEARCH = 'https://store.steampowered.com/search/'
STEAM_APPDETAILS = 'https://store.steampowered.com/api/appdetails'


async def fetch_text(session, url: str, *, params=None) -> str:
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=25)) as r:
        r.raise_for_status()
        return await r.text()


async def fetch_json(session, url: str, *, params=None):
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=25)) as r:
        r.raise_for_status()
        return await r.json(content_type=None)


def steam_price(row) -> tuple[str | None, bool]:
    pct = row.select_one('.discount_pct')
    is_100 = bool(pct and '-100%' in pct.get_text(' ', strip=True))
    old = row.select_one('.discount_original_price')
    old_price = old.get_text(' ', strip=True) if old else None
    if not old_price:
        prices = row.select('.search_price span')
        if prices:
            old_price = prices[0].get_text(' ', strip=True)
    return old_price, is_100


async def steam_details(session, appid: str):
    data = await fetch_json(session, STEAM_APPDETAILS, params={
        'appids': appid, 'cc': STEAM_COUNTRY, 'l': LANG
    })
    row = data.get(appid, {})
    return row.get('data') if row.get('success') else None


async def get_steam(session) -> list[Giveaway]:
    page = await fetch_text(session, STEAM_SEARCH, params={
        'specials': '1', 'maxprice': 'free', 'cc': STEAM_COUNTRY, 'l': LANG, 'ndl': '1'
    })
    soup = BeautifulSoup(page, 'html.parser')
    out = []

    for row in soup.select('a.search_result_row'):
        appid = (row.get('data-ds-appid') or '').split(',')[0].strip()
        if not appid.isdigit():
            continue
        old_price, is_100 = steam_price(row)
        if not is_100:
            continue

        details = None
        try:
            details = await steam_details(session, appid)
        except Exception as exc:
            log.warning('Steam appdetails %s failed: %s', appid, exc)

        if details:
            if details.get('type') != 'game' or details.get('is_free') is True:
                continue
            po = details.get('price_overview') or {}
            if po:
                if not (
                    int(po.get('initial') or 0) > 0
                    and int(po.get('final') or 0) == 0
                    and int(po.get('discount_percent') or 0) == 100
                ):
                    continue
                old_price = po.get('initial_formatted') or old_price
            title = details.get('name') or f'Steam App {appid}'
            image = details.get('header_image') or (
                f'https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg'
            )
        else:
            title_el = row.select_one('.title')
            title = title_el.get_text(strip=True) if title_el else f'Steam App {appid}'
            img = row.select_one('img')
            image = (img.get('src') if img else None) or (
                f'https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg'
            )

        out.append(Giveaway(
            'Steam', appid, title,
            f'https://store.steampowered.com/app/{appid}/?cc={STEAM_COUNTRY}',
            image, old_price, None, STEAM_COUNTRY,
        ))
    return out
