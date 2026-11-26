# От формы до ответа Flask

Здесь разобрана регистрация одной заявки: что отправляет браузер, как сервер проверяет запрос и как открывается готовая карточка. Обработка данных в SQLite объясняется в [пояснении кода](code_guide.md).

Ссылки и фрагменты закреплены на версии [`61ea24a`](https://github.com/mvkorob/vkr/tree/61ea24a9b1a3f674f762f330386e8f74507ed37b).

## 1. Браузер отправляет форму

[Код: ticket_new.html, строки 7–9](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/templates/ticket_new.html#L7-L9)

```html
<form method="post" action="/tickets" class="stack">
  <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
  <label for="ticket-title">Тема заявки<input id="ticket-title" name="title" required minlength="5" maxlength="160" placeholder="Кратко укажите суть проблемы" autofocus></label>
```

`method="post"` задаёт способ отправки. `action="/tickets"` указывает адрес обработчика. Введённые значения передаются под именами полей: `title`, `description`, `category`, `priority`, `asset_id`.

Скрытое поле `csrf_token` получает значение от сервера. Оно связывает отправленную форму с сеансом, в котором эта форма была открыта. Проверка выполняется при получении запроса.

## 2. Flask выбирает обработчик по адресу и методу

[Код: web.py, строки 462–465](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/web.py#L462-L465)

```python
@app.post("/tickets")
def create_ticket_post():
    user = require_user()
    data = secure_form()
```

Декоратор `@app.post("/tickets")` регистрирует функцию для POST-запросов по адресу `/tickets`. Сам реестр открывается GET-запросом по тому же адресу; это другой обработчик.

`require_user()` возвращает вошедшего пользователя. `secure_form()` проверяет токен и возвращает поля формы. Только после этого начинается чтение данных. Пустой выбор СЗИ превращается в `None`, выбранный ID в целое число.

## 3. Проверки входа и CSRF выполняются до записи

[Код: web.py, строки 323–334](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/web.py#L323-L334)

```python
def require_user(roles=None):
    user = current_user()
    if user is None:
        abort(401)
    if roles and user["role"] not in roles:
        abort(403)
    return user

def secure_form():
    if not check_csrf(session.get("csrf_token"), request.form.get("csrf_token")):
        abort(403)
    return request.form
```

Если пользователя нет, вызывается `abort(401)`. Это останавливает обработчик; общий обработчик ошибок отвечает перенаправлением 303 на `/login`. Если передан набор ролей и роль пользователя в него не входит, возвращается 403.

Для создания заявки достаточно входа. Для изменения статуса обработчик вызывает `require_user({"operator", "admin"})`, поэтому заявителю эта операция недоступна.

`secure_form()` сравнивает токен сеанса и токен отправленной формы. При отсутствии или несовпадении токена запрос завершается с кодом 403 до вызова функции создания заявки.

## 4. Обработчик передаёт значения предметной функции

[Код: web.py, строки 468–476](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/web.py#L468-L476)

```python
ticket_id = service.create_ticket(
    db_path,
    user,
    str(data.get("title", "")),
    str(data.get("description", "")),
    str(data.get("category", "")),
    str(data.get("priority", "")),
    asset_id,
)
```

`service.create_ticket` получает путь базы, вошедшего пользователя и значения полей. В ней проверяются длина текста, допустимые категория и приоритет, существование активного СЗИ. Затем сохраняются заявка, событие регистрации и первоначальная запись истории статусов.

Возвращённый `ticket_id` служит номером записи и позволяет сформировать адрес карточки. Веб-обработчик отвечает за HTTP-запрос, а предметная функция за проверку и сохранение обращения. Этот же сервис можно вызвать из теста или команды без браузера.

## 5. При ошибке снова открывается форма, при успехе карточка

[Код: web.py, строки 477–479](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/web.py#L477-L479)

```python
except (ValueError, sqlite3.IntegrityError) as exc:
    return forward("/tickets/new", error=str(exc))
return forward(f"/tickets/{ticket_id}", message="Заявка зарегистрирована")
```

`ValueError` возникает при неверных значениях, `sqlite3.IntegrityError` при нарушении ограничения базы. Ошибка преобразуется в сообщение и перенаправление на форму.

При успехе сервер возвращает адрес `/tickets/<ticket_id>`. Например, если создана запись с ID 12, браузер получает перенаправление на `/tickets/12`. Код ответа 303 просит открыть этот адрес GET-запросом. При обычном обновлении уже открытой карточки браузер повторяет чтение, а не создание заявки.

[Код: web.py, строки 316–321](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/web.py#L316-L321)

```python
def forward(path, message="", error=""):
    if message:
        session["message"] = message
    if error:
        session["error"] = error
    return redirect(path, code=303)
```

`forward()` сохраняет сообщение в сеансе и возвращает перенаправление. При формировании следующей страницы `show()` забирает сообщение через `session.pop`, поэтому оно выводится однократно.

## 6. Вход создаёт новый сеанс пользователя

[Код: web.py, строки 418–421](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/web.py#L418-L421)

```python
session.clear()
session["user_id"] = user["id"]
session["csrf_token"] = new_csrf_token()
return redirect("/", code=303)
```

Эти строки выполняются после успешной проверки логина и пароля. Старое содержимое сеанса очищается, сохраняется ID пользователя, создаётся новый CSRF-токен. Браузер перенаправляется на главную страницу. На следующих запросах пользователь загружается из базы по сохранённому ID.

[Полный обработчик входа, строки 410–421](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/src/infosec_desk/web.py#L410-L421).

## 7. Что проверяют тесты

| Действие | Ожидаемый результат | Тест |
| --- | --- | --- |
| Отправить корректную заявку | Открывается карточка с темой и номером | [test_web.py:46](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/tests/test_web.py#L46-L58) |
| Убрать CSRF-токен | Ответ 403 | [test_web.py:32](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/tests/test_web.py#L32-L43) |
| Открыть экспорт под заявителем | Ответ 403 | [test_web.py:61](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/tests/test_web.py#L61-L65) |
| Сменить статус под специалистом | Новый статус отображается в карточке | [test_web.py:68](https://github.com/mvkorob/vkr/blob/61ea24a9b1a3f674f762f330386e8f74507ed37b/tests/test_web.py#L68-L83) |
