
# ВАЖНО: заменить только блок шагов 6-7

from app.utils.datetime_parser import parse_time_input, parse_date_input

user_temp_time = {}

async def handle_time_step(message, state):
    parsed = parse_time_input(message.text)
    if not parsed:
        await message.answer("Не понял время. Пример: 13:45 или 13-45")
        return

    h, m = parsed
    user_temp_time[message.from_user.id] = (h, m)

    await message.answer(
        "Шаг 7/7\nУкажи дату\nПример: 25.03.26"
    )
    await state.set_state("waiting_for_date")


async def handle_date_step(message, state):
    parsed_date = parse_date_input(message.text)
    if not parsed_date:
        await message.answer("Не понял дату. Пример: 25.03.26")
        return

    user_id = message.from_user.id
    h, m = user_temp_time.get(user_id, (9,0))

    final_dt = parsed_date.replace(hour=h, minute=m)

    # дальше использовать final_dt как deadline

    await message.answer(f"Понял: {final_dt.strftime('%d.%m.%Y %H:%M')}")

    # сохранить задачу дальше...
