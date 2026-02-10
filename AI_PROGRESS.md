# AI Progress Log

## Current Phase
Phase 1 — Core Validation (ZIP upload and text matching)

## What already works
- Cloud Run deployment successful
- Automatic deploy via GitHub → Cloud Build → Artifact Registry → Cloud Run
- Single image OCR using Google Vision
- Web upload form available

## Known problems
- No ZIP archive support yet
- No reference text extraction
- No comparison report
- No manual review UI

## Last completed task
Google Vision OCR integrated and returning text.

## Current task (DO NOT REPEAT PREVIOUS WORK)
Implement ZIP archive processing:
- Read images from /images
- Read reference texts from /texts
- Match files by filename prefix

## Next tasks (priority order)
1. Extract reference text from TXT/DOCX
2. Exact match comparison
3. Result table in UI
4. Manual review mode

## Rules for AI developer
- Never rewrite existing working OCR
- Modify minimal files
- Prefer adding modules instead of replacing main.py
- After completing a task: update this file

апдейт 10.02
## Что уже работает
- Рабочий деплой на Cloud Run.
- Автоматический пайплайн GitHub → Cloud Build → Cloud Run.
- OCR через Google Vision для одиночного изображения.
- Веб‑форма загрузки.
- ✅ **Создана база Firestore (Native mode) в регионе europe‑west1 для хранения статусов заданий.**
- ✅ **Создан топик Pub/Sub `ocr‑jobs` для постановки задач в очередь.**

## Последняя выполненная задача
Настроена инфраструктура: создана Firestore (native mode) и топик Pub/Sub `ocr‑jobs`.

## Текущая задача (не повторять предыдущее!)
- Реализовать API‑эндпоинты для создания Job и публикации задания в Pub/Sub.
- Разработать воркер‑сервис, который подписывается на `ocr‑jobs`, выполняет OCR и обновляет статус в Firestore.

## Следующие задачи (приоритет снижается сверху вниз)
1. Извлечение текста из TXT/DOCX.
2. Сравнение строк на полное совпадение.
3. Таблица результатов в UI.
4. Режим ручной проверки.

