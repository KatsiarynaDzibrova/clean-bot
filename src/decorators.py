"""Access control decorators."""

from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from .config import ALLOWED_USERS


def restricted(func):
    """Decorator to restrict access to allowed users only."""
    @wraps(func)
    async def wrapped(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
    ):
        user = update.effective_user
        if not user:
            return
        username = (user.username or "").lower()
        if username not in ALLOWED_USERS:
            if update.message:
                await update.message.reply_text("Access denied.")
            elif update.callback_query:
                await update.callback_query.answer("Access denied.", show_alert=True)
            return
        return await func(update, context, *args, **kwargs)

    return wrapped
