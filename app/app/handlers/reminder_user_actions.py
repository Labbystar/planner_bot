from aiogram import Router, F
from aiogram.types import CallbackQuery
from app.repositories.user_statuses import set_status
from app.utils.user_statuses import *

DB_PATH = "planner.db"

router = Router()

@router.callback_query(F.data.startswith("read_"))
async def mark_read(callback: CallbackQuery):
    rid = int(callback.data.split("_")[1])
    await set_status(DB_PATH, rid, callback.from_user.id, STATUS_READ)
    await callback.answer("Отмечено")

@router.callback_query(F.data.startswith("done_"))
async def mark_done(callback: CallbackQuery):
    rid = int(callback.data.split("_")[1])
    await set_status(DB_PATH, rid, callback.from_user.id, STATUS_DONE)
    await callback.answer("Выполнено")

@router.callback_query(F.data.startswith("fail_"))
async def mark_fail(callback: CallbackQuery):
    rid = int(callback.data.split("_")[1])
    await set_status(DB_PATH, rid, callback.from_user.id, STATUS_FAILED)
    await callback.answer("Отмечено")

@router.callback_query(F.data.startswith("snooze_"))
async def mark_snooze(callback: CallbackQuery):
    rid = int(callback.data.split("_")[1])
    await set_status(DB_PATH, rid, callback.from_user.id, STATUS_SNOOZED)
    await callback.answer("Отложено")
