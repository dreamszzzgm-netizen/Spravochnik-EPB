# DATA_MODEL.md — Spravoshnik EPB v1.2

## 1. Назначение

Документ фиксирует целевую реляционную модель данных Spravoshnik EPB v1.

Целевая СУБД: PostgreSQL.

Основные принципы:
- нормализованные основные сущности;
- отдельные таблицы N:M;
- soft delete для важных сущностей;
- audit отдельно от бизнес-таблиц;
- файлы физически хранятся вне БД;
- динамические поля не заменяют основные колонки;
- бизнес-инварианты обеспечиваются сервисами и, где возможно, ограничениями БД.

---

## 2. Базовые системные поля

Для большинства основных таблиц:

```text
id
created_at
created_by
updated_at
updated_by
deleted_at
deleted_by
version
```

`version` используется для optimistic locking там, где возможны конкурентные изменения.

---

## 3. organizations

Организации: юридические лица, ИП, филиалы.

Поля:

```text
id
organization_type
parent_organization_id NULL
full_name
short_name
inn
kpp NULL
ogrn NULL
ogrnip NULL
legal_address NULL
actual_address NULL
residence_address NULL
director_name NULL
phone NULL
email NULL
bank_details JSONB NULL
passport_data JSONB NULL
comment NULL
created_at
created_by
updated_at
updated_by
deleted_at
deleted_by
version
```

Правила:
- `parent_organization_id` используется для филиала;
- ИП может иметь `ogrnip`, `residence_address`, `passport_data`;
- история старых реквизитов отдельно не ведётся.

Индексы:
- `inn`;
- `ogrn`;
- `ogrnip`;
- `short_name`;
- `parent_organization_id`.

---

## 4. organization_contacts

Контактные лица внутри организации.

```text
id
organization_id FK organizations
full_name
position NULL
phone NULL
email NULL
note NULL
is_primary BOOLEAN
created_at
updated_at
deleted_at
```

Правило:
- у организации может быть много контактов;
- желательно ограничение: не более одного `is_primary = true` среди активных контактов.

---

## 5. opos

ОПО.

```text
id
name
registration_number NULL
hazard_class NULL
address NULL
registration_date NULL
owner_organization_id FK organizations
operator_organization_id FK organizations
comment NULL
created_at
created_by
updated_at
updated_by
deleted_at
deleted_by
version
```

Связи:
- организация-владелец;
- эксплуатирующая организация.

---

## 6. hazard_signs

Справочник признаков опасности.

```text
id
code NULL
name
is_active
sort_order
```

---

## 7. opo_hazard_signs

N:M между ОПО и признаками опасности.

```text
opo_id FK opos
hazard_sign_id FK hazard_signs
PRIMARY KEY (opo_id, hazard_sign_id)
```

---

## 8. opo_activity_types

Справочник видов деятельности ОПО.

```text
id
name
is_active
sort_order
```

---

## 9. opo_activities

N:M.

```text
opo_id FK opos
activity_type_id FK opo_activity_types
PRIMARY KEY (opo_id, activity_type_id)
```

---

## 10. technical_device_types

Типы технических устройств.

```text
id
code
name
description NULL
is_active
sort_order
```

Примеры:
- сосуд;
- котёл;
- трубопровод;
- резервуар;
- газопровод;
- другое.

---

## 11. technical_devices

Постоянная карточка оборудования.

```text
id
owner_organization_id FK organizations
opo_id FK opos NULL
type_id FK technical_device_types
name
manufacturer NULL
serial_number NULL
model NULL
manufacture_year NULL
commissioning_date NULL
passport_number NULL
comment NULL
created_at
created_by
updated_at
updated_by
deleted_at
deleted_by
version
```

Правила:
- устройство может существовать без ОПО;
- `owner_organization_id` обязателен;
- одна физическая единица создаётся один раз.

Индексы:
- `owner_organization_id`;
- `opo_id`;
- `type_id`;
- `serial_number`.

---

## 12. building_types

Типы зданий/сооружений.

```text
id
code
name
is_active
sort_order
```

---

## 13. buildings

Здания и сооружения.

```text
id
owner_organization_id FK organizations
opo_id FK opos NULL
type_id FK building_types
name
address NULL
purpose NULL
construction_year NULL
area NULL
floors NULL
comment NULL
created_at
created_by
updated_at
updated_by
deleted_at
deleted_by
version
```

Правила:
- `owner_organization_id` обозначает владельца карточки здания/сооружения и не подменяет `opos.owner_organization_id`/`opos.operating_organization_id`;
- при привязке к ОПО возможное расхождение владельцев проверяется и показывается пользователю, но не исправляется молча.

---

## 14. custom_field_definitions

Определения дополнительных полей.

```text
id
entity_type
entity_subtype_id NULL
field_key
label
data_type
unit NULL
is_required
is_active
sort_order
validation_rules JSONB NULL
```

`entity_type` например:
- organization;
- opo;
- technical_device;
- building;
- contract;
- expertise.

`entity_subtype_id` используется, например, для конкретного типа технического устройства.

---

## 15. custom_field_values

Значения дополнительных полей.

```text
id
field_definition_id FK custom_field_definitions
entity_type
entity_id
value_json JSONB
created_at
updated_at
UNIQUE(field_definition_id, entity_type, entity_id)
```

Правило:
- тип значения валидируется по definition;
- основные критичные данные не должны уходить сюда вместо нормальных колонок.

---

## 16. contracts

Договоры.

```text
id
customer_organization_id FK organizations
customer_contact_id FK organization_contacts NULL
number
contract_date
start_date NULL
end_date NULL
original_end_date NULL
amount NUMERIC
currency CHAR(3) DEFAULT 'RUB'
status
comment NULL
created_at
created_by
updated_at
updated_by
deleted_at
deleted_by
version
```

Статусы:
- draft;
- approval;
- signed;
- in_progress;
- suspended;
- completed;
- terminated;
- archived.

`original_end_date` фиксируется один раз при первом переходе `approval -> signed` и хранит исходный договорный срок. `end_date` после подписания является действующим сроком и изменяется только подписанным дополнительным соглашением.

`amount` является материализованной действующей суммой:

```text
SUM(active contract_items.price)
+ SUM(active signed contract_addenda.amount_delta)
```

Итоговая сумма не может быть отрицательной.

Уникальность номера может быть настроена в рамках года/организации.

---

## 17. contract_responsibles

Несколько ответственных сотрудников.

```text
contract_id FK contracts
employee_id FK employees
role_note NULL
PRIMARY KEY (contract_id, employee_id)
```

Ответственные могут изменяться до terminal-статуса договора.

---

## 17.1. contract_suspensions

```text
id
contract_id FK contracts
started_at TIMESTAMPTZ
ended_at TIMESTAMPTZ NULL
reason NOT NULL
created_by FK users
created_at TIMESTAMPTZ
```

Ограничение: одновременно не более одного открытого периода на договор. В PostgreSQL это дополнительно обеспечивается partial unique index:

```text
UNIQUE(contract_id) WHERE ended_at IS NULL
```

---

## 17.2. contract_addenda

Дополнительные соглашения к договору.

```text
id
contract_id FK contracts
number
addendum_date DATE
status
amount_delta NUMERIC NULL
currency CHAR(3) DEFAULT 'RUB'
new_end_date DATE NULL
description NULL
signed_at TIMESTAMPTZ NULL
created_by FK users
updated_by FK users
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
deleted_at TIMESTAMPTZ NULL
version
```

Статусы:
- draft;
- approval;
- signed;
- cancelled.

Правила:
- дополнительное соглашение не заменяет исходный договор;
- `signed` и `cancelled` являются terminal-статусами дополнительного соглашения;
- изменение суммы/срока применяется только после перехода соглашения в `signed`;
- при подписании `signed_at` фиксируется один раз;
- сумма договора пересчитывается из active items + всех active signed addenda, поэтому повторный вызов signing не может повторно применить delta;
- `new_end_date`, если задан, меняет `contracts.end_date`, но не `contracts.original_end_date`;
- продление срока требует непустого бизнес-обоснования в `description`;
- projected effective amount не может стать отрицательным;
- исторические значения договора воспроизводимы по `original_end_date`, неизменяемым после подписания contract items и цепочке подписанных addenda.

`document_id` намеренно **не входит в физическую таблицу CP4.2**. Опциональная связь дополнительного соглашения с документом добавляется миграцией Stage 8 после появления Documents-модуля.

---

## 18. contract_items

Предметы договора.

```text
id
contract_id FK contracts
name
expertise_type_id FK expertise_types
price NUMERIC
currency CHAR(3) DEFAULT 'RUB'
comment NULL
created_at
updated_at
deleted_at
version
```

До подписания предметы договора изменяемы по бизнес-правам. После подписания состав предметов и их цены замораживаются.

Базовая сумма договора = сумма активных `contract_items.price`. Действующая сумма дополнительно включает `amount_delta` всех active signed `contract_addenda`.

---

## 19. Связи предметов договора с предметами экспертизы

Критичная связь не реализуется через `subject_type + subject_id`.

### 19.1. contract_item_technical_devices

```text
contract_item_id FK contract_items
technical_device_id FK technical_devices
PRIMARY KEY (contract_item_id, technical_device_id)
```

### 19.2. contract_item_buildings

```text
contract_item_id FK contract_items
building_id FK buildings
PRIMARY KEY (contract_item_id, building_id)
```

Предмет договора должен иметь минимум одну связь хотя бы в одной таблице.

Будущая документация добавляется отдельной FK-связью миграцией.

---

## 20. expertise_types

Справочник типов экспертиз.

```text
id
code
name
is_active
sort_order
```

---

## 21. expertises

Экспертизы.

```text
id
contract_id FK contracts
expertise_type_id FK expertise_types
status
internal_number NULL
conclusion_date NULL
safe_operation_until NULL
responsible_expert_id FK employees
comment NULL
created_at
created_by
updated_at
updated_by
deleted_at
deleted_by
version
```

Главный инвариант обеспечивается таблицей `expertise_subjects` с реальными FK.

---

## 21.1. expertise_subjects

```text
id
expertise_id FK expertises UNIQUE
technical_device_id FK technical_devices NULL
building_id FK buildings NULL
```

CHECK:

```text
(technical_device_id IS NOT NULL AND building_id IS NULL)
OR
(technical_device_id IS NULL AND building_id IS NOT NULL)
```

PostgreSQL гарантирует `1 экспертиза = 1 существующий предмет`.

---

## 22. expertise_contract_items

Экспертиза может быть связана с несколькими предметами одного договора.

```text
expertise_id FK expertises
contract_item_id FK contract_items
PRIMARY KEY (expertise_id, contract_item_id)
```

Сервис должен проверять, что все `contract_item_id` относятся к тому же `contract_id`, что и экспертиза.

---

## 23. expertise_participants

Участники экспертизы.

```text
id
expertise_id FK expertises
employee_id FK employees
participation_role
is_external_snapshot BOOLEAN DEFAULT FALSE
external_name NULL
external_details JSONB NULL
```

Роли:
- responsible_expert;
- expert;
- specialist.

Ответственный эксперт дополнительно хранится в `expertises.responsible_expert_id` для удобства и строгого инварианта.

---

## 24. inspections

Одна карточка обследования на экспертизу.

```text
id
expertise_id FK expertises UNIQUE
summary NULL
results NULL
created_at
updated_at
version
```

---

## 25. ndt_methods

Справочник методов НК.

```text
id
code
name
is_active
sort_order
```

---

## 26. inspection_ndt_results

Структурированные результаты НК.

```text
id
inspection_id FK inspections
method_id FK ndt_methods
title NULL
result_text NULL
result_data JSONB NULL
source_type NULL
created_at
updated_at
deleted_at
```

Отдельного глобального пользовательского реестра нет.

---

## 27. inspection_defects

Дефекты.

```text
id
inspection_id FK inspections
defect_type NULL
location NULL
size_description NULL
criticality NULL
description NULL
recommendation NULL
created_at
updated_at
deleted_at
```

---

## 28. inspection_photos

Связь фотографий с обследованием и, при необходимости, дефектом.

```text
id
inspection_id FK inspections
document_id FK documents
defect_id FK inspection_defects NULL
caption NULL
sort_order
```

---

## 29. inspection_reviewed_documents

Документы, рассмотренные при проведении экспертизы.

```text
inspection_id FK inspections
document_id FK documents
note NULL
sort_order
PRIMARY KEY (inspection_id, document_id)
```

Файл не копируется.

---

## 30. calculations

Расчёты внутри экспертизы.

```text
id
expertise_id FK expertises
calculation_type
title
methodology NULL
input_data JSONB NULL
formula_text NULL
calculated_result JSONB NULL
expert_result JSONB NULL
override_reason NULL
source_document_id FK documents NULL
created_at
updated_at
deleted_at
```

Правило:
- если `expert_result` отличается от автоматического результата, `override_reason` обязателен.

---

## 31. rtn_registration_attempts

Попытки регистрации заключения ЭПБ в Ростехнадзоре.

```text
id
expertise_id FK expertises
attempt_number
status
prepared_at NULL
submitted_at NULL
registered_at NULL
registry_number NULL
decision_text NULL
decision_document_id FK documents NULL
created_at
created_by
updated_at
version
```

Статусы:
- prepared;
- submitted;
- under_review;
- registered;
- rejected.

Уникальность:
```text
UNIQUE (expertise_id, attempt_number)
```

Повторная подача = новая запись.

---

## 31.1. contract_status_history

```text
id
contract_id FK contracts
from_status NULL
to_status
changed_at TIMESTAMPTZ
changed_by FK users
reason NULL
```

## 31.2. expertise_status_history

```text
id
expertise_id FK expertises
from_status NULL
to_status
changed_at TIMESTAMPTZ
changed_by FK users
reason NULL
```

## 31.3. rtn_attempt_status_history

```text
id
registration_attempt_id FK rtn_registration_attempts
from_status NULL
to_status
changed_at TIMESTAMPTZ
changed_by FK users
reason NULL
```

---

## 32. technical_device_rtn_records

Учёт технического устройства в РТН.

```text
id
technical_device_id FK technical_devices
registration_number NULL
registration_date NULL
basis NULL
application_document_id FK documents NULL
readiness_act_document_id FK documents NULL
decision_document_id FK documents NULL
status NULL
created_at
updated_at
version
```

Это отдельный процесс от регистрации заключения ЭПБ.

---

## 33. tasks

Задачи.

```text
id
title
description NULL
creator_employee_id FK employees
due_date NULL
priority
status
is_personal BOOLEAN
source_workflow_template_version_id FK workflow_template_versions NULL
source_workflow_task_template_id FK workflow_task_templates NULL
created_at
updated_at
completed_at NULL
cancelled_at NULL
deleted_at
version
```

Статусы:
- new;
- in_progress;
- completed;
- cancelled.

Просрочка вычисляется:
```text
status NOT IN (completed, cancelled)
AND due_date < current_date
```

---

## 34. task_assignees

Несколько исполнителей.

```text
task_id FK tasks
employee_id FK employees
PRIMARY KEY (task_id, employee_id)
```

---

## 35. Связи задач

Для бизнес-критичных связей задач используются FK-backed link-таблицы.

### 35.1. task_organizations
```text
task_id FK tasks
organization_id FK organizations
is_primary BOOLEAN DEFAULT FALSE
PRIMARY KEY (task_id, organization_id)
```

### 35.2. task_contracts
```text
task_id FK tasks
contract_id FK contracts
is_primary BOOLEAN DEFAULT FALSE
PRIMARY KEY (task_id, contract_id)
```

### 35.3. task_contract_items
```text
task_id FK tasks
contract_item_id FK contract_items
is_primary BOOLEAN DEFAULT FALSE
PRIMARY KEY (task_id, contract_item_id)
```

### 35.4. task_technical_devices
```text
task_id FK tasks
technical_device_id FK technical_devices
is_primary BOOLEAN DEFAULT FALSE
PRIMARY KEY (task_id, technical_device_id)
```

### 35.5. task_buildings
```text
task_id FK tasks
building_id FK buildings
is_primary BOOLEAN DEFAULT FALSE
PRIMARY KEY (task_id, building_id)
```

### 35.6. task_expertises
```text
task_id FK tasks
expertise_id FK expertises
is_primary BOOLEAN DEFAULT FALSE
PRIMARY KEY (task_id, expertise_id)
```

### 35.7. task_opos
```text
task_id FK tasks
opo_id FK opos
is_primary BOOLEAN DEFAULT FALSE
PRIMARY KEY (task_id, opo_id)
```

Для личной задачи бизнес-связи могут отсутствовать.

---

## 36. comments

Единая логическая сущность комментария.

```text
id
author_employee_id FK employees
text
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
deleted_at TIMESTAMPTZ NULL
```

Комментарии привязываются к поддерживаемым сущностям через FK-backed link-таблицы.

### 36.1. comment_tasks
```text
comment_id FK comments UNIQUE
task_id FK tasks
```

### 36.2. comment_contracts
```text
comment_id FK comments UNIQUE
contract_id FK contracts
```

### 36.3. comment_expertises
```text
comment_id FK comments UNIQUE
expertise_id FK expertises
```

На v1.2 один комментарий относится ровно к одному объекту из поддерживаемых типов; это проверяется сервисом создания комментариев. При расширении добавляются новые link-таблицы.

---

## 37. comment_mentions

```text
comment_id FK comments
employee_id FK employees
PRIMARY KEY (comment_id, employee_id)
```

Упоминание создаёт уведомление после commit через outbox/job.

---

## 38. employee_function_roles

Справочник профессиональных/бизнес-функций сотрудника. Он не используется как authorization-role.

```text
id
code UNIQUE
name
is_active
```

Примеры:
- manager;
- contract_responsible;
- expert;
- specialist;
- accountant.

---

## 39. employee_function_role_assignments

```text
employee_id FK employees
function_role_id FK employee_function_roles
PRIMARY KEY (employee_id, function_role_id)
```

---

## 40. workflow_templates

Логический шаблон workflow.

```text
id
name
scope_type
is_active
description NULL
created_at TIMESTAMPTZ
created_by FK users
```

`scope_type`, например:
- expertise;
- contract;
- opo_control.

---

## 40.1. workflow_template_versions

Редакция шаблона workflow.

```text
id
workflow_template_id FK workflow_templates
version_number
is_active
created_at TIMESTAMPTZ
created_by FK users
UNIQUE(workflow_template_id, version_number)
```

Существующие задачи не меняются при публикации новой версии workflow.

---

## 40.2. workflow_task_templates

```text
id
workflow_template_version_id FK workflow_template_versions
title
description NULL
assignee_function_role_id FK employee_function_roles NULL
relative_due_days NULL
priority
sort_order
is_required
```

При создании задач сохраняется источник шаблона:

```text
tasks.source_workflow_template_version_id FK workflow_template_versions NULL
tasks.source_workflow_task_template_id FK workflow_task_templates NULL
```

Если ORM не поддерживает добавление этих полей через композицию модели, они физически присутствуют в `tasks`.

---

## 41. documents

Логический документ.

```text
id
title
document_type_id FK document_types NULL
status
current_version_id FK document_versions NULL
created_at
created_by
updated_at
deleted_at
deleted_by
version
```

Статусы:
- draft;
- working;
- final;
- archived.

---

## 42. stored_files

```text
id
storage_key UNIQUE
sha256 CHAR(64) NOT NULL
size_bytes BIGINT NOT NULL
mime_type
created_at TIMESTAMPTZ
created_by FK users NULL
```

## 42.1. document_versions

```text
id
document_id FK documents
version_number
stored_file_id FK stored_files
original_filename
is_hidden_backup BOOLEAN
created_at TIMESTAMPTZ
created_by FK users
```

UNIQUE:

```text
(document_id, version_number)
```

`documents.current_version_id` должен ссылаться на версию того же `document_id`. Рекомендуется composite FK/unique strategy либо эквивалентный DB constraint; одной application-проверки недостаточно.

---

## 43. Связи документов

Для критичных связей используются реальные FK link-таблицы:

### document_organizations
```text
document_id FK documents
organization_id FK organizations
PRIMARY KEY (document_id, organization_id)
```

### document_opos
```text
document_id FK documents
opo_id FK opos
PRIMARY KEY (document_id, opo_id)
```

### document_technical_devices
```text
document_id FK documents
technical_device_id FK technical_devices
PRIMARY KEY (document_id, technical_device_id)
```

### document_buildings
```text
document_id FK documents
building_id FK buildings
PRIMARY KEY (document_id, building_id)
```

### document_contracts
```text
document_id FK documents
contract_id FK contracts
PRIMARY KEY (document_id, contract_id)
```

### document_expertises
```text
document_id FK documents
expertise_id FK expertises
PRIMARY KEY (document_id, expertise_id)
```

### document_tasks
```text
document_id FK documents
task_id FK tasks
PRIMARY KEY (document_id, task_id)
```

### document_pmlas
```text
document_id FK documents
pmla_id FK pmlas
PRIMARY KEY (document_id, pmla_id)
```

---

## 44. document_types

```text
id
code
name
is_active
sort_order
```

---

## 45. document_templates

```text
id
document_type_id FK document_types
name
stored_file_id FK stored_files
version_number
context_schema_id FK template_context_schemas
is_active
applicability_rules JSONB NULL
created_at
created_by
```

---

## 45.1. template_context_schemas

```text
id
schema_key
version
schema_json JSONB
is_active
created_at
UNIQUE(schema_key, version)
```

Стабильные ключи:

```text
organization.full_name
opo.registration_number
technical_device.serial_number
expertise.internal_number
```

---

## 46. generated_documents

Факт генерации. `context_snapshot` хранит минимальный безопасный immutable snapshot данных, необходимых для воспроизводимости, без секретов и избыточных персональных данных.

```text
id
document_id FK documents
template_id FK document_templates
generator_key NULL
organization_id FK organizations NULL
opo_id FK opos NULL
technical_device_id FK technical_devices NULL
building_id FK buildings NULL
contract_id FK contracts NULL
expertise_id FK expertises NULL
pmla_id FK pmlas NULL
template_version
generator_version NULL
context_schema_version NULL
context_hash NULL
context_snapshot JSONB NULL
generated_at TIMESTAMPTZ
generated_by FK users
```

CHECK: для одной генерации заполнен ровно один основной context FK из списка выше. Если документ агрегирует данные связанных сущностей, дополнительные связи восстанавливаются через `document_*` link-таблицы и `context_snapshot`.

---

## 47. normative_document_types

Типы НПД.

```text
id
code
name
is_active
```

---

## 48. normative_documents

Логическая карточка НПД.

```text
id
type_id FK normative_document_types
number NULL
title
issuer NULL
status
source_url NULL
created_at
updated_at
deleted_at
version
```

## 48.1. normative_document_versions

```text
id
normative_document_id FK normative_documents
revision_number
document_date NULL
effective_from NULL
effective_to NULL
document_id FK documents NULL
source_url NULL
created_at
created_by
UNIQUE(normative_document_id, revision_number)
```

Старая редакция не перезаписывается.

---

## 49. Применимость НПД

Для применимости используются реальные FK.

### 49.1. normative_document_technical_device_types
```text
normative_document_id FK normative_documents
technical_device_type_id FK technical_device_types
PRIMARY KEY (normative_document_id, technical_device_type_id)
```

### 49.2. normative_document_building_types
```text
normative_document_id FK normative_documents
building_type_id FK building_types
PRIMARY KEY (normative_document_id, building_type_id)
```

### 49.3. normative_document_expertise_types
```text
normative_document_id FK normative_documents
expertise_type_id FK expertise_types
PRIMARY KEY (normative_document_id, expertise_type_id)
```

---

## 50. expertise_normative_document_versions

```text
expertise_id FK expertises
normative_document_version_id FK normative_document_versions
is_auto_suggested
PRIMARY KEY (expertise_id, normative_document_version_id)
```

Экспертиза фиксирует конкретную редакцию НПД.

---

## 51. pmlas

```text
id
opo_id FK opos
period_start DATE NULL
period_end DATE NULL
status
current_document_id FK documents NULL
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
deleted_at TIMESTAMPTZ NULL
version
```

---

## 51.1. pmla_hazardous_substances

```text
id
pmla_id FK pmlas
name
quantity NUMERIC NULL
unit NULL
hazard_class NULL
notes NULL
```

---

## 51.2. pmla_accident_scenarios

```text
id
pmla_id FK pmlas
code NULL
title
description
consequences NULL
response_actions NULL
sort_order
```

---

## 51.3. pmla_responsibles

```text
pmla_id FK pmlas
employee_id FK employees
responsibility_role
PRIMARY KEY (pmla_id, employee_id, responsibility_role)
```

---

## 51.4. pmla_emergency_services

```text
id
pmla_id FK pmlas
organization_name
service_type
phone NULL
contact_details NULL
sort_order
```

---

## 52. production_control_plans

```text
id
opo_id FK opos
year
status
created_at
updated_at
deleted_at
version
UNIQUE(opo_id, year)
```

---

## 52.1. production_control_inspections

```text
id
plan_id FK production_control_plans
title
inspection_date DATE NULL
responsible_employee_id FK employees NULL
status
summary NULL
created_at
updated_at
deleted_at
version
```

---

## 52.2. production_control_violations

```text
id
inspection_id FK production_control_inspections
description
severity NULL
detected_at DATE NULL
status
created_at
updated_at
deleted_at
```

---

## 52.3. production_control_actions

```text
id
violation_id FK production_control_violations NULL
plan_id FK production_control_plans
title
description NULL
responsible_employee_id FK employees NULL
due_date DATE NULL
status
result NULL
created_at
updated_at
deleted_at
version
```

CHECK: `plan_id` обязателен; если указан `violation_id`, нарушение должно относиться к проверке того же плана.

---

## 53. Ограничения производственного контроля

1. `production_control_inspection.plan_id` определяет план проверки.
2. Каждое нарушение относится ровно к одной проверке.
3. Мероприятие всегда относится к плану; связь с нарушением опциональна.
4. При наличии `violation_id` его проверка должна принадлежать тому же `plan_id`.
5. Завершённое мероприятие хранит результат; удаление выполняется логически.

---

## 54. employees

```text
id
full_name
position NULL
phone NULL
email NULL
employment_type
created_at
updated_at
deleted_at
version
```

`employment_type`:
- staff;
- external_expert.

Текущая доступность сотрудника вычисляется по периодам отсутствия, а не хранится дублирующим флагом.

---

## 54.1. employee_absences

```text
id
employee_id FK employees
absence_type
date_from DATE
date_to DATE
comment NULL
created_at TIMESTAMPTZ
created_by FK users
CHECK(date_to >= date_from)
```

Типы минимум:
- vacation;
- sick_leave;
- other.

---

## 55. expert_profiles

Дополнительные стабильные данные эксперта, не дублирующие аттестации.

```text
employee_id FK employees PRIMARY KEY
category_note NULL
details JSONB NULL
```

---

## 55.1. expert_attestations

```text
id
employee_id FK employees
certificate_number NULL
category NULL
issued_at DATE NULL
valid_until DATE NULL
status NULL
created_at
updated_at
```

## 55.2. expert_attestation_areas

```text
id
attestation_id FK expert_attestations
area_code NULL
area_name
```

## 55.3. expert_attestation_documents

```text
attestation_id FK expert_attestations
document_id FK documents
PRIMARY KEY (attestation_id, document_id)
```

Аттестации являются единственным источником данных о номере удостоверения, областях и периодах действия.

---

## 56. users

```text
id
employee_id FK employees UNIQUE
username UNIQUE
password_hash
is_active
is_superuser
failed_login_count
locked_until TIMESTAMPTZ NULL
last_login_at TIMESTAMPTZ NULL
password_changed_at TIMESTAMPTZ NULL
must_change_password BOOLEAN DEFAULT FALSE
created_at
updated_at
```

Пароли в открытом виде не хранятся.

---

## 56.1. user_sessions

Серверные пользовательские сессии.

```text
id
user_id FK users
session_token_hash UNIQUE
created_at TIMESTAMPTZ
last_activity_at TIMESTAMPTZ
expires_at TIMESTAMPTZ
revoked_at TIMESTAMPTZ NULL
ip_address NULL
user_agent NULL
```

Правила:
- в БД хранится hash токена сессии, а не исходный token;
- logout помечает сессию revoked;
- администратор может отозвать все активные сессии пользователя;
- inactivity timeout проверяется сервером.

---

## 56.2. password_reset_events

Для административного сброса и принудительной смены пароля.

```text
id
user_id FK users
initiated_by FK users
created_at TIMESTAMPTZ
completed_at TIMESTAMPTZ NULL
reason NULL
```

Секреты/одноразовые токены в открытом виде не журналируются.

---

## 57. roles

Authorization-роли пользователей. Не смешиваются с `employee_function_roles`.

```text
id
code UNIQUE
name
is_system
```

---

## 58. permissions

```text
id
code UNIQUE
name
description NULL
```

Примеры:
- contracts.view;
- contracts.create;
- contracts.change_status;
- expertises.edit;
- expertises.register_rtn;
- documents.generate;
- users.manage;
- settings.manage.

---

## 59. role_permissions

```text
role_id FK roles
permission_id FK permissions
PRIMARY KEY (role_id, permission_id)
```

---

## 60. user_role_assignments

Назначение authorization-роли конкретному пользователю.

```text
id
user_id FK users
role_id FK roles
scope_type
scope_config JSONB NULL
assigned_at TIMESTAMPTZ
assigned_by FK users
revoked_at TIMESTAMPTZ NULL
```

`scope_type`:
- ALL;
- ASSIGNED;
- RELATED;
- OWN.

UNIQUE для одной активной комбинации `(user_id, role_id, scope_type)` обеспечивается partial unique index `WHERE revoked_at IS NULL`.

`scope_config` зарезервирован для будущих ограничений подразделения/организационной единицы; на v1.2 он не заменяет backend-проверку бизнес-связей.

---

## 61. notifications

```text
id
user_id FK users
type
title
message
entity_type NULL
entity_id NULL
is_read
is_important
created_at
read_at NULL
dedup_key NULL
```

`dedup_key` помогает не создавать одинаковое уведомление бесконечно.

Для записей с непустым `dedup_key` создаётся UNIQUE/partial UNIQUE index, чтобы дедупликация работала и при параллельных worker.

---

## 62. reminders

Личные напоминания.

```text
id
user_id FK users
title
remind_at
is_done
created_at
```

---

## 63. calendar_event_sources

Отдельная физическая таблица может не понадобиться.

Календарь агрегирует события из:
- contracts;
- tasks;
- expertises;
- opos;
- technical_devices;
- buildings;
- rtn_registration_attempts;
- reminders.

Если позже потребуется кэш, он создаётся отдельно.

---

## 64. audit_events

```text
id
timestamp
user_id FK users NULL
action
entity_type NULL
entity_id NULL
summary
result NULL
request_id NULL
correlation_id NULL
ip_address NULL
metadata JSONB NULL
```

Не хранить секреты, пароли, полные AI prompts с ПД.

---

## 64.1. background_jobs

```text
id
job_key
job_type
status
attempt_count
scheduled_at TIMESTAMPTZ NULL
started_at TIMESTAMPTZ NULL
finished_at TIMESTAMPTZ NULL
last_error NULL
payload JSONB NULL
correlation_id NULL
created_at TIMESTAMPTZ
```

`job_key` — идемпотентный ключ конкретной операции/запуска, а не постоянный идентификатор типа job. Уникальность задаётся для активного/смыслового окна конкретного job-type через соответствующий partial/composite index.

## 64.2. outbox_events

```text
id
event_type
aggregate_type
aggregate_id NULL
payload JSONB
status
created_at TIMESTAMPTZ
processed_at TIMESTAMPTZ NULL
attempt_count
last_error NULL
correlation_id NULL
```

---

## 65. import_jobs

```text
id
import_type
source_document_id FK documents NULL
status
created_by
created_at
confirmed_at NULL
result_summary JSONB NULL
```

Статусы:
- uploaded;
- parsed;
- validated;
- awaiting_confirmation;
- imported;
- failed;
- cancelled.

---

## 66. import_rows

```text
id
import_job_id FK import_jobs
row_number
raw_data JSONB
normalized_data JSONB
validation_errors JSONB NULL
duplicate_candidates JSONB NULL
decision NULL
```

---

## 67. recognition_jobs

```text
id
source_document_id FK documents
document_type_guess NULL
status
provider_type
created_by
created_at
completed_at NULL
```

---

## 68. recognition_fields

```text
id
recognition_job_id FK recognition_jobs
field_key
extracted_value JSONB
confidence NUMERIC NULL
user_value JSONB NULL
is_confirmed
```

Запись в рабочие сущности выполняется только после подтверждения.

---

## 69. ai_operation_metadata

Опциональная техническая таблица без содержимого prompts.

```text
id
operation_type
provider
model NULL
is_external
status
started_at
completed_at NULL
error_code NULL
user_id NULL
```

По умолчанию prompt/response не сохраняются.

---

## 70. backup_runs

```text
id
started_at
completed_at NULL
status
storage_location
app_version
schema_version
size_bytes NULL
manifest JSONB
created_by NULL
```

---

## 71. system_settings

Только несекретные настройки.

```text
key PRIMARY KEY
value_json
updated_at
updated_by
```

Секреты должны храниться отдельным защищённым механизмом.

---

## 72. numbering_sequences

```text
id
document_type_id FK document_types
year NULL
prefix NULL
current_value
format_pattern
UNIQUE(document_type_id, year, prefix)
```

Выдача следующего номера выполняется транзакционно с блокировкой строки последовательности.

Пример:
```text
ЭПБ-{number:03d}/{year}
```

---

## 73. Основные связи

```text
organizations 1 ── N organization_contacts

organizations 1 ── N technical_devices (owner_organization_id)
organizations 1 ── N buildings (owner_organization_id)

opos 1 ── N technical_devices
opos 1 ── N buildings

contracts 1 ── N contract_items
contracts 1 ── N contract_suspensions
contracts 1 ── N contract_addenda
contracts N ── 1 organizations

contract_items N ── M subjects

expertises N ── 1 contracts
expertises N ── M contract_items
expertises 1 ── 1 subject

expertises 1 ── 0..1 inspections
expertises 1 ── N calculations
expertises 1 ── N rtn_registration_attempts
expertises N ── M normative_documents

tasks N ── M employees
tasks N ── M business entities

documents 1 ── N document_versions
documents N ── M business entities

opos 1 ── N pmlas
opos 1 ── N production_control_plans

users 1 ── N user_role_assignments
roles 1 ── N user_role_assignments
roles N ── M permissions
employees N ── M employee_function_roles
users 1 ── N user_sessions
```

---

## 74. Ограничения целостности

Обязательные проверки:

1. Экспертиза имеет ровно один предмет экспертизы.
2. Тип предмета должен существовать в допустимом справочнике.
3. Экспертиза и её contract_items относятся к одному договору.
4. Один inspection на expertise.
5. Номер попытки РТН уникален внутри экспертизы.
6. При registered попытке должны быть `registry_number` и `registered_at`.
7. При ручном изменении расчётного результата обязательна причина.
8. Завершённая задача не может считаться просроченной.
9. Soft-deleted записи не участвуют в обычных рабочих выборках.
10. Физический файл одной версии не должен случайно перезаписываться другой версией.
11. Одновременно существует не более одного открытого `contract_suspensions` на договор.
12. Подписанные/отменённые `contract_addenda` не изменяются и не удаляются как обычные записи.
13. Effective contract amount не может быть отрицательной.

---

## 75. Индексы

Минимально предусмотреть индексы по:

- FK;
- status;
- due_date;
- registration_number;
- contract number/date;
- expertise status;
- RTN registry number;
- technical device serial number;
- organization INN;
- document type;
- deleted_at;
- created_at для журналов.

Составные индексы определяются после анализа реальных запросов UI.

Для CP4.2 дополнительно используется partial unique index `contract_suspensions(contract_id) WHERE ended_at IS NULL`.

---

## 76. Миграции

Все таблицы и изменения схемы создаются миграциями.

Схема не должна модифицироваться хаотично во время обычного выполнения приложения.

Stage 4 CP4.2 migration head: `0012_stage4_contract_lifecycle` (`0012_stage4_contract_lifecycle_addenda.py`).

---

## 77. Что уточняется на реализации

Технические детали, которые допускают выбор:

- конкретный ORM;
- конкретный тип UUID/BIGINT PK;
- точная реализация полиморфных ссылок;
- JSONB vs typed value tables для custom fields;
- полнотекстовый поиск;
- партиционирование журналов.

Они не должны нарушать бизнес-инварианты этого документа.

---

## 78. Data conventions

```text
бизнес-дата    → DATE
момент события → TIMESTAMPTZ
деньги         → NUMERIC + currency CHAR(3)
```

Naive datetime и `float` для денег не используются.

`field_key` динамического поля после начала использования неизменяем.

## 79. FK delete policy

По умолчанию для бизнес-данных:
- RESTRICT;
- SET NULL только при допустимом бизнес-смысле;
- soft delete.

Физический `ON DELETE CASCADE` не используется для исторически значимых данных.

## 80. Database invariants

Каждый инвариант реализуется максимально близко к БД:

```text
FK / UNIQUE / CHECK / INDEX / transaction / service rule
```

Ключевые:

1. экспертиза имеет ровно один существующий предмет;
2. одно основное обследование на экспертизу;
3. номер попытки РТН уникален внутри экспертизы;
4. contract_item принадлежит тому же договору и содержит выбранный предмет;
5. номер внутреннего документа выдаётся атомарно;
6. завершённая/отменённая задача не считается просроченной;
7. прошлый RTN attempt исторически защищён после новой попытки;
8. экспертиза ссылается на конкретную редакцию НПД;
9. максимум один открытый период приостановки договора;
10. optimistic locking обязателен для ключевых карточек;
11. профессиональная функция сотрудника не выдаёт authorization permission;
12. активная user-role-scope assignment уникальна;
13. подписанное дополнительное соглашение является единственным состоянием, влияющим на addendum-изменение суммы/срока договора;
14. documents.current_version_id принадлежит тому же document;
15. notification dedup_key уникален для непустых значений;
16. workflow task сохраняет source workflow revision;
17. linked production-control violation/action относятся к одному плану;
18. `contracts.original_end_date` после первого подписания неизменяем;
19. действующая сумма договора = active items + active signed addenda deltas и неотрицательна;
20. signed/cancelled addendum terminal и не отменяется задним числом.

---

## Статус

**Документ:** Data Model v1.2  
**Состояние:** Synchronized with Stage 4 CP4.2 contract lifecycle/addenda backend  
**Следующий этап:** Stage 5/6/8 добавляют свои реальные FK/providers без изменения CP4.2 contract invariants.
