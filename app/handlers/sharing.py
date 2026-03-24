from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from app.context import AppContext

router = Router()


@router.message(Command("sharecopy"))
async def cmd_sharecopy(message: Message, command: CommandObject, app: AppContext) -> None:
    if not command.args or not command.args.isdigit():
        await message.answer("Формат: /sharecopy ID")
        return
    reminder_id = int(command.args)
    try:
        link = await app.sharing_service.create_share_link(message.from_user.id, reminder_id, "copy")
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await message.answer(f"Ссылка для копии:\n{link}")


@router.message(Command("sharerecipient"))
async def cmd_sharerecipient(message: Message, command: CommandObject, app: AppContext) -> None:
    if not command.args or not command.args.isdigit():
        await message.answer("Формат: /sharerecipient ID")
        return
    reminder_id = int(command.args)
    try:
        link = await app.sharing_service.create_share_link(message.from_user.id, reminder_id, "recipient")
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await message.answer(f"Ссылка для подписки на исходное напоминание:\n{link}")


@router.message(Command("myshares"))
async def cmd_myshares(message: Message, app: AppContext) -> None:
    shares = await app.shares_repo.list_user_shares(message.from_user.id)
    if not shares:
        await message.answer("Активных share-ссылок нет")
        return

    lines = []
    for share in shares:
        if app.config.bot_username:
            link = f"https://t.me/{app.config.bot_username}?start=share_{share.token}"
        else:
            link = f"share_{share.token}"
        lines.append(
            f"Reminder ID: {share.reminder_id}\n"
            f"Режим: {share.share_mode}\n"
            f"Токен: {share.token}\n"
            f"Ссылка: {link}"
        )
    await message.answer("\n\n".join(lines))


@router.message(Command("unshare"))
async def cmd_unshare(message: Message, command: CommandObject, app: AppContext) -> None:
    if not command.args:
        await message.answer("Формат: /unshare TOKEN")
        return
    token = command.args.strip().replace("share_", "")
    ok = await app.shares_repo.deactivate_share_by_token(token, message.from_user.id)
    await message.answer("Ссылка отключена" if ok else "Ссылка не найдена")


@router.callback_query(F.data.startswith("share_accept:"))
async def cb_share_accept(callback: CallbackQuery, app: AppContext) -> None:
    token = callback.data.split(":", 1)[1]
    try:
        result = await app.sharing_service.accept_share(token, callback.from_user.id, app.bot)
    except ValueError as exc:
        await callback.message.answer(str(exc))
        await callback.answer()
        return

    await callback.message.answer(result)
    await callback.answer("Готово")


@router.callback_query(F.data == "share_cancel")
async def cb_share_cancel(callback: CallbackQuery) -> None:
    await callback.message.answer("Принятие share-ссылки отменено")
    await callback.answer()
