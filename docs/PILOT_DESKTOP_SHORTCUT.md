# Spravoshnik EPB — запуск Pilot с рабочего стола Windows

Для обычного пользователя командная строка не требуется.

## Однократная настройка администратором

Откройте PowerShell в корне установленного Pilot и выполните:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\pilot\create-desktop-shortcuts.ps1
```

Скрипт создаёт на рабочем столе текущего пользователя два ярлыка:

- `Spravoshnik EPB` — умный запуск;
- `Остановить Spravoshnik EPB` — безопасная остановка без удаления данных.

## Что делает ярлык Spravoshnik EPB

1. Проверяет наличие локальной конфигурации Pilot.
2. Проверяет наличие Docker CLI.
3. Если Docker Engine не работает, запускает Docker Desktop.
4. Ждёт готовности Docker Engine.
5. Запускает Compose-проект `spravoshnik-epb-work` с `deploy/pilot/.env.pilot` и `docker-compose.pilot.yml`.
6. Читает `PILOT_HTTP_PORT` из `.env.pilot`.
7. Ждёт успешного ответа `/backend/health/live`.
8. Открывает Spravoshnik EPB в браузере по умолчанию.

PowerShell запускается скрыто. При ошибке пользователь получает обычное Windows-окно с сообщением на русском языке.

## Остановка

Ярлык `Остановить Spravoshnik EPB` выполняет только безопасный `docker compose stop` для проекта `spravoshnik-epb-work`.

Остановка не удаляет PostgreSQL volume, документы или резервные копии.

**Никогда не используйте `docker compose down -v` для обычной остановки Pilot.** Ключ `-v` удаляет named volume с рабочей PostgreSQL-базой.

## Важно для установки

Ярлыки содержат абсолютные пути к скриптам текущей установки. Если папку Pilot перенесли в другое место, повторно запустите `create-desktop-shortcuts.ps1` из новой папки.
