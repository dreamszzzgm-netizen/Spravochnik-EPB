# PERMISSIONS.md — Spravoshnik EPB v1.2

## 1. Назначение

Документ фиксирует ролевую модель и permissions Spravoshnik EPB v1.

Принцип:
- роли = наборы разрешений;
- backend всегда проверяет разрешения;
- UI только скрывает недоступные действия для удобства;
- суперпользователь имеет полный доступ.

---

## 2. Базовые роли

Рекомендуемые системные роли:

- Администратор
- Руководитель
- Ответственный по договору
- Эксперт
- Специалист
- Бухгалтер
- Просмотр

Эти роли являются **authorization-ролями пользователя**, а не профессиональными функциями сотрудника.

Один пользователь может иметь несколько authorization-ролей через `user_role_assignments`.
Профессиональные функции сотрудника (`expert`, `specialist`, `accountant` и т.п.) хранятся отдельно и используются для workflow/назначений, но сами по себе не дают доступа.

---

## 3. Формат permission

```text
<module>.<action>
```

Примеры:

```text
organizations.view
organizations.create
organizations.edit
organizations.delete

contracts.view
contracts.create
contracts.edit
contracts.change_status

expertises.view
expertises.create
expertises.edit
expertises.change_status
expertises.register_rtn

tasks.view
tasks.create
tasks.assign
tasks.edit
tasks.complete

documents.view
documents.upload
documents.generate
documents.delete

settings.manage
users.manage
backup.manage
```

---

# 4. Организации

Permissions:

```text
organizations.view
organizations.create
organizations.edit
organizations.delete
organizations.restore
organizations.import
```

Рекомендации:
- руководитель: всё кроме системного восстановления;
- ответственный по договору: view/create/edit;
- эксперт: view;
- специалист: view связанных;
- бухгалтер: view;
- администратор: всё.

---

# 5. ОПО

```text
opo.view
opo.create
opo.edit
opo.delete
opo.restore
opo.manage_control_dates
```

---

# 6. Технические устройства

```text
technical_devices.view
technical_devices.create
technical_devices.edit
technical_devices.delete
technical_devices.restore
technical_devices.import
technical_devices.manage_rtn_accounting
```

---

# 7. Здания и сооружения

```text
buildings.view
buildings.create
buildings.edit
buildings.delete
buildings.restore
buildings.import
```

---

# 8. Договоры

```text
contracts.view
contracts.create
contracts.edit
contracts.delete
contracts.restore
contracts.change_status
contracts.terminate
contracts.complete
contracts.manage_responsibles
contracts.manage_items
contracts.manage_addenda
```

Назначение специальных прав CP4.2:
- `contracts.change_status` — только обычные переходы договора (`draft -> approval`, `approval -> signed`, архивирование) и команды приостановки/возобновления;
- `contracts.terminate` — только расторжение договора;
- `contracts.complete` — только ручное завершение после успешного серверного readiness-check;
- `contracts.manage_addenda` — создание, изменение, удаление и смена статуса дополнительных соглашений;
- `contracts.manage_items` — управление предметами договора до подписания;
- `contracts.manage_responsibles` — управление ответственными до terminal-статуса.

Одно специальное право **не заменяет** другое. Например, наличие `contracts.change_status` не разрешает расторжение или завершение, а `contracts.manage_addenda` не предоставляет `contracts.view` для чтения списка дополнительных соглашений.

Все contract permissions работают совместно со scope `ALL / ASSIGNED / RELATED / OWN`. Совпадение scope не компенсирует отсутствие требуемого permission code; отсутствие доступа к договору/вложенному дополнительному соглашению не должно раскрывать существование записи и возвращается через общий 404 policy.

Рекомендуемо:
- руководитель: полный бизнес-доступ;
- ответственный: полный доступ к своим договорам;
- эксперт: просмотр связанных;
- специалист: просмотр связанных;
- бухгалтер: просмотр + финансовые поля по необходимости;
- администратор: полный технический доступ.

---

# 9. Экспертизы

```text
expertises.view
expertises.create
expertises.edit
expertises.delete
expertises.restore
expertises.change_status
expertises.assign_experts
expertises.manage_inspection
expertises.manage_calculations
expertises.manage_normative_docs
expertises.manage_conclusion
expertises.register_rtn
expertises.mark_customer_received
expertises.complete
```

---

# 10. Обследование / НК / дефекты

```text
inspection.view
inspection.edit
inspection.manage_ndt
inspection.manage_defects
inspection.manage_photos
inspection.manage_reviewed_documents
```

Эксперт:
- полный доступ к своим экспертизам.

Специалист:
- доступ к тем экспертизам, где назначен.

---

# 11. Задачи

```text
tasks.view
tasks.view_all
tasks.create
tasks.assign
tasks.edit
tasks.change_status
tasks.delete
tasks.restore
tasks.comment
```

Обычный сотрудник:
- видит свои задачи;
- может менять статус своих задач;
- может комментировать связанные задачи.

Руководитель:
- видит все задачи;
- может назначать исполнителей.

---

# 12. Документы

```text
documents.view
documents.upload
documents.edit_metadata
documents.create_version
documents.generate
documents.download
documents.delete
documents.restore
documents.manage_templates
```

Права проверяются также по связанной бизнес-сущности.

---

# 13. НПД

```text
npd.view
npd.create
npd.edit
npd.delete
npd.restore
npd.import
npd.check_actuality
npd.confirm_actuality_update
```

---

# 14. РТН

```text
rtn.view
rtn.prepare_package
rtn.submit
rtn.record_result
rtn.correct_historical_attempt
rtn.register_equipment
```

`rtn.submit` должно быть отдельным правом, не автоматически доступным всем экспертам.

---

# 15. ПМЛА / производственный контроль

```text
pmla.view
pmla.create
pmla.edit
pmla.generate

production_control.view
production_control.edit
production_control.generate_documents
```

---

# 16. Сотрудники и пользователи

```text
employees.view
employees.create
employees.edit
employees.delete

users.view
users.create
users.edit
users.reset_password
users.lock
users.unlock
users.manage_roles
users.revoke_sessions
```

Создание пользователей — только администратор.

`users.manage_roles` управляет `user_role_assignments` и их scope.
Изменение бизнес-функции сотрудника не должно автоматически выдавать authorization permissions.
`users.revoke_sessions` позволяет отозвать активные сессии пользователя.

---

# 17. Настройки

```text
settings.view
settings.manage
directories.manage
custom_fields.manage
workflows.manage
numbering.manage
ai_settings.manage
storage_settings.manage
system_health.view
```

---

# 18. Backup

```text
backup.view
backup.create
backup.restore
```

`backup.restore` — только администратор/суперпользователь.

---

# 19. Audit

```text
audit.view
```

Руководитель может видеть бизнес-аудит.
Администратор — полный системный аудит.

---

# 20. Аналитика

```text
analytics.personal
analytics.management
analytics.financial
```

---

# 21. Матрица ролей — кратко

| Область | Администратор | Руководитель | Ответственный | Эксперт | Специалист | Бухгалтер |
|---|---|---|---|---|---|---|
| Организации | полный | полный | редактирование | просмотр | связанный просмотр | просмотр |
| ОПО | полный | полный | редактирование | просмотр | просмотр | просмотр |
| Техустройства | полный | полный | редактирование | редакт. связанных | редакт. связанных | просмотр |
| Договоры | полный | полный | свои/назначенные | просмотр связанных | просмотр связанных | просмотр/финансы |
| Экспертизы | полный | полный | просмотр/контроль | свои — полный | назначенные разделы | просмотр |
| НК/обследование | полный | полный | просмотр | полный по своим | по назначению | нет |
| РТН | полный | полный | по праву | по отдельному праву | нет | нет |
| Задачи | полный | все | свои + назначение | свои | свои | свои |
| Документы | полный | полный | связанные | связанные | связанные | связанные |
| НПД | полный | просмотр/управление | просмотр | работа с НПД | просмотр | просмотр |
| Аналитика | полный | полный | ограниченно | личная | личная | финансовая |
| Пользователи | полный | нет по умолчанию | нет | нет | нет | нет |
| Настройки | полный | ограниченно | нет | нет | нет | нет |
| Backup | полный | просмотр при необходимости | нет | нет | нет | нет |

---

# 22. Scope permissions

Помимо permission важно учитывать область данных.

Пример:

```text
expertises.edit
```

не обязательно означает редактирование всех экспертиз.

Scope может быть:

```text
ALL
ASSIGNED
RELATED
OWN
```

Permission и scope всегда проверяются совместно на backend.

Физически assignment хранит `user_id + role_id + scope_type`; `scope_config` зарезервирован для будущего подразделения/организационной единицы. Scope не задаётся строковыми условиями в UI и не заменяет backend policy.

Примеры:
- эксперт редактирует `ASSIGNED`;
- руководитель — `ALL`;
- специалист — `RELATED`;
- обычный пользователь задачу — `OWN/ASSIGNED`.

---

# 23. Суперпользователь

Суперпользователь:
- обходит обычные role checks;
- используется для первоначальной настройки и аварийного администрирования;
- его действия всё равно пишутся в audit.

---

# 24. Запрещённые практики

Нельзя:
- проверять права только по наличию кнопки;
- хранить роли строковыми if по всему коду;
- давать права `admin = true` всем руководителям;
- разрешать пользователю менять собственные permissions;
- скрывать от audit действия суперпользователя.

---

## Статус

**Документ:** Permissions v1.2  
**Состояние:** Synchronized with Stage 4 CP4.2 contract lifecycle/addenda backend  
**Следующий этап:** при расширении Tasks/Expertises/Documents подключать собственные permissions/providers без ослабления contract permission isolation.
