# Spravoshnik EPB — опытный экземпляр Pilot v0.1

Этот документ описывает первый технический экземпляр Spravoshnik EPB для работы в доверенной локальной сети организации.

Pilot v0.1 предназначен для контролируемой проверки системы на отдельном сервере или Windows-ПК с Docker Desktop. Это **не публичный интернет-сервис** и пока не полная замена всех рабочих процессов ЭПБ.

## 1. Что входит в Pilot v0.1

Docker Compose поднимает:

- PostgreSQL 17;
- одноразовый сервис миграции Alembic;
- FastAPI backend;
- background worker;
- scheduler;
- Next.js frontend;
- ручной maintenance-сервис резервного копирования.

Из локальной сети публикуется только frontend. PostgreSQL и backend не открывают отдельные host-порты.

Схема:

```text
ПК сотрудников в LAN
        |
        | http://IP_СЕРВЕРА:3000
        v
      frontend
        |
        | /backend/*
        v
      backend
       / | \
      /  |  \
PostgreSQL worker scheduler
        |
   local storage
```

Удалённая работа допускается через защищённый VPN с доступом в LAN. Не публикуйте порт Pilot напрямую в интернет.

## 2. Требования к серверу

Для первого опытного экземпляра рекомендуется:

- Windows 10/11 Pro или Windows Server / Linux;
- Docker Desktop или Docker Engine с Docker Compose v2;
- постоянный LAN IPv4-адрес или DHCP reservation;
- достаточно свободного места для PostgreSQL, файлов и резервных копий;
- локальная папка проекта на диске, который регулярно резервируется.

Для Windows все дальнейшие примеры можно выполнять из PowerShell в корне репозитория.

Проверьте Docker:

```powershell
docker version
docker compose version
```

## 3. Получение Pilot-ветки

В уже клонированном репозитории:

```powershell
git fetch origin
git checkout agent/stage5-cp59-pilot-deployment
git pull --ff-only origin agent/stage5-cp59-pilot-deployment
```

Перед реальной эксплуатацией мы позднее заменим ветку на закреплённый release/tag. Для текущего опытного экземпляра используем эту review-ветку.

## 4. Создание локальной конфигурации

Скопируйте шаблон:

```powershell
Copy-Item deploy\pilot\.env.pilot.example deploy\pilot\.env.pilot
```

Откройте:

```text
deploy/pilot/.env.pilot
```

Обязательно замените:

```dotenv
POSTGRES_PASSWORD=CHANGE_ME
```

на длинный случайный пароль.

После этого обновите пароль и в `DATABASE_URL`.

Пример структуры URL:

```text
postgresql+psycopg://spravoshnik:ВАШ_ПАРОЛЬ@postgres:5432/spravoshnik
```

Если пароль содержит символы вроде `@`, `:`, `/`, `#`, `%`, их необходимо URL-кодировать в `DATABASE_URL`.

Файл `deploy/pilot/.env.pilot` содержит секреты и **не должен попадать в Git**.

### SESSION_COOKIE_SECURE

Для первого Pilot внутри доверенной LAN без TLS шаблон содержит:

```dotenv
SESSION_COOKIE_SECURE=false
```

Когда приложение будет переведено на HTTPS/TLS, значение **обязательно** должно стать:

```dotenv
SESSION_COOKIE_SECURE=true
```

## 5. Подготовка локальных каталогов

Создайте каталоги, если Docker ещё не создал их сам:

```powershell
New-Item -ItemType Directory -Force var\pilot\storage | Out-Null
New-Item -ItemType Directory -Force var\pilot\backups | Out-Null
```

Здесь будут храниться рабочие файлы Pilot и созданные резервные копии.

Данные PostgreSQL находятся в Docker named volume `pilot_postgres_data`.

## 6. Проверка конфигурации Compose

Перед первым запуском:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml config
```

Команда должна завершиться без ошибок.

В Pilot-файле наружу публикуется только frontend-порт, по умолчанию `3000`.

## 7. Сборка образов

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml build
```

Используются два собственных образа:

- `spravoshnik-epb-backend:pilot`;
- `spravoshnik-epb-frontend:pilot`.

Backend image один и тот же для API, migration, worker и scheduler. Это гарантирует, что приложение и история миграций не расходятся между процессами.

## 8. Первый запуск

Запустите стек:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml up -d
```

Порядок запуска контролируется Compose:

1. PostgreSQL становится healthy;
2. `migrate` выполняет `alembic upgrade head`;
3. backend/worker/scheduler разрешается стартовать только после успешной миграции;
4. frontend ожидает healthy backend.

Если миграция завершилась ошибкой, не обходите этот gate ручным запуском backend — сначала устраните причину.

Проверьте состояние:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml ps -a
```

Ожидаемо:

- `postgres` — running / healthy;
- `migrate` — exited с кодом `0`;
- `backend` — running / healthy;
- `worker` — running;
- `scheduler` — running;
- `frontend` — running.

## 9. Создание первого администратора

Администратор **не создаётся автоматически** и пароль не хранится в Compose.

После успешного первого запуска выполните:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml run --rm backend spravoshnik-bootstrap-superuser --username admin --name "Администратор"
```

Команда интерактивно запросит пароль. Не передавайте рабочий пароль в командной строке и не записывайте его в `.env.pilot`.

Повторное создание пользователя с тем же username должно завершиться ошибкой, а не заменить существующую учётную запись молча.

## 10. Проверка backend health

Поскольку backend специально не опубликован наружу, проверяем его из контейнера:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health/ready').read().decode())"
```

Readiness проверяет минимум:

- соединение с PostgreSQL;
- доступность и возможность записи в локальное файловое хранилище.

## 11. Доступ с компьютеров сотрудников

На серверном Windows-ПК выполните:

```powershell
ipconfig
```

Найдите IPv4-адрес сетевого адаптера локальной сети, например:

```text
192.168.1.25
```

Если `PILOT_HTTP_PORT=3000`, на другом компьютере той же LAN откройте:

```text
http://192.168.1.25:3000
```

Если Windows Firewall блокирует входящее соединение, разрешите только выбранный Pilot frontend-порт для доверенного LAN-профиля. PostgreSQL `5432` и backend `8000` открывать в локальную сеть для этой схемы не требуется.

Для удалённого сотрудника используйте VPN в сеть организации и затем тот же внутренний адрес. Не делайте port-forward из интернета на Pilot.

## 12. Проверка frontend → backend proxy

Frontend обращается к API same-origin через `/backend/*`.

После запуска можно проверить с серверного ПК:

```powershell
Invoke-WebRequest http://127.0.0.1:3000/backend/health/live
```

Запрос должен пройти через Next.js frontend к внутреннему backend-сервису.

## 13. Просмотр журналов

Все сервисы:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml logs --tail 200
```

Конкретный сервис:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml logs -f backend
```

или:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml logs -f worker
```

Не публикуйте логи наружу без проверки на конфиденциальные данные.

## 14. Нормальная остановка и повторный запуск

Остановить контейнеры без удаления данных:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml stop
```

Запустить снова:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml start
```

Можно удалить контейнеры, сохранив PostgreSQL volume и host storage:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml down
```

После этого вернуть стек:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml up -d
```

### ОПАСНО: `down -v`

**Не используйте `docker compose down -v` для обычной остановки Pilot.**

Ключ `-v` удаляет named volumes, включая рабочую базу PostgreSQL. В production/pilot-инструкциях он допустим только как намеренный разрушительный сброс после проверки резервной копии.

## 15. Ручная резервная копия

Перед обновлением системы и перед любыми рискованными административными действиями создавайте резервную копию.

Запуск:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml --profile maintenance run --rm backup
```

В каталоге:

```text
var\pilot\backups\<UTC_TIMESTAMP>\
```

появятся:

```text
database.dump
storage.tar.gz
manifest.txt
```

`database.dump` — PostgreSQL custom-format dump.

`storage.tar.gz` — снимок локального файлового хранилища.

`manifest.txt` содержит timestamp, версию приложения и Alembic schema head, если его удалось прочитать.

Скопируйте критичные резервные копии также на отдельный локальный носитель/сервер организации согласно внутренней политике хранения.

## 16. Обновление Pilot

Рекомендуемый порядок:

1. убедиться, что текущий экземпляр работает;
2. создать резервную копию;
3. получить новую проверенную версию Git;
4. пересобрать образы;
5. запустить миграцию/стек;
6. проверить health и вход пользователя.

Пример:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml --profile maintenance run --rm backup

git fetch origin
git pull --ff-only

docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml build

docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml up -d

docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml ps -a
```

После обновления обязательно повторите `/health/ready` и вход в программу.

Не обновляйте опытный сервер на произвольный незавершённый commit. Используйте только checkpoint/release, который мы отдельно признали GREEN.

## 17. Восстановление из резервной копии

Восстановление — потенциально разрушительная операция. Выполняйте его только администратором и только после проверки выбранной копии.

Обязательный безопасный порядок:

1. остановить процессы, которые могут писать данные;
2. **создать safety backup текущего состояния**;
3. выбрать совместимую резервную копию `database.dump + storage.tar.gz`;
4. восстановить PostgreSQL;
5. восстановить соответствующее файловое хранилище;
6. проверить/применить миграции для версии приложения;
7. запустить сервисы;
8. проверить `/health/ready`;
9. войти в программу;
10. проверить несколько реальных организаций, договоров, задач и файлов.

Pilot v0.1 намеренно не предоставляет автоматическую кнопку «восстановить всё», чтобы случайный запуск не уничтожил рабочее состояние.

### Пример восстановления PostgreSQL

Сначала остановите writers:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml stop frontend backend worker scheduler
```

Сделайте дополнительный safety backup перед изменением текущей БД.

Далее восстановление конкретного dump выполняется через `pg_restore` внутри PostgreSQL/maintenance-контейнера. Точная команда зависит от выбранной копии и того, восстанавливается ли существующая или новая база. Перед первым реальным восстановлением процедура должна быть отрепетирована на тестовом экземпляре, а не впервые на единственной рабочей базе.

Файлы из `storage.tar.gz` должны восстанавливаться **из той же timestamp-папки**, что и `database.dump`, чтобы БД и storage соответствовали друг другу.

## 18. Изменение порта

Если порт `3000` занят, измените в `.env.pilot`:

```dotenv
PILOT_HTTP_PORT=3100
```

После перезапуска пользователи будут открывать:

```text
http://IP_СЕРВЕРА:3100
```

## 19. Что сохраняется при перезапуске

При обычных `stop`, `start`, `restart`, `down`, `up` сохраняются:

- PostgreSQL named volume;
- `var/pilot/storage`;
- `var/pilot/backups`;
- локальный `deploy/pilot/.env.pilot`.

Не удаляйте эти данные при чистке Docker/диска без резервной копии.

## 20. Ограничения этого опытного экземпляра

Pilot v0.1 — **технический опытный экземпляр**.

На текущем checkpoint:

- backend Organizations/OPO/TD/Buildings/Contracts/Tasks уже реализован стадийно;
- CP5.1 Tasks Core завершён;
- CP5.2 Workflow Engine ещё не подключён;
- CP5.3 Contract↔Tasks automation ещё не подключена;
- Stage 6 полноценных экспертиз ещё не завершён;
- пользовательские production-экраны больше не показывают mock/demo-бизнес-данные; уже подключённые разделы используют реальные API, а неподключённые показывают честное пустое/недоступное состояние;
- реестры Contracts и Tasks в Next.js ещё не подключены к уже существующим backend API;
- NПД, уведомления и реальные dashboard-метрики относятся к последующим этапам;
- автоматический weekly backup/retention ещё не включён;
- TLS/reverse proxy ещё не включён;
- внешний интернет-доступ не поддерживается.

Поэтому на этом этапе Pilot используется для:

- проверки установки и обновления;
- проверки многопользовательского LAN-доступа;
- проверки авторизации/серверной части;
- проверки хранения данных и файлов;
- проверки PostgreSQL, worker/scheduler и health;
- раннего UX/эксплуатационного тестирования без фиктивных производственных записей.

Полноценную производственную эксплуатацию текущих экспертиз рекомендуем начинать после Stage 6 и следующих acceptance-checkpoint-ов.

## 21. Быстрая диагностика

Показать состояние:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml ps -a
```

Последние backend logs:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml logs --tail 200 backend
```

Последние migration logs:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml logs migrate
```

Проверить readiness:

```powershell
docker compose --env-file deploy/pilot/.env.pilot -f docker-compose.pilot.yml exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health/ready').read().decode())"
```

Проверить frontend proxy:

```powershell
Invoke-WebRequest http://127.0.0.1:3000/backend/health/live
```

## 22. Правило Pilot v0.1

Перед обновлением, восстановлением, очисткой Docker volumes или переносом сервера сначала создайте и проверьте резервную копию.

Для обычной работы используйте LAN/VPN. Прямой публичный доступ в интернет для этого Pilot не предусмотрен.
