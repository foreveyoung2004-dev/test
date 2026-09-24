from datetime import datetime, timezone

import aiohttp

from config import EPIC_COUNTRY
from models import Giveaway

EPIC_FREE = 'https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions'


async def fetch_json(session, url: str, *, params=None):
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=25)) as r:
        r.raise_for_status()
        return await r.json(content_type=None)


def parse_iso(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def epic_url(el: dict) -> str:
    for m in ((el.get('catalogNs') or {}).get('mappings') or []):
        if m.get('pageSlug'):
            return f"https://store.epicgames.com/p/{m['pageSlug']}"
    for m in el.get('offerMappings') or []:
        if m.get('pageSlug'):
            return f"https://store.epicgames.com/p/{m['pageSlug']}"
    slug = el.get('productSlug') or el.get('urlSlug')
    return f"https://store.epicgames.com/p/{str(slug).strip('/')}" if slug else 'https://store.epicgames.com/free-games'


def epic_image(el: dict) -> str | None:
    images = el.get('keyImages') or []
    for kind in ('OfferImageWide', 'DieselStoreFrontWide', 'Thumbnail'):
        for img in images:
            if img.get('type') == kind and img.get('url'):
                return img['url']
    return next((img.get('url') for img in images if img.get('url')), None)


def epic_old_price(el: dict) -> tuple[int, str | None]:
    tp = (el.get('price') or {}).get('totalPrice') or {}
    original = tp.get('originalPrice')
    if not isinstance(original, int) or original <= 0:
        return 0, None
    fmt = (tp.get('fmtPrice') or {}).get('originalPrice')
    return original, fmt or f"{original / 100:.2f} {tp.get('currencyCode') or ''}".strip()


def active_epic_promo(el: dict, now: datetime):
    groups = (el.get('promotions') or {}).get('promotionalOffers') or []
    for group in groups:
        for offer in group.get('promotionalOffers') or []:
            if (offer.get('discountSetting') or {}).get('discountPercentage') != 0:
                continue
            start, end = parse_iso(offer.get('startDate')), parse_iso(offer.get('endDate'))
            if start and now < start:
                continue
            if end and now >= end:
                continue
            return True, end
    return False, None


async def get_epic(session) -> list[Giveaway]:
    data = await fetch_json(session, EPIC_FREE, params={
        'locale': 'ru', 'country': EPIC_COUNTRY, 'allowCountries': EPIC_COUNTRY
    })
    elements = data.get('data', {}).get('Catalog', {}).get('searchStore', {}).get('elements', [])
    now, out = datetime.now(timezone.utc), []
    for el in elements:
        active, end = active_epic_promo(el, now)
        if not active:
            continue
        original, old_price = epic_old_price(el)
        if original <= 0:
            continue
        categories = {(c.get('path') or '').lower() for c in (el.get('categories') or [])}
        if 'addons' in categories:
            continue
        title = (el.get('title') or '').strip()
        if not title:
            continue
        item_id = str(el.get('id') or el.get('namespace') or title)
        out.append(Giveaway(
            'Epic Games', item_id, title, epic_url(el), epic_image(el),
            old_price, end, EPIC_COUNTRY,
        ))
    return out
