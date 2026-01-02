"""Configuration and constants."""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "<PASTE_YOUR_TOKEN_HERE>"
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not found. Please set it in your .env file.")

DB_PATH = "tasks.db"

allowed = os.getenv("ALLOWED_USERNAMES", "")
ALLOWED_USERS = {u.strip().lower() for u in allowed.split(",") if u.strip()}

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
ADD_NAME, ADD_FREQ = range(2)
EDIT_SELECT, EDIT_FIELD, EDIT_NEWVAL = range(3)
DONE_WAIT_ID = range(1)
