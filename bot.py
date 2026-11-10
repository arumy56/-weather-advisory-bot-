"""
DWAS Weather Advisory Telegram Bot
Listens for user town names or GPS location pins and delivers 3-day agronomic advisories.
"""

import logging
import os
import sys
from dotenv import load_dotenv
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from advisory import MSG, advise, forecast, geocode

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("dwas_bot")

TOKEN = os.getenv("TELEGRAM_TOKEN")


def get_lang(ctx: ContextTypes.DEFAULT_TYPE) -> str:
    return ctx.user_data.get("lang", "en")


def build_keyboard(lang: str) -> ReplyKeyboardMarkup:
    """Build quick-action keyboard including GPS share button and preset farming hubs."""
    loc_button_text = "📍 Shiriki Eneo (GPS)" if lang == "sw" else "📍 Share Location (GPS)"
    lang_toggle = "/en English" if lang == "sw" else "/sw Kiswahili"
    
    keyboard = [
        [KeyboardButton(loc_button_text, request_location=True)],
        [KeyboardButton("Nairobi"), KeyboardButton("Nakuru"), KeyboardButton("Eldoret")],
        [KeyboardButton(lang_toggle), KeyboardButton("/help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    lang = get_lang(ctx)
    reply_markup = build_keyboard(lang)
    await update.message.reply_text(
        MSG[lang]["welcome"],
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def help_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    lang = get_lang(ctx)
    if lang == "sw":
        text = (
            "📖 *Mwongozo wa Kutumia Bot hii:*\n\n"
            "1. Tuma jina la mji wako (k.m. *Eldoret*, *Kitale*, *Kisumu*).\n"
            "2. Au bonyeza kitufe cha '📍 Shiriki Eneo' kutuma GPS yako.\n"
            "3. Utapokea utabiri wa siku 3 pamoja na ushauri wa kilimo (mvua, kupiga dawa, mbolea, na umwagiliaji).\n\n"
            "• `/sw` - Badili lugha kuwa Kiswahili\n"
            "• `/en` - Badili lugha kuwa Kiingereza"
        )
    else:
        text = (
            "📖 *How to use this advisory bot:*\n\n"
            "1. Send any town or region name (e.g., *Eldoret*, *Nakuru*, *Machakos*).\n"
            "2. Or tap the '📍 Share Location' button to send your GPS coordinates.\n"
            "3. You'll receive a 3-day weather breakdown and tailored agronomic guidance for field operations.\n\n"
            "• `/en` - Switch to English\n"
            "• `/sw` - Badili kwenda Kiswahili"
        )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=build_keyboard(lang))


async def lang_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle language between English and Swahili."""
    cmd = update.message.text.lower()
    if "sw" in cmd:
        ctx.user_data["lang"] = "sw"
    else:
        ctx.user_data["lang"] = "en"
    await start_handler(update, ctx)


async def location_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle native GPS pin shared by user."""
    loc = update.message.location
    lang = get_lang(ctx)
    loading_msg = await update.message.reply_text("⏳ Generating farm advisory...")

    try:
        data = await forecast(loc.latitude, loc.longitude)
        coords_label = f"Lat {loc.latitude:.2f}, Lon {loc.longitude:.2f}"
        reply = advise(data, lang=lang, location_name=coords_label)
        await loading_msg.edit_text(reply, parse_mode=ParseMode.MARKDOWN)
    except Exception as exc:
        logger.error("Error fetching forecast for coordinates: %s", exc)
        await loading_msg.edit_text(MSG[lang]["api_error"])


async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-form town / region text input."""
    text = update.message.text.strip()
    lang = get_lang(ctx)

    # Check if text is switching language button
    if text.startswith("/sw") or "kiswahili" in text.lower():
        ctx.user_data["lang"] = "sw"
        return await start_handler(update, ctx)
    if text.startswith("/en") or "english" in text.lower():
        ctx.user_data["lang"] = "en"
        return await start_handler(update, ctx)
    if text.startswith("/help"):
        return await help_handler(update, ctx)

    loading_msg = await update.message.reply_text(f"🔍 Searching weather for '{text}'...")

    try:
        geo = await geocode(text)
        if not geo:
            return await loading_msg.edit_text(MSG[lang]["notfound"].format(query=text))

        lat, lon, display_name = geo
        data = await forecast(lat, lon)
        reply = advise(data, lang=lang, location_name=display_name)
        await loading_msg.edit_text(reply, parse_mode=ParseMode.MARKDOWN)
    except Exception as exc:
        logger.error("Error processing text query '%s': %s", text, exc)
        await loading_msg.edit_text(MSG[lang]["api_error"])


def main() -> None:
    if not TOKEN:
        logger.error("TELEGRAM_TOKEN environment variable is missing. Set it in .env or your environment.")
        sys.exit(1)

    app = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler(["sw", "en"], lang_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    logger.info("Starting DWAS Weather Advisory Telegram Bot polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
