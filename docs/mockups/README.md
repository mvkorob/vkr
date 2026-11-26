# Макеты экранов приложения

Статические HTML-страницы сформированы из шаблонов текущего приложения и демонстрационной базы. Откройте файл в браузере: Flask для просмотра не требуется. Стили берутся из `../../src/infosec_desk/static/`, поэтому сохраняйте структуру репозитория.

| Экран | Файл |
| --- | --- |
| Вход | [login.html](login.html) |
| Главная | [dashboard.html](dashboard.html) |
| Реестр заявок | [tickets.html](tickets.html) |
| Создание заявки | [ticket_new.html](ticket_new.html) |
| Карточка заявки | [ticket_detail.html](ticket_detail.html) |
| О службе | [public_overview.html](public_overview.html) |
| Каталог услуг | [public_services.html](public_services.html) |
| Порядок подачи заявки | [public_submit.html](public_submit.html) |
| Категории обращений | [public_categories.html](public_categories.html) |
| Приоритеты обращений | [public_priorities.html](public_priorities.html) |
| Статусы обращений | [public_status.html](public_status.html) |
| Отслеживание заявки | [public_tracking.html](public_tracking.html) |
| Вопросы и ответы | [public_faq.html](public_faq.html) |
| Конфиденциальность | [public_security.html](public_security.html) |
| Помощь | [public_help.html](public_help.html) |
| Контакты | [public_contacts.html](public_contacts.html) |
| Правила | [public_rules.html](public_rules.html) |
| Обратная связь | [feedback.html](feedback.html) |
| Личный кабинет | [profile.html](profile.html) |
| Помощь сотруднику | [my_help.html](my_help.html) |
| Моя активность | [my_activity.html](my_activity.html) |
| Уведомления | [notifications.html](notifications.html) |
| Средства защиты | [assets.html](assets.html) |
| Пользователи | [admin_users.html](admin_users.html) |
| Журнал действий | [admin_audit.html](admin_audit.html) |
| Управление услугами | [admin_services.html](admin_services.html) |
| Сообщения посетителей | [admin_feedback.html](admin_feedback.html) |
| Настройки службы | [admin_settings.html](admin_settings.html) |
| Статистика службы | [admin_analytics.html](admin_analytics.html) |
| Обмен справочником СЗИ | [admin_exchange.html](admin_exchange.html) |

Публичные страницы и форма обратной связи показаны без входа в систему. Внутренние экраны показаны для роли сотрудника; страницы с префиксом `admin_` показаны для администратора. Реестр и список активности содержат до 25 заявок; показатели главной рассчитаны по демонстрационной базе. Ссылки между этими экранами работают локально. Формы служат для просмотра и не отправляют данные.

[Работа активности и уведомлений](../acceptance/notifications_protocol.md) описана
на примере проверенного сценария.

[Права и операции справочника СЗИ](../acceptance/assets_protocol.md) проверены
на отдельной копии базы.

[Пользователи и аудит](../acceptance/users_audit_protocol.md): права, отключение
учётной записи и сохранение связанных заявок.

[Услуги и обратная связь](../acceptance/services_feedback_protocol.md): добавление,
отключение услуги и обработка сообщения посетителя.

[Настройки, аналитика и JSON](../acceptance/admin_tools_protocol.md): проверка
сохранения параметров, счётчиков и импорта.

Для обновления всех макетов из корня репозитория:

```bash
python tools/render_mockups.py
```

Для одного экрана:

```bash
python tools/render_mockups.py --pages login
```

Генератор работает с временной копией демонстрационной базы и проверяет сохранность исходного файла. Значения токенов форм удаляются при сохранении HTML.
