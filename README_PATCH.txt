Исправленный патч под блок "Контроль выполнения".

Чинит:
1. ImportError: cannot import name 'confirm_done'
2. Добавляет функции:
   - confirm_done
   - return_to_work
   - mark_in_progress
   - set_overdue
3. Исправляет выборки статусов в services/reminders.py
4. Сохраняет подтверждение выполнения / возврат в работу / просрочки

Заменить файлы:
- app/db.py
- app/services/reminders.py
- app/utils/formatting.py
- app/keyboards/reminders.py
- app/handlers/reminder_actions.py
- app/handlers/menu.py
- app/scheduler.py
