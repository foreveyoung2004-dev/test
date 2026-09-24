import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN', '').strip()
CHECK_INTERVAL_MINUTES = max(5, int(os.getenv('CHECK_INTERVAL_MINUTES', '15')))
STEAM_COUNTRY = os.getenv('STEAM_COUNTRY', 'BY').upper()
EPIC_COUNTRY = os.getenv('EPIC_COUNTRY', 'BY').upper()
LANG = os.getenv('LANG', 'russian')
DB_PATH = Path(os.getenv('DB_PATH', 'giveaways.db'))
USER_AGENT = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/131.0 Safari/537.36 FreeGamesBYBot/2.1'
)
