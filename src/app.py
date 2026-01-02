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
"""

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .config import TOKEN, ADD_NAME, ADD_ROOM, ADD_FREQ, EDIT_SELECT, EDIT_FIELD, EDIT_NEWVAL, DONE_WAIT_ID, logger
from .database import init_db
from .handlers import (
    start,
    addtask_start,
    addtask_name,
    addtask_room,
    addtask_freq,
    rooms_cmd,
    tasks_cmd,
    due_cmd,
    done_start,
    done_receive_id,
    remove_cmd,
    edit_start,
    edit_select,
    edit_field,
    edit_newval,
    cancel,
)


def main():
    init_db()
    if TOKEN.startswith("<PASTE"):
        print(
            "Please set your bot token in TELEGRAM_BOT_TOKEN env var or paste it into the script."
        )
        return

    app = ApplicationBuilder().token(TOKEN).build()

    # basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rooms", rooms_cmd))
    app.add_handler(CommandHandler("tasks", tasks_cmd))
    app.add_handler(CommandHandler("due", due_cmd))
    app.add_handler(CommandHandler("remove", remove_cmd))

    # addtask conversation
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("addtask", addtask_start)],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_name)],
            ADD_ROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_room)],
            ADD_FREQ: [MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_freq)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(add_conv)

    # done conversation (for interactive id entry)
    done_conv = ConversationHandler(
        entry_points=[CommandHandler("done", done_start)],
        states={
            DONE_WAIT_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, done_receive_id)
            ]
        },
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
