# Organization Smart Import Hardening — Design

## Context

This design extends the verified `agent/parallel-org-smart-import` checkpoint without changing CP5.2 Workflow Engine internals. The existing flow already parses pasted text into a read-only preview and requires explicit `Применить к форме` before normal save.

## Goals

1. Make organization create **and edit** forms legal-form aware:
   - legal entity / branch: INN, KPP, OGRN, director, legal/actual addresses;
   - individual entrepreneur: INN, OGRNIP, residence address, passport details.
2. Enforce the same applicability rules on the backend so the UI is not the only protection layer.
3. Add local file import for TXT, DOCX, XLSX, PDF, PNG, JPG/JPEG while preserving preview-before-apply.
4. Keep passport and other personal data fully local: no external HTTP/AI calls and no prompt/response logging.

## Data flow

`File or pasted text -> local extraction/OCR -> deterministic requisites parser -> candidate -> duplicate/applicability validation -> preview -> explicit apply -> normal organization create/update`

Recognition never writes directly to organization tables.

## Local extraction

- TXT: UTF-8 text.
- DOCX: local ZIP/XML extraction from `word/document.xml`.
- XLSX: local ZIP/XML extraction from worksheets/shared strings.
- PDF: local embedded-text extraction first; when text is absent/insufficient, render pages locally and pass them to the local OCR adapter.
- PNG/JPG/JPEG: local OCR adapter.

OCR is executed only through a local Tesseract process. `TESSERACT_CMD` may point to a local executable. Default command is `tesseract`; OCR language defaults to `rus+eng`. If OCR is required but unavailable, the API fails closed with a clear local-component error; data is never sent to an external service.

Safety limits:
- upload limit: 5 MiB;
- Office expanded ZIP limit: 20 MiB;
- PDF page limit: 20 pages;
- OCR subprocess timeout: 30 seconds per page;
- temporary files are deleted after extraction.

## Legal-form validation

A focused domain helper validates the final payload:

- IP rejects non-empty `legal_address`, `actual_address`, `director_name`, KPP and OGRN.
- Legal entity / branch rejects non-empty `residence_address`, `passport_details` and OGRNIP.
- Switching type clears stored fields that are no longer applicable.
- Identifier upsert continues to remove identifiers omitted from the submitted legal-form-specific list.

Validation errors are returned as 422 and do not partially persist data.

## UI

Both `/organizations/new` and `/organizations/[id]/edit`:
- show only fields relevant to the selected organization type;
- show only relevant identifiers;
- allow either pasted text or a file for smart import;
- show preview/warnings before any values are applied;
- keep explicit final save separate from smart import.

## Tests

Backend:
- legal-form validator create/update/type-switch behavior;
- TXT/DOCX/XLSX extraction;
- PDF embedded-text extraction;
- image/PDF OCR adapter success through a stubbed local runner and fail-closed missing-Tesseract behavior;
- upload size and unsupported/corrupt file handling;
- import preview remains read-only.

Frontend:
- new and edit forms expose the correct fields per legal form;
- smart-import file upload calls preview API and does not auto-save;
- applying preview is explicit;
- lint/typecheck/Vitest/build remain green.

## Integration guardrails

- no Workflow Engine model/service/migration edits;
- no automatic merge into CP5.2 or Pilot;
- no external AI/network processing of organization documents;
- hardening branch remains a review checkpoint until CI is green.