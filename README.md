# 🔬 Researcher — ИИ-агент для исследований через NotebookLM

Персональный Telegram-агент, который принимает файлы, ссылки и документы, обрабатывает их через **Google NotebookLM Studio** и возвращает готовые артефакты: аудио-ревью, презентации, видео, отчёты, инфографику и другие.

## Как это работает

```
Пользователь → Telegram → OpenClaw → Researcher Agent → NotebookLM → Результат → Telegram
```

1. Отправляешь PDF, ссылку, YouTube или аудио в Telegram
2. Агент предлагает выбрать действие (кнопки)
3. Материал загружается в NotebookLM
4. NotebookLM генерирует артефакт
5. Результат приходит в Telegram одним сообщением (файл + описание)

## Доступные артефакты

| Артефакт | Описание | Формат |
|----------|----------|--------|
| 🎧 Аудио-ревью | Подкаст-стиль обзор материала | MP3 |
| 🎬 Видео | Видео-обзор | MP4 |
| 📊 Слайды | Презентация по материалу | PDF/PPTX |
| 📋 Репорт | Текстовый отчёт / саммари | Markdown |
| 📈 Инфографика | Визуальная сводка | PNG |
| 🧠 Mind Map | Карта связей и идей | JSON |
| ❓ Квиз | Тестовые вопросы | JSON |
| 🃏 Флешкарты | Карточки для запоминания | JSON |
| 📊 Таблица данных | Структурированные данные | CSV |

## Поддерживаемые входные форматы

- PDF-документы
- Ссылки на статьи и веб-страницы
- YouTube-видео
- Аудиофайлы (mp3, wav, ogg)
- Изображения
- Пересланные сообщения из Telegram
- Голосовые сообщения

## Архитектура

Researcher работает как агент [OpenClaw](https://openclaw.ai) — open-source платформы для управления ИИ-агентами.

```
OpenClaw Gateway (Mac Mini)
├── Astra — основной агент
├── Lisa — спецагент для сбора спецификаций
├── CTO — автопилот spec-to-code
└── Researcher — этот агент
    ├── Telegram бот (@MaxAiResercherbot)
    ├── notebooklm-py — Python-клиент для NotebookLM API
    └── SOUL.md — инструкции и правила поведения
```

### Ключевые компоненты

- **OpenClaw** — оркестратор, маршрутизирует Telegram-сообщения к агенту
- **notebooklm-py** — библиотека для работы с Google NotebookLM API
- **SOUL.md** — описание поведения агента (UX-флоу, правила доставки, форматирование)

## Установка и настройка

### 1. Зависимости

```bash
# notebooklm-py с поддержкой браузерной авторизации
uvx --python 3.13 --from "notebooklm-py[browser]" notebooklm --version

# Playwright (для авторизации)
uvx --python 3.13 --from playwright playwright install chromium

# ffmpeg (для конвертации аудио WAV→MP3)
brew install ffmpeg
```

### 2. Авторизация в NotebookLM

```bash
uvx --python 3.13 --from "notebooklm-py[browser]" notebooklm login
```

Откроется браузер → войти в Google → дождаться страницы NotebookLM → нажать Enter.

Проверка:
```bash
uvx --python 3.13 --from "notebooklm-py[browser]" notebooklm auth check --test
```

> Авторизация истекает каждые ~20 минут. Агент автоматически переавторизуется через OpenClaw CDP.

### 3. Регистрация в OpenClaw

```bash
# Добавить агента
openclaw agents add researcher \
  --workspace ~/.openclaw/workspace-researcher \
  --model anthropic/claude-sonnet-4-5 \
  --non-interactive

# Добавить Telegram-канал
openclaw channels add --channel telegram --account researcher --token "<BOT_TOKEN>"

# Привязать
openclaw agents bind --agent researcher --bind telegram:researcher

# Дать доступ к инструментам (exec, read, write, etc.)
# В openclaw.json → agents.list → researcher → tools: {"profile": "full", ...}
```

### 4. Workspace

```
~/.openclaw/workspace-researcher/
├── IDENTITY.md    — имя и тема агента
├── SOUL.md        — правила поведения, UX-флоу, форматирование
└── *.mp3/*.pptx   — временные файлы для отправки в Telegram
```

## UX-флоу

### Файл без команды
```
Пользователь: [отправляет PDF]
Агент: 📎 Получил: «документ.pdf». Что сделать?
       [🎧 Аудио-ревью] [📊 Слайды]
       [🎬 Видео]       [📋 Репорт]
       [📈 Инфографика] [🧠 Mind Map]
Пользователь: [нажимает 🎧 Аудио-ревью]
Агент: 🔄 Создаю ноутбук...
       📤 Загружаю файл...
       🎧 Генерирую аудио (5-10 мин)...
       [отправляет MP3 + описание одним сообщением]
```

### Файл с командой
```
Пользователь: [отправляет PDF] "сделай аудио-ревью"
Агент: ✅ Принял! Делаю аудио-ревью...
       [статусы → результат]
```

### Формат доставки

Один пост в Telegram — файл + caption (до 1024 символов):

```
🎧 Название документа — Год
Автор

📌 О чём: Краткое описание.

💡 Ключевые идеи:
— Идея 1
— Идея 2
— Идея 3
— Идея 4
— Идея 5

📄 Источник, год
```

## Python-код (legacy)

В папке `src/` находится Python-реализация Telegram-бота, созданная CTO-агентом. Текущая версия Researcher работает через OpenClaw (не запускает Python-бот напрямую), но код полезен как референс:

- `src/telegram/` — Telegram-хендлеры
- `src/core/` — оркестрация, группировка сообщений, проекты
- `src/integrations/notebooklm/` — клиент и адаптер для notebooklm-py
- `src/integrations/supabase/` — персистентность проектов
- `src/workers/` — фоновая обработка задач
- `src/models/` — модели данных (проект, материал, результат)
- `tests/` — 204 теста

## Разработка

```bash
git clone git@github.com:MakcKozlov/researcher.git
cd researcher
pip install -r requirements.txt
python -m pytest --tb=short -q
```
