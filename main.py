from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
import sqlite3
import asyncio

API_TOKEN = '7351910412:AAFDKQ7y7zSnX9R3YoReGvYJ78RvWx8s5yc'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Подключение к БД
conn = sqlite3.connect("shop.db")
cursor = conn.cursor()

# Создание таблиц
cursor.execute('''
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    price INTEGER,
    category_id INTEGER,
    FOREIGN KEY (category_id) REFERENCES categories(id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS cart (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER,
    FOREIGN KEY (product_id) REFERENCES catalog(id)
)
''')

conn.commit()

# Главное меню
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="🛒 Корзина")]
        ],
        resize_keyboard=True
    )

# Обработчик команды /start
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer("👋 Привет! Это бот-магазин. Выберите действие:", reply_markup=main_menu())

# Обработчик кнопки "🔙 Назад"
@dp.message(lambda message: message.text == "🔙 Назад")
async def go_back(message: types.Message):
    await message.answer("🔙 Вы вернулись в главное меню", reply_markup=main_menu())

# Показ корзины
@dp.message(lambda message: message.text == "🛒 Корзина")
async def show_cart(message: types.Message):
    try:
        cursor.execute("""
            SELECT catalog.name, catalog.price
            FROM cart
            JOIN catalog ON cart.product_id = catalog.id
            WHERE cart.user_id = ?
        """, (message.from_user.id,))

        items = cursor.fetchall()

        if not items:
            await message.answer("🛒 Ваша корзина пуста!")
            await message.answer("Вы можете вернуться в каталог и добавить товары.", reply_markup=main_menu())
            return

        total = sum(item[1] for item in items)
        text = "\n".join([f"{item[0]} - {item[1]} сом" for item in items])
        text += f"\n\n💰 Итого: {total} сом"

        keyboard = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="✅ Оформить заказ")],
            [KeyboardButton(text="📝 Редактировать"), KeyboardButton(text="🔙 Назад")]
        ], resize_keyboard=True)

        await message.answer(f"🛒 Ваша корзина:\n\n{text}", reply_markup=keyboard)

    except Exception as e:
        print(f"Ошибка при получении корзины: {e}")
        await message.answer("❌ Произошла ошибка при получении корзины.")


# Редактирование корзины
@dp.message(lambda message: message.text == "📝 Редактировать")
async def edit_cart(message: types.Message):
    try:
        # Получаем товары из корзины пользователя
        cursor.execute("""
            SELECT catalog.id, catalog.name
            FROM cart
            JOIN catalog ON cart.product_id = catalog.id
            WHERE cart.user_id = ?
        """, (message.from_user.id,))

        items = cursor.fetchall()

        # Логируем товары для отладки
        print(f"Товары в корзине для пользователя {message.from_user.id}: {items}")

        # Если корзина пуста, показываем сообщение и выходим
        if not items:
            await message.answer("❌ Ваша корзина пуста!")
            return

        # Если корзина не пуста, создаем клавиатуру с кнопками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for item in items:
            keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"❌ {item[1]}", callback_data=f"remove_{item[0]}")])

        # Отправляем сообщение с клавиатурой
        await message.answer("Выберите товар для удаления:", reply_markup=keyboard)

    except Exception as e:
        # Логируем ошибку
        print(f"Ошибка при редактировании корзины: {e}")
        await message.answer("❌ Произошла ошибка при редактировании корзины.")


# Удаление товара из корзины
@dp.callback_query(lambda c: c.data.startswith("remove_"))
async def remove_from_cart(callback: types.CallbackQuery):
    try:
        product_id = int(callback.data[7:])  # Извлекаем ID товара из callback_data

        # Удаляем товар только для конкретного пользователя
        cursor.execute("DELETE FROM cart WHERE user_id = ? AND product_id = ? LIMIT 1", (callback.from_user.id, product_id))
        conn.commit()

        await callback.answer("✅ Товар удалён из корзины!")

        # Обновляем корзину после удаления товара
        cursor.execute("""
            SELECT catalog.id, catalog.name
            FROM cart
            JOIN catalog ON cart.product_id = catalog.id
            WHERE cart.user_id = ?
        """, (callback.from_user.id,))

        items = cursor.fetchall()

        if not items:
            await callback.message.edit_text("❌ Ваша корзина пуста!")
            return

        # Если корзина не пуста, создаем клавиатуру с кнопками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for item in items:
            keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"❌ {item[1]}", callback_data=f"remove_{item[0]}")])

        # Обновляем сообщение с клавиатурой
        await callback.message.edit_text("Выберите товар для удаления:", reply_markup=keyboard)

    except Exception as e:
        print(f"Ошибка при удалении товара из корзины: {e}")
        await callback.answer("❌ Произошла ошибка при удалении товара из корзины.")


# Оформление заказа (создание чека)
@dp.message(lambda message: message.text == "✅ Оформить заказ")
async def checkout(message: types.Message):
    try:
        cursor.execute("""
            SELECT catalog.name, catalog.price
            FROM cart
            JOIN catalog ON cart.product_id = catalog.id
            WHERE cart.user_id = ?
        """, (message.from_user.id,))

        items = cursor.fetchall()

        if not items:
            await message.answer("❌ Ваша корзина пуста! Добавьте товары перед оформлением заказа.")
            return

        total = sum(item[1] for item in items)
        receipt = "\n".join([f"{item[0]} - {item[1]} сом" for item in items])
        receipt += f"\n\n💰 Итого: {total} сом"

        await message.answer(f"🧾 Ваш чек:\n\n{receipt}\n\n✅ Спасибо за покупку!", reply_markup=main_menu())

        # Очистка корзины после оформления заказа
        cursor.execute("DELETE FROM cart WHERE user_id = ?", (message.from_user.id,))
        conn.commit()

    except Exception as e:
        print(f"Ошибка при оформлении заказа: {e}")
        await message.answer("❌ Произошла ошибка при оформлении заказа.")


# Показ категорий товаров
@dp.message(lambda message: message.text == "🛍 Каталог")
async def show_categories(message: types.Message):
    try:
        cursor.execute("SELECT name FROM categories")
        categories = cursor.fetchall()

        if not categories:
            await message.answer("❌ Нет доступных категорий!")
            return

        # Создание клавиатуры с категориями
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[])  # создаем пустой список для клавиш
        for category in categories:
            keyboard.keyboard.append([KeyboardButton(text=category[0])])  # Добавляем категорию как строку в список кнопок

        keyboard.keyboard.append([KeyboardButton(text="🔙 Назад")])  # Добавляем кнопку "Назад"

        await message.answer("Выберите категорию:", reply_markup=keyboard)

    except Exception as e:
        print(f"Ошибка при получении категорий: {e}")
        await message.answer("❌ Произошла ошибка при загрузке категорий.")

# Показ товаров в категории
@dp.message(lambda message: message.text not in ["🛍 Каталог", "🔙 Назад", "🛒 Корзина"])
async def show_products(message: types.Message):
    try:
        cursor.execute("SELECT id FROM categories WHERE name = ?", (message.text,))
        category = cursor.fetchone()

        if category:
            cursor.execute("SELECT name, price FROM catalog WHERE category_id = ?", (category[0],))
            products = cursor.fetchall()

            if not products:
                await message.answer("❌ В этой категории нет товаров.")
                return

            # Создание клавиатуры с товарами
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            for product in products:
                # Добавляем кнопку для каждого товара
                keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"{product[0]} - {product[1]} сом", callback_data=f"add_{product[0]}")])

            # Добавляем кнопку "Назад"
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_categories")])

            await message.answer("Выберите товар для добавления в корзину:", reply_markup=keyboard)
        else:
            await message.answer("❌ Эта категория не существует!")

    except Exception as e:
        print(f"Ошибка при получении товаров: {e}")
        await message.answer("❌ Произошла ошибка при загрузке товаров.")

#Добавление в корзину
@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    try:
        product_name = callback.data[4:]

        cursor.execute("SELECT id FROM catalog WHERE name = ?", (product_name,))
        product = cursor.fetchone()

        if product:
            cursor.execute("INSERT INTO cart (user_id, product_id) VALUES (?, ?)", (callback.from_user.id, product[0]))
            conn.commit()
            await callback.answer(f"✅ {product_name} добавлен в корзину!")
        else:
            await callback.answer("❌ Этот товар не существует.")

    except Exception as e:
        print(f"Ошибка при добавлении товара в корзину: {e}")
        await callback.answer("❌ Произошла ошибка при добавлении товара в корзину.")

#Обработчик кнопки "🔙 Назад" в категориях
@dp.callback_query(lambda c: c.data == "back_to_categories")
async def back_to_categories(callback: types.CallbackQuery):
    await show_categories(callback.message)

#Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

