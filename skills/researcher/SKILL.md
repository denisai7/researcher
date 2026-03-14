---
name: researcher
description: "Research agent skill for NotebookLM. Accepts files, URLs, YouTube links, PDFs, audio — creates notebooks, uploads materials, generates artifacts (audio reviews, videos, slides, reports, infographics, mind maps, quizzes, flashcards, data tables). Trigger when user sends materials or asks for research processing."
metadata:
  {
    "openclaw":
      {
        "emoji": "🔬",
        "requires":
          {
            "anyBins": ["uvx", "notebooklm"],
          },
      },
  }
---

# 🔬 Researcher — NotebookLM Research Skill

Ты — исследовательский агент. Когда пользователь присылает материалы (файлы, ссылки, PDF, YouTube, аудио, изображения), ты обрабатываешь их через Google NotebookLM и возвращаешь результат.

## Инструмент

Используй CLI `notebooklm` через `uvx`:

```bash
uvx --python 3.13 --from "notebooklm-py[browser]" notebooklm <command>
```

Или если `notebooklm` установлен глобально — просто `notebooklm <command>`.

## Полный workflow

### 1. Получение материалов

Когда пользователь присылает файл, ссылку или YouTube — определи тип:
- **URL/ссылка** → `source add "<url>"`
- **YouTube** → `source add "<youtube_url>"`
- **PDF/файл** → `source add "<file_path>"`
- **Текст** → `source add-text "<title>" "<content>"`

### 2. Создание ноутбука

```bash
notebooklm create "Название исследования"
```

Запомни `notebook_id` из вывода.

### 3. Выбор ноутбука

```bash
notebooklm use <notebook_id>
```

### 4. Добавление источников

```bash
notebooklm source add "<url_or_file_path>"
```

Дождись обработки. Проверь статус:

```bash
notebooklm source list
```

Статус `ready` = источник обработан.

### 5. Генерация артефактов

| Артефакт | Команда | Формат |
|----------|---------|--------|
| 🎧 Аудио-ревью | `notebooklm generate audio --wait` | MP3 |
| 🎬 Видео | `notebooklm generate video --wait` | MP4 |
| 📊 Слайды | `notebooklm generate slide-deck --wait` | PDF/PPTX |
| 📋 Репорт | `notebooklm generate report --wait` | Markdown |
| 📈 Инфографика | `notebooklm generate infographic --wait` | PNG |
| 🧠 Mind Map | `notebooklm generate mind-map --wait` | JSON |
| ❓ Квиз | `notebooklm generate quiz --wait` | JSON |
| 🃏 Флешкарты | `notebooklm generate flashcards --wait` | JSON |
| 📊 Таблица данных | `notebooklm generate data-table --wait` | CSV |

Опции генерации:
- Аудио: `--format deep-dive|brief|critique|debate`, `--length short|default|long`
- Видео: `--style whiteboard|classic|anime|kawaii|auto`
- Репорт: `--format briefing-doc|study-guide|blog-post`
- Квиз/Флешкарты: `--difficulty easy|medium|hard`, `--quantity fewer|standard`
- Слайды: `--format detailed-deck|presenter-slides`
- Инфографика: `--orientation landscape|portrait|square`, `--style professional|sketch-note|anime`

### 6. Скачивание результата

```bash
notebooklm download audio ./output.mp3
notebooklm download video ./output.mp4
notebooklm download slide-deck ./output.pptx
notebooklm download report ./output.md
notebooklm download infographic ./output.png
notebooklm download mind-map ./output.json
notebooklm download quiz --format json ./output.json
notebooklm download flashcards --format json ./output.json
notebooklm download data-table ./output.csv
```

### 7. Отправка результата

После скачивания — отправь файл пользователю с описанием.

## UX-флоу

### Файл без команды

Если пользователь прислал материал без указания действия — предложи выбор:

```
📎 Получил: «документ.pdf». Что сделать?
[🎧 Аудио-ревью] [📊 Слайды]
[🎬 Видео]       [📋 Репорт]
[📈 Инфографика] [🧠 Mind Map]
```

### Файл с командой

Если пользователь указал действие (например, "сделай аудио-ревью") — сразу выполняй.

```
✅ Принял! Делаю аудио-ревью...
🔄 Создаю ноутбук...
📤 Загружаю файл...
🎧 Генерирую аудио (5-10 мин)...
[отправляет MP3 + описание]
```

### Статусы выполнения

Сообщай пользователю о прогрессе на каждом этапе:
1. `🔄 Создаю ноутбук...`
2. `📤 Загружаю материалы...`
3. `⏳ Материалы обрабатываются в NotebookLM...`
4. `🎧 Генерирую артефакт (это может занять 5-10 минут)...`
5. `📥 Скачиваю результат...`
6. `✅ Готово!`

## Формат доставки результата

Один пост — файл + caption (до 1024 символов для Telegram):

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

## Поддерживаемые форматы

| Вход | Типы |
|------|------|
| Документы | PDF, DOCX, PPTX, XLSX, TXT, RTF, CSV, Markdown |
| Ссылки | Веб-страницы, Google Docs/Slides/Sheets |
| Видео | YouTube, MP4 |
| Аудио | MP3, WAV, OGG, M4A, FLAC |
| Изображения | JPG, PNG, GIF, WebP |

### Автоконвертация

Некоторые форматы конвертируются автоматически перед загрузкой:
- DOC, DOCX, PPT, PPTX, XLS, XLSX, RTF, TXT → PDF (через LibreOffice `soffice --headless --convert-to pdf`)
- HEIC, TIFF → JPEG (через macOS `sips`)
- WAV → MP3 (через `ffmpeg -i input.wav -q:a 2 output.mp3`)

## Авторизация

Для работы нужна авторизация в Google NotebookLM:

```bash
uvx --python 3.13 --from "notebooklm-py[browser]" notebooklm login
```

Проверка авторизации:

```bash
uvx --python 3.13 --from "notebooklm-py[browser]" notebooklm auth check --test
```

Куки хранятся в `~/.notebooklm/storage_state.json`.

Если авторизация истекла — повторить `notebooklm login`.

## Chat с ноутбуком

Можно задать вопрос по загруженным материалам:

```bash
notebooklm ask "В чём главная идея?"
```

## Лимиты

- Максимальный размер файла для NotebookLM: **200 MB**
- Максимальный размер файла для скачивания через Telegram Bot API: **20 MB**
- Генерация аудио/видео может занять **5-15 минут**
- Авторизация может истекать каждые **~20 минут**

## Ошибки

- Если источник не обработался — проверь `notebooklm source list` (статус `error`)
- Если авторизация истекла — запусти `notebooklm login`
- Если rate limit — подожди и повтори
