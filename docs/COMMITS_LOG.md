# COMMITS LOG (APPEND-ONLY)

ВНИМАНИЕ: Этот журнал append-only.

- Нельзя удалять существующие записи.
- Можно только добавлять новые записи в конец файла.
- Для каждой новой записи: хэш, дата, описание, причина, затронутые подсистемы, риск.

## История коммитов

### 3245573
- Дата: 2026-04-11
- Сообщение: `chore: bootstrap project skeleton and tooling`
- Что сделано: создан каркас проекта, базовые конфиги, точка входа, базовые обработчики.
- Почему: стартовая инфраструктура для дальнейшей функциональности.
- Подсистемы: app bootstrap, config, logging, package tooling.
- Риск: низкий.

### 5179c7c
- Дата: 2026-04-11
- Сообщение: `chore: setup db models and migrations foundation`
- Что сделано: добавлены модели БД для пользователей/привычек/расписаний/выходных/чекинов и первичная миграция.
- Почему: нужен устойчивый persistence-слой.
- Подсистемы: SQLAlchemy models, Alembic.
- Риск: средний (изменения схемы).

### 3272dad
- Дата: 2026-04-11
- Сообщение: `feat: implement habit domain services and schedule engine`
- Что сделано: добавлены доменные сервисы привычек, пользовательский сервис и движок расписаний.
- Почему: реализация ключевой бизнес-логики привычек.
- Подсистемы: domain/services.
- Риск: средний.

### 9b2e91e
- Дата: 2026-04-11
- Сообщение: `feat: inline habits management and slot-based list UI`
- Что сделано: реализован inline CRUD привычек, слоты утро/день/вечер/все, мастер создания привычки.
- Почему: основной UX должен быть на inline-кнопках.
- Подсистемы: Telegram handlers + FSM.
- Риск: средний.

### 4be622b
- Дата: 2026-04-11
- Сообщение: `feat: weekly calendar navigation and day drill-down`
- Что сделано: внедрен недельный календарь, листание недель и просмотр деталей дня.
- Почему: визуализация прогресса по времени.
- Подсистемы: calendar handler.
- Риск: средний.

### e1e145d
- Дата: 2026-04-11
- Сообщение: `feat: checkin flow with plan and over-plan metrics`
- Что сделано: добавлены отметки `✅/❌`, undo последней отметки и расчет plan/over-plan метрик.
- Почему: целевая механика учета выполнения и перевыполнения.
- Подсистемы: checkins, metrics, stats UI.
- Риск: средний-высокий (алгоритмика метрик).

### 13d2611
- Дата: 2026-04-11
- Сообщение: `feat: add diary text entries and linking to calendar days`
- Что сделано: текстовый дневник с хранением в БД и отображением заметок в календарных днях.
- Почему: расширение трекера до журнала прогресса.
- Подсистемы: diary entries, calendar integration.
- Риск: средний.

### 97becea
- Дата: 2026-04-11
- Сообщение: `feat: add voice diary storage and transcription pipeline`
- Что сделано: добавлено хранение голосовых, таблица транскрипций и pipeline транскрибации с retry.
- Почему: поддержка голосового дневника и подготовки к поиску ГС.
- Подсистемы: diary voice, STT pipeline.
- Риск: средний-высокий (внешние зависимости STT/Telegram file API).

### d016b55
- Дата: 2026-04-11
- Сообщение: `feat: implement notes search over text and transcripts`
- Что сделано: реализован поиск по тексту и транскрипциям, режим только голосовые, отправка найденных voice.
- Почему: быстрый доступ к нужным заметкам и ГС.
- Подсистемы: search handlers, FTS/trigram indexes.
- Риск: средний.

### 18794a9
- Дата: 2026-04-11
- Сообщение: `feat: add diary export markdown with media zip`
- Что сделано: экспорт дневника в ZIP с markdown и media.
- Почему: переносимость дневника в внешние заметочники.
- Подсистемы: export service, telegram document flow.
- Риск: средний.

### 42d174d
- Дата: 2026-04-11
- Сообщение: `feat: generate static html statistics report`
- Что сделано: генерация HTML-отчета со сводной статистикой и трендом.
- Почему: наглядная аналитика вне Telegram интерфейса.
- Подсистемы: report service, templates, export command.
- Риск: средний.

### 0cec4d0
- Дата: 2026-04-11
- Сообщение: `docs: add append-only product and ai functional specs`
- Что сделано: добавлены append-only спецификации продукта и функционала для нейросети.
- Почему: зафиксировать функционал и исключить потерю требований.
- Подсистемы: documentation.
- Риск: низкий.

## Правило пополнения журнала

Для каждого следующего коммита добавлять новый блок в конец этого файла по тому же шаблону.

### a2db3d0
- Дата: 2026-04-11
- Сообщение: `docs: add detailed commit log and update docs policy`
- Что сделано: добавлен append-only журнал коммитов и шаблон заполнения для последующих изменений.
- Почему: требование полного и постоянного учета истории изменений.
- Подсистемы: documentation governance.
- Риск: низкий.

### d872474
- Дата: 2026-04-11
- Сообщение: `chore: add ci guard for append-only docs and finalize tests`
- Что сделано: добавлен CI workflow, скрипт запрета удаления строк в append-only документах и тесты доменной логики.
- Почему: защита критичных спецификаций и контроль регрессий.
- Подсистемы: CI/CD, tests, docs integrity checks.
- Риск: низкий-средний.

### dfc1edd
- Дата: 2026-04-11
- Сообщение: `docs: append latest commit entries to commits log`
- Что сделано: журнал коммитов дополнен последними изменениями по документации и CI.
- Почему: соблюдение требования фиксировать историю в append-only формате.
- Подсистемы: documentation.
- Риск: низкий.

### abc0c6f
- Дата: 2026-04-11
- Сообщение: `feat: add inline start menu and day-off settings screen`
- Что сделано: внедрено inline главное меню и экран настроек выходных дней недели.
- Почему: соответствие требованию основного интерфейса на inline-кнопках и управляемых выходных.
- Подсистемы: bot UX, settings/day-off.
- Риск: средний.

### 0cf872d
- Дата: 2026-04-11
- Сообщение: `fix: prevent duplicate enum creation in base migration`
- Что сделано: исправлена первая миграция, исключено повторное создание PostgreSQL enum-типов.
- Почему: на чистом сервере `alembic upgrade head` падал с `DuplicateObject`.
- Подсистемы: database migrations.
- Риск: низкий.

### 3681110
- Дата: 2026-04-11
- Сообщение: `fix: use postgresql enum types with create_type disabled in migration`
- Что сделано: заменен тип enum в первой миграции на PostgreSQL-специфичный `ENUM` с отключенным автосозданием.
- Почему: устранение повторного `CREATE TYPE` во время создания таблиц.
- Подсистемы: database migrations.
- Риск: низкий.

### cd11194
- Дата: 2026-04-11
- Сообщение: `fix: use postgresql enum type in diary entries migration`
- Что сделано: исправлена вторая миграция для корректной работы PostgreSQL enum `diary_entry_type`.
- Почему: миграции падали из-за дублирования enum-типа.
- Подсистемы: database migrations.
- Риск: низкий.

### 86bbc4d
- Дата: 2026-04-11
- Сообщение: `feat: simplify button navigation and add back flow with faster callbacks`
- Что сделано: упрощено главное меню, добавлены подменю и единая кнопка `Назад`, экспорт переведен на кнопки, ускорены callback-ответы и рендер календаря.
- Почему: устранить перегрузку интерфейса, добавить навигацию назад и снизить задержки нажатий.
- Подсистемы: handlers UX/navigation, calendar performance, callback flow.
- Риск: средний.

### 4f2ddc1
- Дата: 2026-04-11
- Сообщение: `docs: append navigation and callback performance updates`
- Что сделано: append-only спецификации дополнены фиксацией изменений по подменю, кнопке `Назад`, button-only экспорту и ускорению callback/календаря.
- Почему: зафиксировать обновленные UX-контракты и инварианты поведения бота.
- Подсистемы: documentation (product/ai specs).
- Риск: низкий.

### 4e8c5b9
- Дата: 2026-04-11
- Сообщение: `fix: migrate telegram ids to bigint and remove command filters`
- Что сделано: `users.telegram_user_id` переведен на `BIGINT` (модель + миграции), добавлена миграция `0005`, удален command-фильтр старта в пользу кнопочного входа через текст.
- Почему: устранить переполнение `INTEGER` и связанные падения/задержки при нажатии кнопок; довести интерфейс до режима без command-хендлеров.
- Подсистемы: database schema/migrations, handlers/common, startup UX.
- Риск: средний (изменение схемы users).

### aae24cd
- Дата: 2026-04-11
- Сообщение: `feat: simplify navigation and add all-day tap checkins`
- Что сделано: главное меню сокращено до `Привычки/Дневник/Настройки`, вторичные разделы перенесены в `Настройки`, добавлен слот `all_day`, реализована отметка выполнения по нажатию на привычку, исправлен краш в checkin callback parsing.
- Почему: уменьшить перегрузку интерфейса, ускорить ежедневные отметки и устранить падение при нажатиях.
- Подсистемы: handlers UX/navigation, habits checkin flow, schedule engine, migrations/time_slot enum.
- Риск: средний (изменение callback-контрактов и enum time_slot).

### 2b02c5d
- Дата: 2026-04-11
- Сообщение: `docs: append menu consolidation and all-day habit behavior`
- Что сделано: append-only спецификации и журнал коммитов дополнены правилами по новой структуре меню, слоту `all_day` и one-tap отметкам привычек.
- Почему: зафиксировать новые UX-контракты и не потерять функциональные изменения.
- Подсистемы: documentation (product/ai specs, commits log).
- Риск: низкий.

### 8f01757
- Дата: 2026-04-11
- Сообщение: `fix: persist enum values to match postgres enum literals`
- Что сделано: в ORM-моделях enum-колонки переведены на сохранение `.value` (через `values_callable`) вместо имен enum.
- Почему: устранить ошибку `invalid input value for enum habit_type: "NEGATIVE"` при создании привычки.
- Подсистемы: db models / enum serialization.
- Риск: средний (затрагивает запись/чтение enum-полей).

### 969a7f3
- Дата: 2026-04-11
- Сообщение: `docs: append enum serialization fix and latest commit entries`
- Что сделано: append-only спецификации и журнал коммитов дополнены фиксацией исправления enum-serializaton и связанных изменений.
- Почему: поддержание полного неизменяемого аудита функционала.
- Подсистемы: documentation.
- Риск: низкий.

### 2dd8903
- Дата: 2026-04-11
- Сообщение: `feat: streamline routine ui and add dated day-offs with weekly review flow`
- Что сделано: упрощен рабочий интерфейс рутины, управление привычками вынесено в настройки, добавлены emoji-иконки привычек, day-off выбор по датам недели/месяца, исправлен export user-context, добавлено воспроизведение ГС в дневнике, внедрен weekly digest с комментарием в дневник.
- Почему: снизить когнитивную нагрузку в ежедневном режиме и закрыть ключевые UX/надежность проблемы.
- Подсистемы: handlers UX/navigation, habits FSM, export flow, diary playback, day-off UX, background jobs, db schema.
- Риск: средний-высокий (изменены callback-контракты, добавлен фоновой джоб и новая таблица).
