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
        "/tasks   - list all tasks (or /tasks <room>)\n"
        "/due     - show tasks due now (or /due <room>)\n"
        "/done    - mark task done (usage: /done <id> or just /done then send id)\n"
        "/edit    - edit task\n"
        "/remove  - remove task (usage: /remove <id>)\n"
        "/rooms   - list available rooms\n"
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
    rooms = get_rooms()
    if rooms:
        room_list = ", ".join(rooms)
        await update.message.reply_text(f"Which room? ({room_list})")
    else:
        await update.message.reply_text("Which room?")
    return ADD_ROOM


@restricted
async def addtask_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    room_txt = update.message.text.strip()
    rooms = get_rooms()
    # Case-insensitive match
    matched_room = None
    for r in rooms:
        if r.lower() == room_txt.lower():
            matched_room = r
            break
    if rooms and not matched_room:
        room_list = ", ".join(rooms)
        await update.message.reply_text(
            f"Unknown room. Please choose from: {room_list}"
        )
        return ADD_ROOM
    context.user_data["new_task_room"] = matched_room or room_txt
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
    room = context.user_data.get("new_task_room")
    add_task_db(name, freq_days, room)
    await update.message.reply_text(f"Added: {name} — {room} — every {freq_days} days.")
    context.user_data.pop("new_task_name", None)
    context.user_data.pop("new_task_room", None)
    return ConversationHandler.END


# ---- Rooms command ----
@restricted
async def rooms_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rooms = get_rooms()
    if rooms:
        lines = ["Available rooms:"]
        for r in rooms:
            lines.append(f"• {r}")
        await update.message.reply_text("\n".join(lines))
    else:
        await update.message.reply_text("No rooms configured. Add rooms to rooms.txt")


# ---- List tasks ----
@restricted
async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    room_filter = None
    if args:
        room_arg = " ".join(args)
        rooms = get_rooms()
        for r in rooms:
            if r.lower() == room_arg.lower():
                room_filter = r
                break
        if not room_filter:
            await update.message.reply_text(f"Unknown room: {room_arg}")
            return
    rows = list_tasks_db(room=room_filter)
    if not rows:
        if room_filter:
            await update.message.reply_text(f"No tasks in {room_filter}.")
        else:
            await update.message.reply_text("No tasks yet. Add one with /addtask")
        return

    if room_filter:
        # Single room - simple list
        lines = [f"Tasks in {room_filter}:"]
        for r in rows:
            lines.append(format_task_row(r))
    else:
        # All rooms - group by room
        lines = ["Your cleaning tasks:"]
        tasks_by_room = {}
        for r in rows:
            room = r[4]
            if room not in tasks_by_room:
                tasks_by_room[room] = []
            tasks_by_room[room].append(r)
        for room in tasks_by_room:
            lines.append(f"\n{room}:")
            for r in tasks_by_room[room]:
                lines.append(format_task_row(r))
    await update.message.reply_text("\n".join(lines))


# ---- Due tasks ----
@restricted
async def due_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    room_filter = None
    if args:
        room_arg = " ".join(args)
        rooms = get_rooms()
        for r in rooms:
            if r.lower() == room_arg.lower():
                room_filter = r
                break
        if not room_filter:
            await update.message.reply_text(f"Unknown room: {room_arg}")
            return
    due = tasks_due_now(room=room_filter)
    if not due:
        if room_filter:
            await update.message.reply_text(f"No tasks due in {room_filter}. Good job!")
        else:
            await update.message.reply_text("No tasks are due right now. Good job!")
        return
    header = f"Tasks due in {room_filter}:" if room_filter else "Tasks to do now:"
    lines = [header]
    for tid, name, freq, last_iso, room, notes, nd in due:
        lines.append(f"{tid}. {name} — {room} — every {freq}d")
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
        "What do you want to edit? Reply with 'name', 'frequency', 'room' or 'notes'."
    )
    return EDIT_FIELD


@restricted
async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip().lower()
    if choice not in ("name", "frequency", "room", "notes"):
        await update.message.reply_text("Reply with 'name', 'frequency', 'room' or 'notes'.")
        return EDIT_FIELD
    context.user_data["edit_field"] = choice
    if choice == "room":
        rooms = get_rooms()
        if rooms:
            room_list = ", ".join(rooms)
            await update.message.reply_text(f"Send the new room ({room_list}).")
        else:
            await update.message.reply_text("Send the new room.")
    else:
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
    elif field == "room":
        rooms = get_rooms()
        matched_room = None
        for r in rooms:
            if r.lower() == newval.lower():
                matched_room = r
                break
        if rooms and not matched_room:
            room_list = ", ".join(rooms)
            await update.message.reply_text(f"Unknown room. Choose from: {room_list}")
            return EDIT_NEWVAL
        update_task_field(tid, "room", matched_room or newval)
        await update.message.reply_text(f"Updated room to {matched_room or newval}.")
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
