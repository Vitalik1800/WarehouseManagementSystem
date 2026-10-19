# WarehouseManagementSystem

Система управління складом із REST API та графічним інтерфейсом.

## Можливості

- Авторизація, ролі та керування користувачами.
- Управління складами та місцями зберігання.
- Облік категорій, товарів і постачальників.
- Надходження, видача та списання товарів.
- Контроль складських залишків.
- Панель показників та журнал активності.
- Налаштування зовнішнього вигляду.

## Технології

Python 3.12, FastAPI, Uvicorn, SQLAlchemy, Alembic, MySQL, CustomTkinter, HTTPX, Pytest.

## Встановлення на Windows

Встановіть Python 3.12 та MySQL. Виконуйте команди з кореня проєкту.

```cmd
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements-lock.txt
copy .env.example .env
```

## Конфігурація

У файлі `.env` налаштуйте `DATABASE_URL` та `JWT_SECRET_KEY` (щонайменше 32 символи). Замініть шаблонні паролі. Для робочого середовища встановіть `APP_ENV=production` та `DEBUG=false`.

## База даних

Створіть базу MySQL і користувача з необхідними правами. Після налаштування `.env` виконайте:

```cmd
python -m alembic upgrade head
python -m alembic current
```

Перед міграціями існуючої бази створіть резервну копію.

## Створення адміністратора

```cmd
python -m scripts.bootstrap_admin
```

Скрипт інтерактивно запитує ім’я, логін і пароль.

## Запуск Backend

```cmd
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

API: http://127.0.0.1:8000/docs
Перевірка стану: http://127.0.0.1:8000/health

## Запуск Frontend

Відкрийте друге вікно CMD у корені проєкту, активуйте `.venv` та виконайте:

```cmd
python -m frontend.main
```

Адреса API задається через `FRONTEND_API_BASE_URL` у `.env`.

## Тестування

```cmd
python -m pytest tests/unit -q
python -m pytest tests/integration -q
```

Інтеграційні тести потребують окремої тестової бази. Не запускайте їх проти робочої бази даних.

## Безпека

Не публікуйте `.env`, JWT-секрети, паролі та резервні копії. Не відкривайте API у публічний інтернет без додаткового захисту.

## Версія

Підготовка релізу v1.0.0.
