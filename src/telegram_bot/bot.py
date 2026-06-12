"""Bot Telegram pentru controlul pipeline-ului: generare la cerere, aprobare upload, status."""

from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.config import env
from src.storage import db

HELP_TEXT = (
    "Comenzi disponibile:\n"
    "/generate <idee> - genereaza un video pe baza ideii (sau trending daca e gol)\n"
    "/status - lista videoclipuri in asteptare de aprobare\n"
    "/approve <run_id> - aproba si posteaza videoclipul pe YouTube\n"
    "/reject <run_id> - respinge videoclipul generat\n"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.main import run_pipeline

    idea = " ".join(context.args) if context.args else None
    await update.message.reply_text("Generare pornita... iti trimit videoclipul cand e gata.")

    loop = asyncio.get_event_loop()
    try:
        run_id = await loop.run_in_executor(None, run_pipeline, idea)
        await update.message.reply_text(f"Video generat cu succes. ID rulare: {run_id}")
    except Exception as exc:  # noqa: BLE001
        await update.message.reply_text(f"Eroare la generare: {exc}")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = db.get_pending_runs()
    if not pending:
        await update.message.reply_text("Nu exista videoclipuri in asteptare de aprobare.")
        return

    lines = ["Videoclipuri in asteptare:"]
    for run_id, data in pending.items():
        lines.append(f"- {run_id}: {data.get('titlu', 'fara titlu')}")
    await update.message.reply_text("\n".join(lines))


async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.main import approve_and_upload

    if not context.args:
        await update.message.reply_text("Foloseste: /approve <run_id>")
        return

    run_id = context.args[0]
    await update.message.reply_text(f"Se posteaza {run_id} pe YouTube...")

    loop = asyncio.get_event_loop()
    try:
        url = await loop.run_in_executor(None, approve_and_upload, run_id)
        await update.message.reply_text(f"Postat cu succes: {url}")
    except Exception as exc:  # noqa: BLE001
        await update.message.reply_text(f"Eroare la upload: {exc}")


async def reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Foloseste: /reject <run_id>")
        return

    run_id = context.args[0]
    db.update_run(run_id, {"status": "rejected"})
    await update.message.reply_text(f"Rularea {run_id} a fost respinsa.")


def main() -> None:
    token = env("TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("reject", reject))

    app.run_polling()


if __name__ == "__main__":
    main()
