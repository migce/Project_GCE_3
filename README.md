# Project GCE 3

Описание проекта будет добавлено позже.

## Установка

1. Создайте виртуальную среду:
```bash
python -m venv venv
```

2. Активируйте виртуальную среду:
```bash
source venv/Scripts/activate  # Windows Git Bash
# или
venv\Scripts\activate.bat     # Windows Command Prompt
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

## Использование

Добавьте инструкции по использованию проекта.

## PostgreSQL: настройка и миграция с SQLite

Проект по умолчанию использует SQLite (файл `db.sqlite3`). Для продакшена рекомендуется PostgreSQL. В `gce_project/settings.py` добавлена поддержка Postgres через переменные окружения.

### 1) Установите драйвер и зависимости

```bash
pip install -r requirements.txt
```

Если ранее был установлен `psycopg2`/`psycopg2-binary` и при установке появляется ошибка вида
«Microsoft Visual C++ 14.0 or greater is required», используйте драйвер `psycopg` (v3) из этого
проекта — он ставится как бинарный пакет и не требует сборки на Windows:

```bash
pip uninstall -y psycopg2 psycopg2-binary
pip install -r requirements.txt
```

### 2) Поднимите PostgreSQL и создайте БД/пользователя

Пример (psql):

```sql
CREATE USER gce3 WITH PASSWORD 'change_me';
CREATE DATABASE gce3 OWNER gce3;
GRANT ALL PRIVILEGES ON DATABASE gce3 TO gce3;
```

### 3) Настройте переменные окружения

Вариант A (через файл .env — рекомендуется для локальной разработки):

1. Скопируйте `.env.example` в `.env` (или используйте уже созданный `.env`).
2. Укажите строку подключения:

```
DATABASE_URL=postgres://gce3:ваш_пароль@localhost:5432/gce3
DB_CONN_MAX_AGE=60
```

Вариант B (через единый URL в окружении):

```powershell
$env:DATABASE_URL = "postgres://gce3:change_me@localhost:5432/gce3"
```

Вариант C (через отдельные переменные):

```powershell
$env:DB_ENGINE = 'postgres'
$env:DB_NAME = 'gce3'
$env:DB_USER = 'gce3'
$env:DB_PASSWORD = 'change_me'
$env:DB_HOST = 'localhost'
$env:DB_PORT = '5432'
$env:DB_CONN_MAX_AGE = '60'   # опционально
```

Поддерживаются также `DB_SSLMODE` и `DB_CONNECT_TIMEOUT` (опционально).

### 4) Перенос данных (из SQLite в PostgreSQL)

1. На текущей SQLite-схеме (без активной записи) создайте дамп данных:

```bash
python manage.py dumpdata \
  --natural-foreign --natural-primary \
  --exclude=contenttypes --exclude=auth.permission \
  --indent 2 > dump.json
```

2. Переключите переменные окружения на PostgreSQL (см. п.3) и примените миграции:

```bash
python manage.py migrate
```

3. Загрузите данные:

```bash
python manage.py loaddata dump.json
```

4. (Опционально) Сбросить последовательности PK, если после загрузки появляются ошибки при вставке:

```bash
python manage.py sqlsequencereset main auth admin sessions contenttypes | python manage.py dbshell
```

### 5) Проверка

```bash
python manage.py check
python manage.py runserver
```

Если БД PostgreSQL используется — размер БД в интерфейсе может не отображаться (ранее вычислялся по файлу SQLite).
