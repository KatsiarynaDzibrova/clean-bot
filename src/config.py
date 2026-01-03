"""Configuration and constants."""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "<PASTE_YOUR_TOKEN_HERE>"
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not found. Please set it in your .env file.")

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
DB_PATH = os.path.join(BASE_DIR, "tasks.db")
ROOMS_PATH = Path(__file__).parent.parent / "rooms.txt"


def get_rooms() -> list[str]:
    """Load rooms from rooms.txt file."""
    if ROOMS_PATH.exists():
        return [line.strip() for line in ROOMS_PATH.read_text().splitlines() if line.strip()]
    return []

allowed = os.getenv("ALLOWED_USERNAMES", "")
ALLOWED_USERS = {u.strip().lower() for u in allowed.split(",") if u.strip()}

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
ADD_NAME, ADD_ROOM, ADD_FREQ, ADD_POINTS = range(4)
EDIT_SELECT, EDIT_FIELD, EDIT_NEWVAL = range(3)
DONE_WAIT_ID = range(1)
