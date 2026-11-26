# Как работает код приложения

Разбор идёт от запуска к регистрации и обработке заявки. В каждом разделе приведён настоящий фрагмент исходника, затем объяснение его работы и пример.

Фрагменты и номера строк относятся к версии [`61ea24a`](https://github.com/mvkorob/vkr/tree/61ea24a9b1a3f674f762f330386e8f74507ed37b). Ссылки открывают эту версию, поэтому последующие изменения файлов не сдвинут указанные строки.

Подробный путь HTTP-запроса разобран в [пояснении маршрутов Flask](flask_routes_explained.md). Состав модулей и схемы находятся в [архитектуре](architecture.md).

## 1. С чего начинается запуск

[Код: run.py, строки 70–76](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/run.py#L70-L76)

```python
os.chdir(ROOT)
command = sys.argv[1] if len(sys.argv) > 1 else "serve"
if command == "serve" or command.startswith("--"):
    prepare_runtime()
from infosec_desk.__main__ import main as app_main

app_main()
```

`ROOT` указывает на папку проекта. `os.chdir(ROOT)` делает её текущей: относительный путь `instance/infosec.sqlite3` будет отсчитываться от проекта, даже если команду вызвали из другой папки.

Если команда не указана, выбирается `serve`. Перед запуском сервера `prepare_runtime()` проверяет окружение Python и зависимости. Затем управление передаётся командам приложения в `__main__.py`. Веб-приложение создаёт фабрика `create_app`. Для Gunicorn объект приложения создаётся в `wsgi.py`.

## 2. Как проверяются поля формы

[Код: security.py, строки 31–35](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/security.py#L31-L35)

```python
def clean_text(value: str, name: str, *, minimum: int = 1, maximum: int = 500) -> str:
    cleaned = value.strip()
    if not minimum <= len(cleaned) <= maximum:
        raise ValueError(f"{name}: допустимая длина от {minimum} до {maximum} символов")
    return cleaned
```

`strip()` убирает пробелы с краёв строки. Затем проверяется её длина. Если она выходит за границы, функция поднимает `ValueError`; обработчик формы покажет сообщение об ошибке.

Например, тема `  Нет доступа  ` сохранится как `Нет доступа`. Для темы заявки заданы границы от 5 до 160 символов, для описания от 10 до 4000. Эти проверки выполняются на сервере: обход ограничения HTML-формы их не отменяет.

## 3. Что сохраняется вместо пароля

[Код: security.py, строки 10–15](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/security.py#L10-L15)

```python
def password_hash(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Пароль должен содержать не менее 10 символов")
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${key.hex()}"
```

Сначала проверяется минимальная длина: 10 символов. Затем создаётся случайная соль, то есть дополнительные данные для вычисления хеша. PBKDF2-HMAC-SHA256 вычисляет проверочное значение; число повторений задано константой `ITERATIONS` и равно 310 000.

В базе сохраняется строка с названием алгоритма, числом повторений, солью и хешем. При входе `verify_password()` повторяет вычисление с сохранённой солью и сравнивает результат через `hmac.compare_digest`. Благодаря случайной соли одинаковые пароли двух пользователей дают разные сохранённые строки.

[Проверка введённого пароля, строки 18–28](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/security.py#L18-L28).

## 4. Почему заявитель видит только свои заявки

[Код: service.py, строки 233–237](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/service.py#L233-L237)

```python
def list_tickets(db_path, user, status="", query="", limit=None):
    parts, params = ([], [])
    if user["role"] == "requester":
        parts.append("t.author_id=?")
        params.append(user["id"])
```

Для роли `requester` к SQL-запросу добавляется условие `t.author_id=?`. На место `?` SQLite подставляет идентификатор вошедшего пользователя из списка `params`. Он берётся из учётной записи, а не из поля формы. Фильтры поиска и статуса добавляются к тому же условию.

Например, если вошёл пользователь с ID 3, реестр будет содержать только строки с `author_id=3`. Специалист и администратор могут видеть общий реестр.

[Код: service.py, строки 254–258](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/service.py#L254-L258)

```python
def get_ticket(db_path, user, ticket_id):
    with connect(db_path) as db:
        row = db.execute(_ticket_select() + " WHERE t.id=?", (ticket_id,)).fetchone()
        if not row or (user["role"] == "requester" and row["author_id"] != user["id"]):
            return None
```

Карточка проверяется отдельно. Если заявка не найдена или принадлежит другому заявителю, возвращается `None`. Поэтому ввод чужого номера прямо в адресной строке не открывает карточку.

В запросах значения передаются отдельно от SQL-текста через параметры `?`. Так введённая тема или поисковая строка остаётся данными запроса.

## 5. Как заявка получает номер, автора и историю

[Код: service.py, строки 290–301](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/service.py#L290-L301)

```python
cursor = db.execute(
    (
        "INSERT INTO tickets(title,description,category,priority,asset_id,author_id)\n"
        "               VALUES(?,?,?,?,?,?)"
    ),
    (title, description, category, priority, asset_id, user["id"]),
)
ticket_id = cursor.lastrowid
db.execute(
    "INSERT INTO audit_events(actor_id,ticket_id,action,details) VALUES(?,?,?,?)",
    (user["id"], ticket_id, "created", "Заявка зарегистрирована"),
)
```

`INSERT` создаёт запись в `tickets`. Автор берётся из `user["id"]`, поэтому заявитель не может подменить его полем формы. `cursor.lastrowid` возвращает ID новой записи. Этот же ID записывается в событие регистрации.

Следом создаётся запись в `ticket_status_history` с первоначальным статусом `new`. Все три записи находятся внутри одной транзакции. Полный блок находится [в строках 278–309](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/service.py#L278-L309).

В базе хранится числовой ID. Для интерфейса он дополняется префиксом и нулями: ID 12 показывается как `З-000012`. Это оформление номера, отдельной таблицы номеров здесь нет.

## 6. Зачем нужна транзакция

[Код: db.py, строки 133–144](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/db.py#L133-L144)

```python
@contextmanager
def transaction(path: str | Path):
    db = connect(path)
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

Транзакция объединяет несколько SQL-команд в одну операцию. `BEGIN IMMEDIATE` начинает запись, `yield db` передаёт подключение коду внутри `with transaction(...)`.

Если весь блок выполнен, `commit()` сохраняет изменения. Если любая команда завершилась исключением, `rollback()` отменяет изменения этого блока, а `raise` передаёт ошибку вызывающему коду. `finally` закрывает подключение в обоих случаях.

При регистрации это означает: заявка, событие регистрации и первоначальный статус сохраняются вместе. Ошибка при записи истории отменит и вставку самой заявки.

## 7. Почему новую заявку нельзя сразу закрыть

[Код: service.py, строки 23–29](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/service.py#L23-L29)

```python
TRANSITIONS = {
    "new": {"in_progress", "on_hold"},
    "in_progress": {"on_hold", "resolved"},
    "on_hold": {"in_progress"},
    "resolved": {"closed", "in_progress"},
    "closed": set(),
}
```

Словарь `TRANSITIONS` задаёт, куда разрешено перейти из каждого статуса. Например, из `new` можно перейти в `in_progress` или `on_hold`. Статуса `closed` в этом наборе нет. У закрытой заявки набор следующих состояний пуст.

[Код: service.py, строки 344–347](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/service.py#L344-L347)

```python
if not current:
    raise ValueError("Заявка не найдена")
if status != current["status"] and status not in TRANSITIONS[current["status"]]:
    raise ValueError("Недопустимый переход между статусами")
```

Перед записью сервер сравнивает текущий и запрошенный статусы. Если статус меняется, новый должен входить в разрешённый набор. Поэтому попытка перейти `new → closed` вызовет ошибку, а путь `new → in_progress → resolved → closed` допустим.

Сначала функция также проверяет роль: менять состояние могут специалист и администратор. При назначении исполнителя проверяются его роль и активность. Изменение исполнителя и статуса фиксируется в `audit_events`, смена статуса также в `ticket_status_history`. Автору заявки и исполнителю создаются уведомления, кроме пользователя, который сам внёс изменение.

[Полная операция изменения заявки, строки 335–407](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/service.py#L335-L407).

## 8. Как защищено скачивание вложения

[Код: service.py, строки 545–550](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/service.py#L545-L550)

```python
def get_attachment(db_path, user, attachment_id):
    with connect(db_path) as db:
        row = db.execute("SELECT * FROM ticket_attachments WHERE id=?", (attachment_id,)).fetchone()
        if not row or not get_ticket(db_path, user, row["ticket_id"]):
            return None
        return dict(row)
```

Сначала файл ищется по ID. Затем вызывается та же проверка доступа к заявке, что используется для её карточки. Если файл не найден или заявка пользователю недоступна, возвращается `None`.

Например, знание адреса `/attachments/10` само по себе не даёт заявителю доступ к файлу из чужой заявки. HTTP-обработчик при таком результате отвечает 404.

[Обработчик скачивания, строки 543–553](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/web.py#L543-L553).

## 9. Как экспорт сохраняет фильтры и обрабатывает текст

[Код: web.py, строки 797–801](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/web.py#L797-L801)

```python
def records_for_export():
    user = require_user({"operator", "admin"})
    return service.list_tickets(
        db_path, user, request.args.get("status", ""), request.args.get("q", "")
    )
```

Выгрузка разрешена специалисту и администратору. Данные для файла получает `list_tickets` с параметрами `status` и `q` из адреса запроса. Поэтому при передаче тех же параметров реестр и файл выбирают заявки по одинаковым фильтрам.

[Код: web.py, строки 830–832](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/web.py#L830-L832)

```python
def spreadsheet_safe(value):
    v = str(value)
    return "'" + v if v.lstrip().startswith(("=", "+", "-", "@")) else v
```

Электронные таблицы могут воспринимать текст, начинающийся с `=`, `+`, `-` или `@`, как формулу. Функция добавляет перед таким значением апостроф. Например, `=1+1` попадёт в выгрузку как текст с ведущим апострофом. Эту обработку используют и CSV, и XLSX.

[Запись строк в CSV и XLSX, строки 834–861](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/web.py#L834-L861). CSV создаётся через `csv.writer` с разделителем `;`, а в XLSX строки добавляет openpyxl.

## Где проверяется описанное поведение

| Сценарий | Проверка |
| --- | --- |
| Создание заявки и событие регистрации | [test_service.py:24](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/tests/test_service.py#L24-L40) |
| Заявитель видит только свои обращения | [test_service.py:43](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/tests/test_service.py#L43-L58) |
| Роли и допустимые переходы статусов | [test_service.py:61](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/tests/test_service.py#L61-L85) |
| Создание заявки через HTTP-форму | [test_web.py:46](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/tests/test_web.py#L46-L58) |
| Отказ без CSRF-токена | [test_web.py:32](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/tests/test_web.py#L32-L43) |
| Права специалиста и выгрузка | [test_web.py:68](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/tests/test_web.py#L68-L83) |
