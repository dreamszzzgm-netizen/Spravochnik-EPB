# CHANGELOG_v1.2.md — Spravoshnik EPB

## Назначение

Этот файл фиксирует изменения проектной документации v1.2 относительно комплекта v1.1 после полного cross-document review.

## Критические исправления

1. Разделены профессиональные функции сотрудников и authorization-роли пользователей.
2. Добавлена физическая связь `user_role_assignments` с `scope_type`.
3. Добавлена модель отзывных серверных `user_sessions`.
4. Добавлена модель административного password reset без хранения секретов в audit.
5. Удалено дублирование аттестационных данных между `expert_profiles` и `expert_attestations`.
6. Удалено дублирующее поле `contracts.suspension_started_at`; источник истины — `contract_suspensions`.
7. Добавлена модель `contract_addenda`.
8. Универсальные `task_links` заменены FK-backed link-таблицами.
9. Комментарии унифицированы; mentions имеют явные FK.
10. Применимость НПД переведена на FK-backed связи с типами ТУ, зданий и экспертиз.
11. Шаблон документа теперь использует `StoredFile` и `TemplateContextSchema`.
12. Добавлена проверка целостности `documents.current_version_id`.
13. Workflow шаблоны получили версии; задачи сохраняют source revision.
14. PMLA получил структурированные вещества, сценарии, ответственных и аварийные службы.
15. Производственный контроль получил структуру `plan → inspection → violation → action`.
16. Отсутствия сотрудников вынесены в отдельные исторические периоды.
17. Audit дополнен `result`, `request_id`, `correlation_id`, `ip_address`.
18. Notification deduplication закреплена DB-ограничением.
19. Numbering scope получил уникальность и атомарную выдачу.
20. Уточнена семантика idempotency key фоновых jobs.

## Синхронизация документов

Изменены:
- `README.md`;
- `ARCHITECTURE.md`;
- `ARCHITECTURE_REVIEW_DECISIONS.md`;
- `DATA_MODEL.md`;
- `BUSINESS_RULES.md`;
- `PERMISSIONS.md`;
- `UI_MAP.md`;
- `DEVELOPMENT_PLAN.md`.

## Изменения плана разработки

- из Этапа 3 удалён неутверждённый `clone device`;
- Этап 1 расширен session/scope/password-reset тестами;
- Этап 4 включает дополнительные соглашения;
- workflow тестируется с version provenance;
- Этап 14 реализует структурированный PMLA и производственный контроль;
- финальная приёмка включает concurrency/race/session сценарии.

## Статус

**Версия документации:** 1.2  
**Готовность:** разрешено начинать технический Этап 0.  
**Ограничение:** бизнес-миграции Этапа 1+ должны соответствовать `DATA_MODEL.md` v1.2.
