"""Telegram bot command handlers."""

from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from .config import ADD_NAME, ADD_ROOM, ADD_FREQ, EDIT_SELECT, EDIT_FIELD, EDIT_NEWVAL, DONE_WAIT_ID, get_rooms
from .database import (
    add_task_db,
    list_tasks_db,
    get_task_db,
    update_task_last_done,
    update_task_field,
    remove_task_db,
)
from .utils import parse_frequency_to_days, tasks_due_now, format_task_row
from .decorators import restricted


# ---- Start/Help ----
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
    except ValueError:
        await update.message.reply_text(
            "I couldn't parse that. Use examples like '3d', '1w', '1m' or '7'. Try /addtask again."
        )
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
    for tid, name, freq, last_iso, notes, nd in due:
        lines.append(f"{tid}. {name} — every {freq}d")
    lines.append("\nMark a task done with /done <id>")
    await update.message.reply_text("\n".join(lines))


# ---- Done command ----
@restricted
async def done_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text(
            f"Marked done: {row[1]}. Next due in {row[2]} days."
        )
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
    await update.message.reply_text(
        f"Marked done: {row[1]}. Next due in {row[2]} days."
    )
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
    await update.message.reply_text(
        "What do you want to edit? Reply with 'name', 'frequency' or 'notes'."
    )
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
            await update.message.reply_text(
                "Could not parse frequency. Use '3d', '1w', '1m' or days like '7'."
            )
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
