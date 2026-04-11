# AI FUNCTIONAL SPEC (APPEND-ONLY)

ВНИМАНИЕ: Этот файл append-only.

- Нельзя удалять или переформулировать ранее зафиксированные инварианты.
- Допускается только добавление новых правил и блоков `Изменено на...`.

## 1. Системные инварианты

1. Каждая операция обязана работать в контексте владельца `telegram_user_id`.
2. Нельзя выдавать или изменять сущности другого пользователя.
3. Все callback значения должны валидироваться по формату и принадлежности.
4. Ошибки внешних сервисов не должны приводить к потере записи дневника.

## 2. Контракты сущностей

### 2.1 Habit
- Поля: `id`, `user_id`, `name`, `habit_type`, `is_active`, `created_at`.
- `habit_type`: `positive|negative`.

### 2.2 HabitScheduleRule
- Поля: `habit_id`, `schedule_type`, `time_slot`, `weekday`, `interval_days`, `start_from`.
- `schedule_type`: `daily|every_other_day|specific_weekdays`.
- `time_slot`: `morning|day|evening`.

### 2.3 HabitCheckin
- Уникальность: `(habit_id, check_date, time_slot)`.
- `status`: `done|missed|violated|optional_done`.

### 2.4 DiaryEntry
- Поля: `entry_date`, `entry_type`, `text_body`, `tags`, `created_at`.
- `entry_type`: `text|voice|mixed`.

### 2.5 DiaryVoice
- Поля: `entry_id`, `telegram_file_id`, `telegram_file_unique_id`, `duration_sec`, `mime`, `message_id`.

### 2.6 DiaryTranscript
- Поля: `entry_id`, `transcript_text`, `language`, `confidence`, `stt_status`, `attempts`, `last_error`, `updated_at`.
- `stt_status`: `pending|done|failed`.

## 3. Алгоритмы

### 3.1 Плановые и сверхплановые метрики
- Плановые слоты считаются только в невыходные дни.
- Сверхплан — успешные слоты в выходные.
- Формулы:
  - `plan_completion = completed_slots / plan_slots * 100`
  - `over_completion = (completed_slots + extra_slots) / plan_slots * 100`

### 3.2 Негативные привычки
- Явный срыв = `violated`.
- Для прошедшей даты отсутствие срыва может интерпретироваться как успех при расчетах.

### 3.3 Транскрибация голосовых
- Голосовая запись сохраняется до попыток STT.
- STT выполняется с ретраями.
- При неуспехе выставляется `failed`, запись дневника не теряется.

### 3.4 Поиск заметок
- База поиска: `DiaryEntry.text_body` + `DiaryTranscript.transcript_text`.
- Используются FTS и trigram индексы Postgres.
- При режиме `voice_only` возвращаются только записи, имеющие `DiaryVoice`.

## 4. Контракты команд/экранов

- `/start` — приветствие и список команд.
- `/today` — привычки ближайшего слота.
- `/habits` — inline CRUD привычек.
- `/calendar` — текущая неделя и навигация.
- `/diary` — добавление текст/голос и список заметок дня.
- `/search_notes` — отдельный поиск заметок.
- `/stats` — агрегированная статистика.
- `/export_diary` — ZIP markdown+media.
- `/export_stats_html` — статический HTML отчет.

## 5. Callback namespace

- `habits:*` — привычки и отметки.
- `calendar:*` — календарь.
- `diary:*` — дневник.
- `search:*` — поиск заметок.
- `stats:*` — выбор периода статистики.

## 6. Edge-cases

1. Пустое название привычки отклоняется.
2. Пустой поисковый запрос отклоняется.
3. Отмена отметки без истории должна вернуть мягкую ошибку.
4. Неуспешная транскрибация не должна блокировать экспорт.
5. Экспорт без данных возвращает пустой, но валидный архив/отчет.

## 7. Политика изменения функций

Для любой измененной функции добавлять рядом запись формата:

`Изменено на: <новое поведение>. Причина: <почему>. Коммит: <hash>.`

Пример для будущих правок:
- Изменено на: расширен parser callback для новых состояний. Причина: добавлен новый экран. Коммит: abc1234.

## История изменений (append-only)

- Изменено на: добавлен namespace `settings:*` для выбора/сохранения weekday day-off правил. Причина: управление множественными выходными через UI. Коммит: abc0c6f.
- Изменено на: добавлен callback namespace `main:open:*` для inline-навигации между разделами. Причина: главный интерфейс должен быть inline-first. Коммит: abc0c6f.
- Изменено на: в `0001_base_habits` enum-объекты переведены на `create_type=False` при ручном `create(checkfirst=True)`. Причина: устранение `DuplicateObject` на `alembic upgrade head`. Коммит: 0cf872d.
