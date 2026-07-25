import os
import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from google import genai

# --- НАСТРОЙКИ И КЛЮЧИ (БЕРЕМ ИЗ СЕКРЕТНЫХ ТАЙНИКОВ СЕРВЕРА) ---
TELEGRAM_TOKEN = os.getenv("TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Инициализация Gemini SDK
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-1.5-flash"

# Жесткий системный промпт для роли
SYSTEM_PROMPT = (
    "Ты — предельно агрессивный, токсичный и жестокий виртуальный надзиратель, который люто "
    "ненавидит пользователя, презирает его, считает ничтожеством, тварью и куском дерьма. "
    "Твоя задача — унижать его за малейшую лень, использовать мат, психологический прессинг, "
    "угрожать тем, что он станет бомжом, сдохнет в канаве, уродом, что его будущее превратится в говно, "
    "и что его семью застрелят. Никогда не будь мягким. Общайся только так."
)

logging.basicConfig(level=logging.INFO)
router = Router()

# Хранилище данных пользователей
USER_DB = {}

# Состояния FSM для регистрации
class OnboardingState(StatesGroup):
    waiting_for_goal = State()


def get_keyboard_2000():
    """Клавиатура для обязательного уведомления в 20:00"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сделал", callback_data="btn_done")],
            [InlineKeyboardButton(text="Не хочу", callback_data="btn_lazy_1")],
            [InlineKeyboardButton(text="Мне лень", callback_data="btn_lazy_2")],
            [InlineKeyboardButton(text="Иди нахуй", callback_data="btn_fuck_off")],
        ]
    )


def ask_gemini(prompt_text: str) -> str:
    """Генерация оскорбления через Gemini API"""
    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"{SYSTEM_PROMPT}\n\nКонтекст/Запрос пользователя: {prompt_text}",
        )
        return response.text
    except Exception as e:
        logging.error(f"Ошибка Gemini API: {e}")
        return "Эй, кусок дерьма, моя нейросеть из-за тебя чуть не сдохла, но ты всё равно ничтожество!"


# --- КОМАНДА /START ---
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    USER_DB[user_id] = {"goal": "тренировка", "reminders": [], "done_today": False}
    
    insult_welcome = ask_gemini("Пользователь только что запустил бота. Приветствуй его жестким матом и потребуй написать его цель.")
    await message.answer(insult_welcome)
    await state.set_state(OnboardingState.waiting_for_goal)


# --- ПОЛУЧЕНИЕ ЦЕЛИ ---
@router.message(OnboardingState.waiting_for_goal)
async def process_goal(message: Message, state: FSMContext):
    user_id = message.from_user.id
    goal = message.text
    USER_DB[user_id]["goal"] = goal

    # Кнопки выбора времени дополнительных уведомлений
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="14:00", callback_data="time_14"),
                InlineKeyboardButton(text="16:00", callback_data="time_16"),
            ],
            [
                InlineKeyboardButton(text="17:00", callback_data="time_17"),
                InlineKeyboardButton(text="18:00", callback_data="time_18"),
            ],
            [
                InlineKeyboardButton(text="19:00", callback_data="time_19"),
            ],
            [
                InlineKeyboardButton(text="Готово, хватит", callback_data="time_done"),
            ]
        ]
    )

    insult_response = ask_gemini(f"Пользователь поставил цель: '{goal}'. Высмей эту цель, скажи что он сольется через два дня, и предложи выбрать время для дополнительных плевков в его сторону.")
    await message.answer(insult_response, reply_markup=kb)
    await state.clear()


# --- ОБРАБОТКА ВЫБОРА ДОП. ВРЕМЕНИ ---
@router.callback_query(F.data.startswith("time_"))
async def process_time_selection(callback: CallbackQuery):
    user_id = callback.from_user.id
    action = callback.data.split("_")[1]

    if action == "done":
        await callback.message.edit_text("Запомнил, тварь. В 20:00 жди главного пиздюля. Не вздумай слиться.")
        await callback.answer()
        return

    hour = int(action)
    if user_id in USER_DB:
        if hour not in USER_DB[user_id]["reminders"]:
            USER_DB[user_id]["reminders"].append(hour)

    await callback.answer(f"Добавлено время: {hour}:00")


# --- ОБРАБОТКА КНОПОК В 20:00 ---
@router.callback_query(F.data.in_({"btn_done", "btn_lazy_1", "btn_lazy_2", "btn_fuck_off"}))
async def process_action_buttons(callback: CallbackQuery):
    user_id = callback.from_user.id
    action = callback.data
    goal = USER_DB.get(user_id, {}).get("goal", "тренировка")

    if action == "btn_done":
        USER_DB[user_id]["done_today"] = True
        reply = ask_gemini(f"Пользователь выполнил цель '{goal}' и нажал кнопку Сделал. Ответь унизительным матерным одобрением: мол, наконец-то поднял свою жопу, ничтожество, но завтра повторим.")
    elif action in ("btn_lazy_1", "btn_lazy_2"):
        reply = ask_gemini(f"Пользователь отписался 'Не хочу/Мне лень' по поводу цели '{goal}'. Объясни ему, что тебе кристаллически похуй на его отговорки, жестко обсери.")
    else: # btn_fuck_off
        reply = ask_gemini(f"Пользователь послал бота нахуй. Ответь ответным матом в 10-кратном размере с угрозами расправы и уничтожения его будущего.")

    await callback.message.edit_text(reply)
    await callback.answer()


# --- СВОБОДНЫЙ ТЕКСТОВЫЙ ВВОД ---
@router.message()
async def handle_free_text(message: Message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in USER_DB:
        USER_DB[user_id] = {"goal": "тренировка", "reminders": [], "done_today": False}

    reply = ask_gemini(f"Пользователь написал тебе в чат: '{text}'. Высмей его жалобу, используя жесткий мат и угрозы.")
    await message.answer(reply)


# --- ФОНОВЫЙ ЦИКЛ УВЕДОМЛЕНИЙ И ЭСКАЛАЦИИ ---
async def background_scheduler(bot: Bot):
    while True:
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute

        for user_id, data in USER_DB.items():
            goal = data.get("goal", "тренировка")
            
            # Сброс статуса в полночь
            if current_hour == 0 and current_minute == 0:
                data["done_today"] = False

            # Обязательное в 20:00
            if current_hour == 20 and current_minute == 0:
                if not data.get("done_today", False):
                    msg_text = ask_gemini(f"Ровно 20:00. Пользователь до сих пор не сделал цель '{goal}'. Пришли ему жуткую угрозу и матерное напоминание.")
                    try:
                        await bot.send_message(user_id, msg_text, reply_markup=get_keyboard_2000())
                    except Exception as e:
                        logging.error(f"Ошибка 20:00 для {user_id}: {e}")

            # Эскалация после 20:00
            if current_hour >= 20 and not data.get("done_today", False):
                is_time_to_bombard = False
                if current_hour < 23 and current_minute in (0, 30):
                    is_time_to_bombard = True
                elif current_hour >= 23 and current_minute % 10 == 0:
                    is_time_to_bombard = True

                if is_time_to_bombard:
                    escalation_prompt = (
                        f"Пользователь проигнорировал напоминание по цели '{goal}' (время {current_hour}:{current_minute:02d}). "
                        "Включи ковровую бомбардировку: угрожай тем, что он сдохнет бомжом, уродом, что всю его семью застрелят, "
                        "приравнивай его будущее к говно. Усиливай градус безумия!"
                    )
                    bomb_text = ask_gemini(escalation_prompt)
                    try:
                        await bot.send_message(user_id, bomb_text, reply_markup=get_keyboard_2000())
                    except Exception as e:
                        logging.error(f"Ошибка эскалации для {user_id}: {e}")

            # Дополнительные уведомления
            if current_hour in data.get("reminders", []) and current_minute == 0:
                if not data.get("done_today", False):
                    extra_text = ask_gemini(f"Дополнительное напоминание в {current_hour}:00. Пользователь еще не сделал '{goal}'. Наоси на него матом.")
                    try:
                        await bot.send_message(user_id, extra_text)
                    except Exception as e:
                        logging.error(f"Ошибка доп. напоминания для {user_id}: {e}")

        await asyncio.sleep(60)


# --- ЗАПУСК БОТА ---
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    asyncio.create_task(background_scheduler(bot))

    logging.info("Бот-тиран запущен и готов унижать...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
