# Stage 4 CP4.2 — Approved Amendments

## Alembic revision identifier

During TDD execution on 2026-08-12, the originally planned revision identifier `0012_stage4_contract_lifecycle_addenda` was found to exceed the default Alembic `alembic_version.version_num` length used by the project.

The user explicitly approved shortening only the **revision id** to:

```text
0012_stage4_contract_lifecycle
```

The migration filename remains:

```text
alembic/versions/0012_stage4_contract_lifecycle_addenda.py
```

The parent remains:

```text
0011_stage4_contracts_core
```

This amendment supersedes the longer revision-id string wherever the original design/implementation plan names it. It does not change the approved CP4.2 functional scope, schema contents, state machine, permissions, or acceptance criteria.
