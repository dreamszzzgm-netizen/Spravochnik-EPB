# DEVELOPMENT_PLAN.md — Spravoshnik EPB v1.2

## 1. Назначение

Документ задаёт порядок реализации Spravoshnik EPB v1.

Главный принцип:

> Не реализовывать всё сразу. Каждый этап должен иметь ограниченный scope, тесты и критерии приёмки.

---

# 2. Общая последовательность

```text
0. Подготовка проекта
1. Core + пользователи
2. Организации
3. ОПО + техустройства + здания
4. Договоры
5. Задачи + workflow
6. Экспертизы
7. Обследование + НК + дефекты + расчёты
8. Документы + генерация
9. РТН
10. НПД
11. Календарь + уведомления
12. Импорт + recognition
13. AI
14. ПМЛА + производственный контроль
15. Аналитика
16. Backup + system health
17. Полировка UX
18. Финальный аудит и релиз
```

---

# 3. Этап 0 — фундамент проекта

Цель:
создать правильный технический каркас.

Работы:
- выбрать Python web framework;
- PostgreSQL;
- ORM;
- migrations;
- конфигурация;
- logging;
- test framework;
- базовая структура модулей;
- CI;
- dev/test config;
- storage abstraction;
- StoredFile/FileBlob;
- обязательный SHA-256;
- background jobs;
- Scheduler отдельно от Worker;
- persistent outbox;
- correlation/request id;
- data conventions (`DATE`, `TIMESTAMPTZ`, `NUMERIC + currency`).

Критерии:
- приложение стартует;
- БД создаётся миграциями;
- health endpoint работает;
- тестовая БД поднимается;
- тесты запускаются одной командой.

Не реализовывать бизнес-модули до завершения этого этапа.

---

# 4. Этап 1 — пользователи, сотрудники, permissions

Реализовать:
- employees;
- users;
- password hash;
- employee business/function roles отдельно от authorization roles;
- roles;
- permissions;
- user_role_assignments + scope;
- user_sessions;
- login/logout;
- inactivity timeout;
- administrative session revoke;
- password reset / must-change-password flow;
- superuser;
- backend authorization;
- audit входов;
- блокировка неудачных входов.

Тесты:
- login;
- wrong password;
- lock;
- permission denied;
- superuser;
- user-role combinations;
- permission + scope;
- employee function does not grant permission;
- session revoke;
- inactivity timeout;
- password reset without secret leakage.

Приёмка:
- разные authorization-роли реально получают разный доступ;
- профессиональная функция сотрудника не меняет права автоматически.

---

# 5. Этап 2 — организации

Реализовать:
- список;
- создание;
- редактирование;
- юрлицо/ИП/филиал;
- головная организация;
- контакты;
- основной контакт;
- soft delete;
- история.

Тесты:
- validation;
- филиал;
- основной контакт;
- soft delete/restore;
- permissions.

---

# 6. Этап 3 — ОПО, технические устройства, здания

Реализовать:
- карточка ОПО;
- владелец;
- оператор;
- признаки опасности;
- виды деятельности;
- technical devices;
- buildings;
- optional OPO link;
- custom fields;
- контрольные даты;

Критический тест:
- устройство без ОПО разрешено;
- здание без ОПО разрешено;
- удаление ОПО не удаляет физически устройства.

---

# 7. Этап 4 — договоры

Реализовать:
- contracts;
- responsibles;
- customer contact;
- contract items;
- subjects;
- сумма;
- статусы;
- приостановка;
- возобновление;
- расторжение;
- завершение readiness check;
- дополнительные соглашения;
- применение подписанного изменения суммы/срока.

Тесты:
- статусные переходы;
- предметы;
- сумма;
- пауза;
- расторжение;
- невозможность завершить при блокерах.

---

# 8. Этап 5 — задачи и workflow

Реализовать:
- tasks;
- multiple assignees;
- links;
- comments;
- priorities;
- overdue computation;
- versioned workflow templates;
- business-function based assignee resolution;
- automatic task creation;
- сохранение source workflow version/task-template.

Тесты:
- several assignees;
- overdue;
- workflow instantiation;
- contract suspension/resume;
- permissions.

---

# 9. Этап 6 — экспертизы

Реализовать:
- expertise card;
- 1 expertise = 1 subject;
- contract links;
- participants;
- status machine;
- create workflow tasks;
- comments;
- history.

Критические тесты:
- нельзя два предмета экспертизы;
- нельзя item другого договора;
- ровно один responsible expert;
- статус меняется только допустимым переходом.

---

# 10. Этап 7 — обследование

Реализовать:
- one inspection per expertise;
- NDT methods;
- results;
- defects;
- photos;
- reviewed documents;
- calculations.

Тесты:
- unique inspection;
- reviewed document without duplicate file;
- override calculation requires reason.

---

# 11. Этап 8 — документы

Сначала:
- document metadata;
- versions;
- StoredFile;
- обязательный SHA-256;
- storage;
- FK-backed link tables;
- upload/download;
- preview;
- soft delete.

Затем:
- document types;
- templates;
- variables;
- context builder;
- DOCX generation;
- PDF generation;
- generated document versions.

Тесты:
- file security;
- permissions;
- versioning;
- multi-links;
- generation;
- invalid template.

---

# 12. Этап 9 — Ростехнадзор

Два независимых потока:

## Equipment accounting
- RTN records technical device.

## Expertise registration
- attempts;
- statuses;
- package;
- rejection;
- repeat attempt;
- registry number.

Критические тесты:
- attempt numbering;
- rejection does not overwrite first attempt;
- registration changes expertise status;
- repeat submission creates new record.

---

# 13. Этап 10 — НПД

Реализовать:
- directory;
- types;
- versioned editions;
- files;
- statuses;
- applicability;
- expertise selection of concrete editions;
- suggestions;
- local text extraction/search where предусмотрено.

После стабильной локальной базы:
- actuality checking adapter.

---

# 14. Этап 11 — календарь и уведомления

Реализовать:
- unified calendar service;
- production calendar;
- reminders;
- notifications;
- 30/14/5;
- dedup;
- scheduler.

Тесты:
- weekends;
- due soon;
- overdue;
- duplicate notifications;
- paused contract.

---

# 15. Этап 12 — импорт

Реализовать сначала Excel:
- job;
- parse;
- validate;
- duplicate candidates;
- preview;
- confirmation;
- transactional save.

После:
- documents recognition pipeline.

Нельзя смешивать импорт и recognition в один большой сервис.

---

# 16. Этап 13 — ИИ

Сначала:
- AIProvider interface;
- local provider;
- AI Gateway;
- policy check;
- PII sanitizer;
- user preview.

Только затем:
- external provider;
- extraction;
- drafting;
- NPD assistance.

Безопасность тестируется отдельно.

---

# 17. Этап 14 — ПМЛА и производственный контроль

После стабильных ОПО/documents/generation:
- PMLA;
- versions;
- context;
- hazardous substances;
- accident scenarios;
- responsibles;
- emergency services;
- production plans;
- inspections;
- violations;
- corrective actions;
- reports;
- templates.

Не делать раньше document generation.

---

# 18. Этап 15 — аналитика

Только после появления реальных рабочих данных.

Реализовать:
- manager dashboard;
- contract metrics;
- expertise metrics;
- tasks;
- employees;
- customers;
- financial aggregates.

Не создавать отдельный data warehouse v1.

---

# 19. Этап 16 — backup и system health

Реализовать:
- DB backup;
- file backup;
- template/settings backup;
- manifest;
- checksum verification;
- `pg_dump` success verification;
- test restore procedure;
- weekly scheduler;
- retention 3;
- manual backup;
- restore;
- health page.

Критический тест:
- реальное восстановление тестовой копии.

---

# 20. Этап 17 — UX

Только после настройки всех функциональных вкладок.

Работы:
- единый дизайн;
- dark theme;
- breadcrumbs;
- быстрые действия;
- фильтры;
- сохранённые фильтры;
- таблицы;
- формы;
- уведомления;
- accessibility;
- desktop Windows browser UX.

---

# 21. Этап 18 — финальная приёмка

Отдельный read-only аудит:

- git status;
- migrations;
- database constraints;
- security;
- routes;
- permissions;
- business invariants;
- documents;
- AI safety;
- backup;
- tests;
- UI;
- installation;
- concurrent editing/optimistic locking;
- atomic numbering race;
- notification deduplication under concurrent workers;
- concurrent document version creation;
- session revocation/timeout.

Финальный вердикт:
```text
PASS / FAIL
```

---

# 22. Правило этапов

Каждый этап должен иметь:

```text
Scope
Non-goals
DB migrations
Implementation
Unit tests
Integration tests
Acceptance checks
Documentation update
Commit
```

Следующий этап не начинается, пока текущий не прошёл acceptance.

---

# 23. Правило промтов ИИ-разработчику

Каждый промт должен содержать:

- рабочую папку;
- ветку;
- цель этапа;
- что прочитать перед началом;
- архитектурные ограничения;
- список файлов/модулей в scope;
- что нельзя менять;
- инварианты;
- тесты;
- команды проверки;
- критерии PASS;
- требование использовать skills/subagents, если среда это поддерживает;
- запрет смешивать будущие этапы в текущий.

---

# 24. Проектные документы, которые агент обязан учитывать

Перед изменениями агент должен читать актуальные:

```text
README.md
ARCHITECTURE.md
DATA_MODEL.md
BUSINESS_RULES.md
PERMISSIONS.md
UI_MAP.md
DEVELOPMENT_PLAN.md
AGENTS.md — если существует
HANDOVER.md / HANDOFF.md — если существует
```

---

# 25. Git-подход

Рекомендуемо:
- отдельная ветка на крупный этап/подэтап;
- маленькие осмысленные commits;
- не смешивать рефакторинг вне scope;
- перед commit запускать проверки;
- документацию обновлять вместе с изменённым контрактом системы.

---

# 26. Приёмочный шаблон каждого этапа

```text
A. Scope
B. Database
C. Backend
D. UI
E. Tests
F. Invariants
G. Security
H. Regression
I. Verdict
```

---

# 27. Приоритеты v1

Критично:
- организации;
- ОПО;
- устройства/здания;
- договоры;
- экспертизы;
- задачи;
- документы;
- РТН;
- НПД;
- security;
- backup.

Высокий:
- workflow;
- import;
- recognition;
- calendar;
- notifications.

Развитие после устойчивого ядра:
- сложные встроенные расчёты;
- расширенный AI;
- автоматические внешние проверки;
- расширенная аналитика.

---

# 28. Definition of Done v1

v1 готова, когда:

1. несколько пользователей работают по LAN;
2. permissions реально ограничивают действия;
3. можно провести полный путь от организации до завершённой экспертизы;
4. документы хранятся и версионируются;
5. заключение формируется;
6. РТН attempts сохраняют историю;
7. договор корректно закрывается;
8. задачи и сроки работают;
9. НПД привязываются к экспертизе;
10. импорт безопасен и подтверждаем;
11. AI не нарушает правила ПД;
12. backup реально восстанавливается;
13. критические сценарии покрыты тестами;
14. миграции воспроизводимы на чистой БД;
15. финальный приёмочный аудит — PASS.

---

## Статус

**Документ:** Development Plan v1.2  
**Состояние:** Revised and synchronized after full project review  
**Следующий этап после утверждения документации:** подготовка технического стека и Этап 0.
