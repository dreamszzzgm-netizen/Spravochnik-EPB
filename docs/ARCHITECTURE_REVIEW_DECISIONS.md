# ARCHITECTURE_REVIEW_DECISIONS.md

## Основание

Документ фиксирует решения после архитектурного review перед началом реализации.

## Принятые изменения

1. `ExpertiseSubject` с реальными FK и CHECK вместо `subject_type + subject_id`.
2. Связи документов через реальные link-таблицы с FK.
3. `StoredFile` отдельно от `Document` и `DocumentVersion`.
4. SHA-256 обязателен для каждого файла.
5. Отдельная status history для Contract, Expertise и RTN attempt.
6. Отдельные периоды `ContractSuspension`.
7. Optimistic locking `version` обязателен для ключевых карточек.
8. Dynamic fields имеют неизменяемый `field_key`.
9. НПД хранит редакции; экспертиза ссылается на конкретную редакцию.
10. DB transaction отделена от filesystem/OCR/AI/PDF side effects.
11. Scheduler отделён от Worker.
12. Для side effects после commit используется persistent outbox.
13. Нумерация атомарна в PostgreSQL.
14. Workflow фиксирует версию шаблона происхождения задач.
15. TemplateContextSchema версионируется.
16. AI использует PUBLIC/INTERNAL/CONFIDENTIAL/PERSONAL.
17. `extract/classify` используют schema-validated response.
18. Recognition confidence хранится по полям.
19. Import хранит сессию, строки, ошибки, решения и итог.
20. Duplicate detection определяется отдельно по сущностям.
21. Permission отделён от scope данных.
22. Стандарт дат/времени/денег: DATE / TIMESTAMPTZ / NUMERIC + currency.
23. `ON DELETE CASCADE` не применяется к исторически значимым бизнес-данным.
24. GlobalSearchService выделяется отдельно.
25. Экспертные аттестации моделируются отдельными сущностями.
26. Предыдущая RTN attempt защищается как историческая.
27. Integration/repository тесты критичной SQL-логики выполняются на PostgreSQL.
28. Generated documents сохраняют provenance.
29. Health checks имеют OK/WARNING/ERROR/UNKNOWN.
30. Correlation ID проходит через request/service/job/audit/log.

## Итог

Архитектура остаётся **модульным монолитом на PostgreSQL**.

Review усиливает ссылочную целостность, воспроизводимость истории, безопасность конкурентной работы и надёжность фоновых/файловых операций, не усложняя систему микросервисами.

## Дополнение v1.2

По результатам полного cross-document review дополнительно приняты решения:

31. Authorization-роли пользователя отделены от профессиональных функций сотрудника.
32. Добавлен `user_role_assignments` с scope.
33. Добавлены отзывные серверные `user_sessions` и события административного reset пароля.
34. Аттестационные данные удалены из `expert_profiles`; единственный источник — `expert_attestations`.
35. Удалено дублирующее `contracts.suspension_started_at`; периоды хранятся в `contract_suspensions`.
36. Добавлена отдельная модель дополнительных соглашений к договору.
37. `task_links` заменены FK-backed link-таблицами.
38. Комментарии унифицированы и получили FK-backed связи и корректный FK для mentions.
39. Применимость НПД моделируется отдельными FK link-таблицами.
40. DOCX-шаблоны используют `StoredFile` и обязательный `TemplateContextSchema`.
41. Workflow получил логическую сущность и версионируемые revisions; задачи сохраняют source revision.
42. PMLA получил структурированные вещества, сценарии, ответственных и аварийные службы.
43. Производственный контроль моделируется как `plan → inspection → violation → action`.
44. Отсутствия сотрудников вынесены в исторические периоды.
45. Audit дополнен request/correlation/result/ip metadata.
46. Notification deduplication обеспечивается DB unique constraint.
47. Numbering sequence имеет уникальную область и атомарную выдачу.
48. Уточнена семантика job idempotency key.
49. Из Development Plan удалён неутверждённый `clone device`.
50. В финальную приёмку добавлены concurrency/race/session tests.

## Итог v1.2

Комплект документации синхронизирован для начала Этапа 0. Перед Этапом 1 миграции должны реализовать именно модель v1.2, особенно разделение EmployeeFunctionRole/UserRoleAssignment и session model.
