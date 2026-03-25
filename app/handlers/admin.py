
from aiogram import Router, F
from aiogram.types import Message
from app.services.users import set_role, list_users

router = Router()

@router.message(F.text == "👑 Админка")
async def admin_panel(message: Message):
    await message.answer("👑 Админка\nИспользуй команду:\n/setrole USER_ID admin|manager|user")

@router.message(F.text.startswith("/setrole"))
async def set_role_cmd(message: Message):
    try:
        _, user_id, role = message.text.split()
        await set_role(int(user_id), role)
        await message.answer(f"Роль обновлена: {user_id} → {role}")
    except:
        await message.answer("Ошибка формата. Пример: /setrole 123 admin")
