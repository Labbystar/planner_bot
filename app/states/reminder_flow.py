from aiogram.fsm.state import State, StatesGroup


class ReminderFlow(StatesGroup):
    waiting_for_text = State()
    waiting_for_category = State()
    waiting_for_priority = State()
    waiting_for_pre_remind = State()
    waiting_for_recipients = State()
    waiting_for_recipients_manual = State()
    waiting_for_interval_hours = State()
    waiting_for_date = State()
    waiting_for_weekday = State()
    waiting_for_time = State()
    waiting_for_when = State()


class GroupFlow(StatesGroup):
    waiting_for_name = State()
    waiting_for_members = State()


class TemplateFlow(StatesGroup):
    waiting_for_name = State()
