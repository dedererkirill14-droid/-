import asyncio
import html
import logging
import os
import random
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ==========================================
# 1. КОНФИГУРАЦИЯ И ДАННЫЕ
# ==========================================
# Токен берётся из переменной окружения BOT_TOKEN, либо вставьте его ниже.
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТЕЛЕГРАМ_ТОКЕН")
DB_NAME = "bot_database.db"

MONTHS_DATA = {
    1: {"name": "Январь", "season": "Зима", "products": {"🍊 Фрукты": "Мандарины, хурма, гранат", "🥕 Овощи": "Репа, тыква, корневой сельдерей"}},
    2: {"name": "Февраль", "season": "Зима", "products": {"🍊 Фрукты": "Помело, киви, апельсины", "🥕 Овощи": "Капуста белокочанная, лук-порей"}},
    3: {"name": "Март", "season": "Весна", "products": {"🍊 Фрукты": "Лимоны, грейпфруты", "🥕 Овощи": "Редис, репчатый лук, топинамбур"}},
    4: {"name": "Апрель", "season": "Весна", "products": {"🌱 Зелень": "Черемша, шпинат, щавель", "🥕 Овощи": "Молодая капуста, редис"}},
    5: {"name": "Май", "season": "Весна", "products": {"🍓 Ягоды": "Клубника", "🌱 Зелень": "Спаржа, салат айсберг, ревень"}},
    6: {"name": "Июнь", "season": "Лето", "products": {"🍓 Ягоды": "Черешня, земляника", "🥕 Овощи": "Кабачки, молодой картофель, огурцы"}},
    7: {"name": "Июль", "season": "Лето", "products": {"🍓 Ягоды": "Малина, черника, смородина", "🥕 Овощи": "Томаты, болгарский перец, баклажаны"}},
    8: {"name": "Август", "season": "Лето", "products": {"🍉 Бахча": "Арбузы, дыни", "🍓 Ягоды": "Брусника", "🥕 Овощи": "Кукуруза, молодой чеснок"}},
    9: {"name": "Сентябрь", "season": "Осень", "products": {"🍏 Фрукты": "Яблоки, груши, сливы", "🍄 Грибы": "Лисички, белые грибы"}},
    10: {"name": "Октябрь", "season": "Осень", "products": {"🍏 Фрукты": "Инжир, виноград", "🥕 Овощи": "Тыква, брюква, цветная капуста"}},
    11: {"name": "Ноябрь", "season": "Осень", "products": {"🍏 Фрукты": "Фейхоа, хурма", "🥕 Овощи": "Клюква, сельдерей, пастернак"}},
    12: {"name": "Декабрь", "season": "Зима", "products": {"🍊 Фрукты": "Мандарины, личи", "🥕 Овощи": "Редька, квашеная капуста"}},
}

RECIPES = {
    "Тыква": [
        "🎃 Крем-суп: запеките тыкву с луком и чесноком, пробейте блендером со сливками.",
        "🎃 Запечённая тыква: нарежьте кубиками, полейте мёдом, посыпьте корицей и запекайте 20 минут.",
    ],
    "Кабачки": [
        "🥒 Оладьи: натрите кабачок, отожмите сок, добавьте 1 яйцо, 2 ст.л. муки и обжарьте.",
        "🥒 Рулетики: нарежьте слайсами, обжарьте, заверните внутрь творожный сыр с чесноком.",
    ],
    "Мандарины": [
        "🍊 Пряный десерт: очистите мандарины, прогрейте в сотейнике с сахаром, корицей и бадьяном 5 минут.",
    ],
    "Хурма": [
        "🥗 Салат: микс салата + дольки хурмы + кубики феты + кедровые орешки. Заправить маслом.",
    ],
}


# ==========================================
# 2. БАЗА ДАННЫХ
# ==========================================
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                recipe_text TEXT,
                UNIQUE(user_id, recipe_text),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
            """
        )
        conn.commit()


def _register_user(user_id: int, username: str | None, first_name: str | None):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username or "unknown", first_name or "User"),
        )
        conn.commit()


def _add_to_favorites(user_id: int, recipe_text: str) -> bool:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO favorites (user_id, recipe_text) VALUES (?, ?)",
            (user_id, recipe_text),
        )
        conn.commit()
        return cur.rowcount > 0


def _get_favorites(user_id: int) -> list[str]:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("SELECT recipe_text FROM favorites WHERE user_id = ?", (user_id,))
        return [row[0] for row in cur.fetchall()]


def _clear_favorites(user_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM favorites WHERE user_id = ?", (user_id,))
        conn.commit()


# Обёртки, чтобы sqlite не блокировал event loop
async def register_user(user_id, username, first_name):
    await asyncio.to_thread(_register_user, user_id, username, first_name)


async def add_to_favorites(user_id, recipe_text) -> bool:
    return await asyncio.to_thread(_add_to_favorites, user_id, recipe_text)


async def get_favorites(user_id) -> list[str]:
    return await asyncio.to_thread(_get_favorites, user_id)


async def clear_favorites(user_id):
    await asyncio.to_thread(_clear_favorites, user_id)


# ==========================================
# 3. КЛАВИАТУРЫ
# ==========================================
def get_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Что в сезоне сейчас?", callback_data="season_now")],
            [InlineKeyboardButton(text="📅 Выбрать конкретный месяц", callback_data="choose_month")],
            [InlineKeyboardButton(text="⭐ Моё Избранное", callback_data="my_favorites")],
        ]
    )


def get_months_keyboard() -> InlineKeyboardMarkup:
    keyboard, row = [], []
    for num, data in MONTHS_DATA.items():
        row.append(InlineKeyboardButton(text=data["name"], callback_data=f"month_{num}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="↩️ В главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_products_keyboard(products_list: list[str]) -> InlineKeyboardMarkup:
    keyboard = []
    joined = " ".join(products_list).lower()
    for prod in RECIPES:
        if prod.lower() in joined:
            keyboard.append([InlineKeyboardButton(text=f"🍳 Рецепт из: {prod}", callback_data=f"recipe_{prod}")])
    keyboard.append([InlineKeyboardButton(text="↩️ Назад к месяцам", callback_data="choose_month")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_save_recipe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❤️ Сохранить в избранное", callback_data="save_to_fav")],
            [InlineKeyboardButton(text="↩️ Главное меню", callback_data="main_menu")],
        ]
    )


def get_favorites_keyboard(has_items: bool) -> InlineKeyboardMarkup:
    keyboard = []
    if has_items:
        keyboard.append([InlineKeyboardButton(text="🗑 Очистить избранное", callback_data="clear_favorites")])
    keyboard.append([InlineKeyboardButton(text="↩️ Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ==========================================
# 4. ЛОГИКА И ХЭНДЛЕРЫ
# ==========================================
logging.basicConfig(level=logging.INFO)
dp = Dispatcher()


class BotStates(StatesGroup):
    viewing_recipe = State()


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    """edit_text, который не падает на 'message is not modified'."""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    name = html.escape(message.from_user.first_name or "друг")
    await message.answer(
        f"🍏 <b>Добро пожаловать в SmartSeason Бот, {name}!</b>\n\n"
        "Я помогаю находить самые свежие и полезные продукты прямо сейчас, "
        "а также предлагаю вкусные рецепты из них.\n\n"
        "Используйте интерактивное меню ниже:",
        reply_markup=get_main_menu(),
    )


@dp.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(callback, "Вы в главном меню. Выберите интересующий раздел:", get_main_menu())
    await callback.answer()


@dp.callback_query(F.data == "choose_month")
async def callback_choose_month(callback: CallbackQuery):
    await safe_edit(callback, "📅 Выберите месяц, чтобы узнать, что созревает в этот период:", get_months_keyboard())
    await callback.answer()


async def send_month_info(callback: CallbackQuery, month_num: int):
    info = MONTHS_DATA[month_num]
    text = f"📅 <b>Месяц:</b> {info['name']} ({info['season']})\n\n🥦 <b>Сезонные продукты:</b>\n"
    all_products = []
    for cat, prods in info["products"].items():
        text += f"📍 <i>{cat}:</i> {prods}\n"
        all_products.append(prods)
    await safe_edit(callback, text, get_products_keyboard(all_products))
    await callback.answer()


@dp.callback_query(F.data == "season_now")
async def callback_season_now(callback: CallbackQuery):
    await send_month_info(callback, datetime.now().month)


@dp.callback_query(F.data.startswith("month_"))
async def callback_specific_month(callback: CallbackQuery):
    month_num = int(callback.data.split("_", 1)[1])
    if month_num not in MONTHS_DATA:
        await callback.answer("Неизвестный месяц", show_alert=True)
        return
    await send_month_info(callback, month_num)


@dp.callback_query(F.data.startswith("recipe_"))
async def callback_get_recipe(callback: CallbackQuery, state: FSMContext):
    product = callback.data.split("_", 1)[1]
    recipes_list = RECIPES.get(product, [])
    if not recipes_list:
        await callback.answer("Рецепты для этого продукта ещё обновляются!", show_alert=True)
        return
    chosen = random.choice(recipes_list)
    await state.update_data(current_recipe=chosen)
    await state.set_state(BotStates.viewing_recipe)
    await safe_edit(
        callback,
        f"🧑‍🍳 <b>Рецепт с ингредиентом [{product}]:</b>\n\n{chosen}",
        get_save_recipe_keyboard(),
    )
    await callback.answer()


@dp.callback_query(BotStates.viewing_recipe, F.data == "save_to_fav")
async def callback_save_to_favorites(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    recipe = data.get("current_recipe")
    if recipe:
        added = await add_to_favorites(callback.from_user.id, recipe)
        msg = "❤️ Рецепт добавлен в избранное!" if added else "Этот рецепт уже в избранном."
        await callback.answer(msg, show_alert=True)
        await state.clear()
        await safe_edit(callback, "Выберите следующее действие:", get_main_menu())
    else:
        await callback.answer("Рецепт не найден, откройте его заново.", show_alert=True)


@dp.callback_query(F.data == "save_to_fav")
async def callback_save_no_state(callback: CallbackQuery):
    # Состояние потерялось (например, после перезапуска бота)
    await callback.answer("Сессия устарела — откройте рецепт заново.", show_alert=True)


@dp.callback_query(F.data == "my_favorites")
async def callback_show_favorites(callback: CallbackQuery):
    favs = await get_favorites(callback.from_user.id)
    if favs:
        text = "⭐ <b>Ваше избранное:</b>\n\n" + "\n\n".join(f"{i}. {html.escape(r)}" for i, r in enumerate(favs, 1))
    else:
        text = "⭐ В избранном пока пусто. Откройте любой рецепт и нажмите «Сохранить»."
    await safe_edit(callback, text, get_favorites_keyboard(bool(favs)))
    await callback.answer()


@dp.callback_query(F.data == "clear_favorites")
async def callback_clear_favorites(callback: CallbackQuery):
    await clear_favorites(callback.from_user.id)
    await callback.answer("Избранное очищено", show_alert=False)
    await safe_edit(
        callback,
        "⭐ В избранном пока пусто. Откройте любой рецепт и нажмите «Сохранить».",
        get_favorites_keyboard(False),
    )


# ==========================================
# 5. ЗАПУСК
# ==========================================
async def main():
    if BOT_TOKEN == "ВАШ_ТЕЛЕГРАМ_ТОКЕН":
        raise SystemExit("Укажите токен: переменная окружения BOT_TOKEN или константа в коде.")
    init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
