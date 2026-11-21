# Подготовка продукта и контракт готовности

Контракт `go-product-platform.setup.json` отслеживается Git. Это исполняемая
конфигурация доверенного продукта, как Makefile. Проверяйте diff перед запуском.
`gpp init --setup --profile <profile> --json` выдаёт обязательные компоненты и
инструменты. Все пути/cwd относительны корню Git; переход за корень запрещён.
`argv` — массив аргументов без shell interpolation; timeout по умолчанию 300 секунд,
можно задать 1–3600. Используйте скрипты продукта для условной установки/миграций;
не вставляйте команды оболочки в одну строку argv. В setup не входят release/deploy.

## Профили и критерии

Все стартовые пути опросника используют один контракт готовности. При подготовке
без описания продукта проверяется техническая основа выбранного стека; предметные
функции и бизнес-требования не придумываются. Для идеи или готовых требований
основа учитывает выясненные ограничения, но настройка не означает реализацию
всего продукта. Подтверждение понимания требований предшествует выбору итогового
стека; установка выполняется после согласования конкретного плана настройки.

Общие компоненты каждого профиля:

| Компонент | Что подготовить | Чем подтвердить |
|---|---|---|
| go | Go-модуль, feature-oriented пакеты, entrypoint, тесты | `go test ./...`, `go build ./...` из корня модуля |
| contracts | Protobuf, Buf lint и генераторы Connect, зафиксированные версии | `buf lint`, `buf generate`, сборка полученных контрактов |
| database | PostgreSQL + pgx/sqlc и миграции; для offline desktop — SQLite по HLD | Реальная проверка подключения, применение миграций в отдельной dev/test БД и integration-тест |
| environment | Версии инструментов, env example, команды запуска/остановки, изоляция worktree | Smoke-тест процесса и healthcheck; проверить отдельные порты/БД/logs каждого worktree |

Дополнения:

| Профиль | Компоненты | Что проверить |
|---|---|---|
| go-api | Общая основа, PostgreSQL | API/integration + модульные тесты |
| web | frontend, ui, e2e | Vite + React + TS; shadcn/Tailwind; production build, typecheck, браузерный smoke с вызовом API |
| ai | web + ai | AI SDK/AI Elements по месту, серверная граница ключей; тест адаптера без секрета, smoke с провайдером при наличии доступа |
| desktop | frontend, ui, e2e, desktop | Wails v3 + React, bindings, SQLite/PG по архитектуре; native build и smoke приложения на целевой ОС |
| mobile-native | mobile | Go API и выбранные SwiftUI/Compose клиенты; SDK, сборка и smoke на симуляторе/эмуляторе выбранной платформы |
| custom | Общая основа + нужные дополнительные компоненты | Адаптации и исключения записать в HLD/workflow, добавить исполняемые checks |

Tools в шаблоне — минимум, дополните graphify, sqlc, goose, mise, Swift/Xcode,
Android SDK/Gradle и другими фактически выбранными инструментами. Для pg/мобильных
проверок CLI version недостаточно: проверки components должны обращаться к среде.
Зависимость «нужны credentials» нельзя заменить фиктивной зелёной проверкой.

## Установка по официальным инструкциям

Перед выполнением сверить выбранную версию и поддерживаемую ОС; зафиксировать
совместимые версии в mise/go.mod/package manager lock/конфигурации генераторов.
Не копировать патч-версии из старого handbook без проверки доступности.

- [Go modules](https://go.dev/doc/tutorial/create-module): `go mod init <module>`
  только при отсутствии модуля. Идентификатор брать из продукта, не из имени папки.
- [Connect Go](https://connectrpc.com/docs/go/getting-started/) и
  [Buf](https://buf.build/docs/cli/installation/): подготовить .proto и config,
  генерацию Go/Connect; версии plugins фиксировать. Домен не зависит от транспорта.
- [pgx](https://github.com/jackc/pgx), [sqlc](https://docs.sqlc.dev/en/stable/overview/install.html),
  [goose](https://github.com/pressly/goose): БД под отдельной dev-ролью, миграции и
  тестовые данные. Не использовать production URL и привилегии приложения для provisioning.
- [Vite](https://vite.dev/guide/): новый React/TS UI — `pnpm create vite <app> --template react-ts`;
  существующий использовать на месте, затем `pnpm install`, typecheck/build.
- [shadcn Vite](https://ui.shadcn.com/docs/installation/vite): Tailwind, alias,
  components.json и минимальный компонент. По запросу canvas применить утверждённый кит;
  не смешивать киты без архитектурного решения.
- [Wails v3](https://v3.wails.io/getting-started/setup/),
  [CLI](https://v3.wails.io/reference/cli/): установить совместимый wails3,
  проверить локально `wails3 init -l`, выбрать React template и пустой целевой каталог.
  Не предполагать, что шаблон называется react-ts во всех версиях.
- [Playwright](https://playwright.dev/docs/intro): установить выбранные браузеры,
  webServer/baseURL, smoke с реальным приложением и сохранением trace при ошибке.
- [AI SDK](https://ai-sdk.dev/docs/getting-started): установить в нужное TS-приложение,
  выбрать провайдера по запросу; серверный ключ только в окружении.
- Для mobile выбрать только нужную платформу, прочитать официальные SDK instructions
  и глобальные Swift/Compose навыки. Не устанавливать оба SDK без продуктовой причины.

## Пример фрагмента контракта

```json
{
  "name": "go",
  "paths": ["go.mod", "cmd/api/main.go"],
  "checks": [
    {"argv": ["go", "test", "./..."], "cwd": ".", "timeout": 300},
    {"argv": ["go", "build", "./..."], "cwd": "."}
  ]
}
```

Это только один компонент, не полный готовый план. Заполните остальные компоненты
шаблона. Команды setup исполняются последовательно до установки недостающих skills;
поставьте необходимые uv/Node/Git раньше них. После установки зависимостей повторный
запуск должен безопасно восстанавливать состояние, сохраняя код и данные продукта.
Не записывайте «выполнено» в readiness JSON: doctor каждый раз запускает checks заново.

## Проектный набор агентных материалов

При полной настройке после согласования списка `skills-project --json` установите
навыки, агентов и референсы в `.agents/` и `.claude/` продукта (`skills-project --approve`;
`init --setup-plan --approve` выполняет этот шаг автоматически). Эти копии и lock
хранятся в Git и имеют приоритет над глобальными. Корневые AGENTS.md
и CLAUDE.md требуют на русском соблюдать software-development-workflow.
MANUAL.md содержит настройку, окружение, запуск и проверки конкретного продукта.
