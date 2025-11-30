"""
Minimal Telegram cleaning-task bot.

Commands:
  /start      - show help
  /addtask    - add a task (conversation: name -> frequency)
  /tasks      - list all tasks (with IDs and next-due)
  /due        - list tasks due now
  /done       - mark a task done (usage: /done <id> OR /done then send id)
  /edit       - edit a task (conversation)
  /remove     - remove a task (usage: /remove <id>)
  /cancel     - cancel current operation

Storage: local SQLite database 'tasks.db'
Run: python cleaner_bot.py
"""

import os
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from functools import wraps
import re
import logging
import asyncio


from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters
)


def restricted(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
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

# ----------------------
# Configuration
# ----------------------
load_dotenv()  # Load variables from .env
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "<PASTE_YOUR_TOKEN_HERE>"
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not found. Please set it in your .env file.")

DB_PATH = "tasks.db"

allowed = os.getenv("ALLOWED_USERNAMES", "")
ALLOWED_USERS = {u.strip().lower() for u in allowed.split(",") if u.strip()}
# ----------------------

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
ADD_NAME, ADD_FREQ = range(2)
EDIT_SELECT, EDIT_FIELD, EDIT_NEWVAL = range(3)
DONE_WAIT_ID = range(1)

# ----------------------
# DB helpers
# ----------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        frequency_days INTEGER NOT NULL,
        last_done TEXT NOT NULL,
        notes TEXT
    )
    """)
    conn.commit()
    conn.close()

def add_task_db(name: str, freq_days: int, notes: str = ""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now_iso = datetime.utcnow().isoformat()
    cur.execute("INSERT INTO tasks (name, frequency_days, last_done, notes) VALUES (?, ?, ?, ?)",
                (name, freq_days, now_iso, notes))
    conn.commit()
    conn.close()

def list_tasks_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, frequency_days, last_done, notes FROM tasks ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_task_db(task_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, frequency_days, last_done, notes FROM tasks WHERE id = ?", (task_id,))
    row = cur.fetchone()
    conn.close()
    return row

def update_task_last_done(task_id: int, when: datetime):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET last_done = ? WHERE id = ?", (when.isoformat(), task_id))
    conn.commit()
    conn.close()

def update_task_field(task_id: int, field: str, value):
    if field not in ("name", "frequency_days", "notes"):
        raise ValueError("Invalid field")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(f"UPDATE tasks SET {field} = ? WHERE id = ?", (value, task_id))
    conn.commit()
    conn.close()

def remove_task_db(task_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

# ----------------------
# Helper utilities
# ----------------------
def parse_frequency_to_days(text: str) -> int:
    """
    Accepts strings like:
      - "3d" => 3
      - "1w" => 7
      - "1m" => 30
      - "10"  => 10 days
      - "2 days" / "2d" / "2w" / "2months" etc.
    Returns integer days. Raises ValueError on bad input.
    """
    s = text.strip().lower()
    # direct integer
    if re.fullmatch(r"\d+", s):
        return int(s)
    m = re.match(r"^(\d+)\s*(d|day|days)$", s)
    if m:
        return int(m.group(1))
    m = re.match(r"^(\d+)\s*(w|week|weeks)$", s)
    if m:
        return int(m.group(1)) * 7
    m = re.match(r"^(\d+)\s*(m|month|months)$", s)
    if m:
        return int(m.group(1)) * 30
    m = re.match(r"^(\d+)\s*(d|w|m)$", s)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit == "d":
            return num
        if unit == "w":
            return num * 7
        if unit == "m":
            return num * 30
    raise ValueError("Could not parse frequency. Use e.g. '3d', '1w', '1m' or a number of days.")

def next_due_text(last_done_iso: str, freq_days: int) -> (datetime, str):
    last = datetime.fromisoformat(last_done_iso)
    nd = last + timedelta(days=freq_days)
    return nd, nd.strftime("%Y-%m-%d %H:%M UTC")

def tasks_due_now():
    now = datetime.utcnow()
    due = []
    for row in list_tasks_db():
        tid, name, freq, last_iso, notes = row
        nd, nd_text = next_due_text(last_iso, freq)
        if nd <= now:
            due.append((tid, name, freq, last_iso, notes, nd))
    return due

def format_task_row(row):
    tid, name, freq, last_iso, notes = row
    nd, nd_text = next_due_text(last_iso, freq)
    return f"{tid}. {name} — every {freq}d — next due: {nd_text}" + (f" — {notes}" if notes else "")

# ----------------------
# Bot handlers
# ----------------------
@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "Cleaning Bot — minimal command interface.\n\n"
        "Commands:\n"
        "/addtask - add a task\n"
        "/tasks   - list all tasks\n"
        "/due     - show tasks due now\n"
        "/done    - mark task done (usage: /done <id> or just /done then send id)\n"
        "/edit    - edit task\n"
        "/remove  - remove task (usage: /remove <id>)\n"
        "/cancel  - cancel current command\n"
    )
    await update.message.reply_text(txt)

# ---- Add task conversation ----
@restricted
async def addtask_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("What's the task name? (e.g. Clean bathroom)")
    return ADD_NAME

@restricted
async def addtask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["new_task_name"] = text
    await update.message.reply_text("How often? (e.g. 3d, 1w, 1m — or number of days)")
    return ADD_FREQ

@restricted
async def addtask_freq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    freq_txt = update.message.text.strip()
    try:
        freq_days = parse_frequency_to_days(freq_txt)
    except ValueError as e:
        await update.message.reply_text("I couldn't parse that. Use examples like '3d', '1w', '1m' or '7'. Try /addtask again.")
        return ConversationHandler.END
    name = context.user_data.get("new_task_name")
    add_task_db(name, freq_days)
    await update.message.reply_text(f"Added: {name} — every {freq_days} days.")
    context.user_data.pop("new_task_name", None)
    return ConversationHandler.END

# ---- List tasks ----
@restricted
async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = list_tasks_db()
    if not rows:
        await update.message.reply_text("No tasks yet. Add one with /addtask")
        return
    lines = ["Your cleaning tasks:"]
    for r in rows:
        lines.append(format_task_row(r))
    await update.message.reply_text("\n".join(lines))

# ---- Due tasks ----
@restricted
async def due_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    due = tasks_due_now()
    if not due:
        await update.message.reply_text("No tasks are due right now. Good job!")
        return
    lines = ["Tasks to do now:"]
    for (tid, name, freq, last_iso, notes, nd) in due:
        lines.append(f"{tid}. {name} — every {freq}d")
    lines.append("\nMark a task done with /done <id>")
    await update.message.reply_text("\n".join(lines))

# ---- Done command ----
@restricted
async def done_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # If user provided id with command: use it
    args = context.args
    if args:
        try:
            tid = int(args[0])
        except ValueError:
            await update.message.reply_text("Usage: /done <id>  — id is numeric.")
            return
        row = get_task_db(tid)
        if not row:
            await update.message.reply_text(f"No task with id {tid}.")
            return
        update_task_last_done(tid, datetime.utcnow())
        await update.message.reply_text(f"Marked done: {row[1]}. Next due in {row[2]} days.")
        return
    # else ask for id
    rows = list_tasks_db()
    if not rows:
        await update.message.reply_text("No tasks to mark done.")
        return ConversationHandler.END
    lines = ["Which task id to mark done? Send the id number."]
    for r in rows:
        lines.append(format_task_row(r))
    await update.message.reply_text("\n".join(lines))
    return DONE_WAIT_ID

@restricted
async def done_receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    try:
        tid = int(txt)
    except ValueError:
        await update.message.reply_text("Please send a numeric id (or /cancel).")
        return DONE_WAIT_ID
    row = get_task_db(tid)
    if not row:
        await update.message.reply_text(f"No task with id {tid}.")
        return ConversationHandler.END
    update_task_last_done(tid, datetime.utcnow())
    await update.message.reply_text(f"Marked done: {row[1]}. Next due in {row[2]} days.")
    return ConversationHandler.END

# ---- Remove ----
@restricted
async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /remove <id>")
        return
    try:
        tid = int(args[0])
    except ValueError:
        await update.message.reply_text("Id must be a number.")
        return
    row = get_task_db(tid)
    if not row:
        await update.message.reply_text(f"No task with id {tid}.")
        return
    remove_task_db(tid)
    await update.message.reply_text(f"Removed task {tid}: {row[1]}")

# ---- Edit conversation ----
@restricted
async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = list_tasks_db()
    if not rows:
        await update.message.reply_text("No tasks to edit.")
        return ConversationHandler.END
    lines = ["Which task id to edit? Send the id number."]
    for r in rows:
        lines.append(format_task_row(r))
    await update.message.reply_text("\n".join(lines))
    return EDIT_SELECT

@restricted
async def edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    try:
        tid = int(txt)
    except ValueError:
        await update.message.reply_text("Send a numeric id (or /cancel).")
        return EDIT_SELECT
    row = get_task_db(tid)
    if not row:
        await update.message.reply_text(f"No task with id {tid}.")
        return ConversationHandler.END
    context.user_data["edit_id"] = tid
    await update.message.reply_text("What do you want to edit? Reply with 'name', 'frequency' or 'notes'.")
    return EDIT_FIELD

@restricted
async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip().lower()
    if choice not in ("name", "frequency", "notes"):
        await update.message.reply_text("Reply with 'name', 'frequency' or 'notes'.")
        return EDIT_FIELD
    context.user_data["edit_field"] = choice
    await update.message.reply_text(f"Send the new value for {choice}.")
    return EDIT_NEWVAL

@restricted
async def edit_newval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    newval = update.message.text.strip()
    tid = context.user_data.get("edit_id")
    field = context.user_data.get("edit_field")
    if field == "frequency":
        try:
            freq_days = parse_frequency_to_days(newval)
        except ValueError:
            await update.message.reply_text("Could not parse frequency. Use '3d', '1w', '1m' or days like '7'.")
            return ConversationHandler.END
        update_task_field(tid, "frequency_days", freq_days)
        await update.message.reply_text(f"Updated frequency to every {freq_days} days.")
    else:
        db_field = "name" if field == "name" else "notes"
        update_task_field(tid, db_field, newval)
        await update.message.reply_text(f"Updated {field}.")
    context.user_data.pop("edit_id", None)
    context.user_data.pop("edit_field", None)
    return ConversationHandler.END

# ---- Cancel handler ----
@restricted
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

# ----------------------
# Main
# ----------------------
def main():
    init_db()
    if TOKEN.startswith("<PASTE"):
        print("Please set your bot token in TELEGRAM_BOT_TOKEN env var or paste it into the script.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    # basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tasks", tasks_cmd))
    app.add_handler(CommandHandler("due", due_cmd))
    app.add_handler(CommandHandler("remove", remove_cmd))

    # addtask conversation
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("addtask", addtask_start)],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_name)],
            ADD_FREQ: [MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_freq)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(add_conv)

    # done conversation (for interactive id entry)
    done_conv = ConversationHandler(
        entry_points=[CommandHandler("done", done_start)],
        states={DONE_WAIT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, done_receive_id)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
    )
    app.add_handler(done_conv)

    # edit conversation
    edit_conv = ConversationHandler(
        entry_points=[CommandHandler("edit", edit_start)],
        states={
            EDIT_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_select)],
            EDIT_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field)],
            EDIT_NEWVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_newval)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(edit_conv)

    # start polling
    logger.info("Bot started. Polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
