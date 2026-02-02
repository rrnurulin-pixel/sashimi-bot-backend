# server.py — webhook-версия бота на FastAPI + aiogram 3.x

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Update, Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram import F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import os
from dotenv import load_dotenv
import logging
import base64
import json

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
KASPI_PHONE = os.getenv("KASPI_PHONE")

if not all([BOT_TOKEN, ADMIN_ID, KASPI_PHONE]):
    raise ValueError("Не указаны BOT_TOKEN, ADMIN_ID или KASPI_PHONE в .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

WEBHOOK_PATH = "/webhook"
# Замени на реальный домен после деплоя
WEBHOOK_URL = "https://твой-домен.vercel.app/webhook"  # ← здесь твой домен

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "Bot is running"}

@dp.message(CommandStart(deep_link=True))
async def start_with_order(message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].startswith('order_'):
        await message.answer("Добро пожаловать в SaShimi!")
        return

    try:
        encoded = args[1].replace('order_', '')
        decoded = base64.urlsafe_b64decode(encoded + '===').decode('utf-8')
        order = json.loads(decoded)
    except Exception as e:
        await message.answer("Ошибка обработки заказа.")
        logging.error(e)
        return

    items = "\n".join([f"{item['name']} × {item['qty']}" for item in order['items']])
    total = order['total']

    text = f"""Новый заказ!

Товары:
{items}

Сумма: {total} ₸

Переведите на Kaspi: {KASPI_PHONE}

После оплаты пришлите скриншот / фото чека в этот чат."""

    await message.answer(text)

@dp.message(F.photo)
async def handle_photo(message: Message):
    photo_id = message.photo[-1].file_id

    caption = f"Новый чек от @{message.from_user.username} (ID: {message.from_user.id})"

    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=caption
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("Принять", callback_data=f"accept_{message.from_user.id}"),
            InlineKeyboardButton("Отменить", callback_data=f"cancel_{message.from_user.id}"),
        ]
    ])

    await bot.send_message(ADMIN_ID, "Действие с заказом:", reply_markup=keyboard)

@dp.callback_query()
async def handle_admin_action(callback: CallbackQuery):
    action, user_id = callback.data.split('_')
    user_id = int(user_id)

    if action == 'accept':
        await bot.send_message(user_id, "Ваш заказ принят!\nСкоро свяжутся.")
        await callback.message.edit_text(callback.message.text + "\n\n✅ Принят")
    elif action == 'cancel':
        await bot.send_message(user_id, "Ваш заказ отменён.")
        await callback.message.edit_text(callback.message.text + "\n\n❌ Отменён")

    await callback.answer()

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    update_dict = await request.json()
    update = Update.de_json(update_dict, bot)
    await dp.feed_update(bot, update)
    return {"ok": True}

async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook установлен: {WEBHOOK_URL}")

async def on_shutdown():
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()

if __name__ == "__main__":
    import uvicorn
    asyncio.run(on_startup())
    uvicorn.run(app, host="0.0.0.0", port=8000)
