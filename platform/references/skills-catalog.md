# Каталог навыков ИИ — Go Product Platform v15 (глобальная установка)

> Часть руководства для поиска и выбора навыков. В v14 все выбранные общие навыки устанавливаются глобально в `~/.agents/skills` и `~/.claude/skills`; проектные навыки создаются только под конкретный продукт. См. Руководство, §18 и §47–48.

## 18. Навыки ИИ: проверенный каталог для Codex, Claude, Zed и Orca {#skills}

**Решение платформы:** небольшой общий набор навыки + профильные инструкции, подключаемые только к затронутой технологии. Не загружать все коллекции в контекст каждой LLM-задачи. Сам навык объясняет *как работать*; корректность подтверждают `go test`, `buf breaking`, Playwright и другие независимые Контрольные проверки качества. См. [локальные итерации](#native-iteration), [фоновые E2E](#background-e2e) и [архитектурные границы](#modular-plugins).

**Приоритеты:** **P0** — включить в каталог платформы; применять по подходящей задаче. **P1** — подключать, когда используется соответствующая технология. **Опционально** — только при включении опционального компонента. **Официальный** означает опубликован разработчиком технологии; **сообщество** требует собственной проверки. Ссылка ведёт на GitHub-репозиторий или конкретный `SKILL.md`.

### 18.1. Минимальный общий набор: процесс и Ядро Go {#skills-core}

| Навык / GitHub | Назначение | Выбор |
|---|---|---|
| [`verification-before-completion`](https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md) | Не разрешает объявлять задачу завершённой без свежих результатов проверок. | **P0**, Superpowers / сообщество |
| [`systematic-debugging`](https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md) | Ищет первопричину сбоя, а не маскирует симптом случайными правками. | **P0**, при ошибках |
| [`using-git-worktrees`](https://github.com/obra/superpowers/blob/main/skills/using-git-worktrees/SKILL.md) | Организует изолированные рабочие каталоги; дополняется `devctl` для отдельных БД, портов и процессов. | **P0**, агентные ветки |
| [`golang-design-patterns`](https://github.com/samber/cc-skills-golang/blob/main/skills/golang-design-patterns/SKILL.md) | Идиоматичный Go, композиция, модули и минимум ненужных интерфейсов. | **P0**, Go / сообщество |
| [`golang-database`](https://github.com/samber/cc-skills-golang/blob/main/skills/golang-database/SKILL.md) | PostgreSQL, `pgx`, транзакции, запросы, пулы и миграции. | **P0**, Go / сообщество |
| [`golang-testing`](https://github.com/samber/cc-skills-golang/blob/main/skills/golang-testing/SKILL.md) | Табличные, модульные и интеграционные тесты, фаззинг, измерения производительности и контроль поведения. | **P0**, Go / сообщество |
| [`golang-concurrency`](https://github.com/samber/cc-skills-golang/blob/main/skills/golang-concurrency/SKILL.md) | Горутины, каналы, отмена контекста, ограничение параллелизма, защита от гонок данных. | **P0**, конкурентность |
| [`golang-security`](https://github.com/samber/cc-skills-golang/blob/main/skills/golang-security/SKILL.md) | Границы доверия, SQL-инъекции, секреты, криптография и безопасная обработка ввода. | **P0**, безопасность серверной части |
| [`go-architecture-review`](https://github.com/eduardo-sl/go-agent-skills) | Проверяет направление зависимостей, владение модулями и избыточные абстракции. | **P0**, архитектурный аудит |

**Ограничение:** `golang-design-patterns` — рекомендации, а не повод создавать фабрики, адаптеры и интерфейсы «на будущее». Для контроля границ модулей добавлять **исполняемую** проверку [arch-go](https://github.com/arch-go/arch-go) или `go-arch-lint` и `golangci-lint/depguard`; это инструменты, **не** agent навыки.

### 18.2. Контракты, Wails 3 и клиентская часть {#skills-platform}

| Навык / GitHub | Назначение | Выбор |
|---|---|---|
| [`protobuf`](https://github.com/bufbuild/claude-plugins/blob/main/plugins/protobuf/skills/protobuf/SKILL.md) | `.proto`, Buf lint/breaking, генерация Go/TS/Swift/Kotlin и Connect/gRPC-контракты. | **P0**, официальный Buf |
| [`wails`](https://github.com/spf13/go-skills/blob/main/wails/SKILL.md) | Go↔JS bindings, окна, events, lifecycle и сборка desktop. | **P1**, сообщество; **обязательно адаптировать под Wails 3** |
| [`shadcn`](https://github.com/shadcn-ui/ui/blob/main/skills/shadcn/SKILL.md) | Настраивает, находит и комбинирует UI-компоненты согласно `components.json` и дизайн-токены. | **P0**, официальный shadcn |
| [`react-best-practices`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/SKILL.md) | Уменьшает лишние render, загрузку JavaScript и задержки интерфейса. | **P0**, Vercel |
| [`composition-patterns`](https://github.com/vercel-labs/agent-skills/blob/main/skills/composition-patterns/SKILL.md) | Учит собирать компоненты через композицию без громоздких props и сложных иерархий. | **P1**, архитектура React |
| [`tanstack-query-development`](https://github.com/axross/skills/blob/main/skills/tanstack-query-development/SKILL.md) | Ключи запросов, инвалидация кэша, мутации, оптимистический интерфейс, повторная загрузка и ошибки. | **P1**, слой данных |
| [`tailwind-design-system`](https://github.com/wshobson/agents/blob/main/plugins/frontend-mobile-development/skills/tailwind-design-system/SKILL.md) | Tailwind v4, семантические дизайн-токены, темы и responsive-правила. | **P1**, библиотека интерфейса |
| [`web-design-guidelines`](https://github.com/vercel-labs/agent-skills/blob/main/skills/web-design-guidelines/SKILL.md) | Ревью UX: навигация, формы, focus, accessibility и работа с клавиатурой. | **P1**, аудит интерфейса; **зафиксировать версию правил** |

**Wails:** найденный `wails` содержит устаревшую оценку статуса v3. Нельзя разрешать агенту смешивать API Wails v2/v3. Источник истины — **установленная версия Wails 3 и её официальные примеры**. Для Android/iOS не выдавать экспериментальный runtime за стабильный.

**Connect:** качественного официального отдельного Connect-Go v2 навык для выбранной версии не закреплено. Официальный Buf `protobuf` покрывает контракты; для транспорт, перехватчики, потоковая передача и ошибок дополнить его короткой **внутренней инструкцией `connectrpc-v2`**, проверяемой компиляцией и интеграционными тестами. Это **предлагаемый** проектный навык, а не публичный GitHub навык. Официальная реализация: [connectrpc/connect-go](https://github.com/connectrpc/connect-go).

### 18.3. Тестирование в коротком локальном цикле {#skills-testing}

| Навык / GitHub | Назначение | Выбор |
|---|---|---|
| [`playwright-cli`](https://github.com/microsoft/playwright-cli/blob/main/skills/playwright-cli/SKILL.md) | Агент самостоятельно открывает UI, воспроизводит E2E, анализирует снимки, трассировки и снимки экрана. | **P0**, официальный Microsoft |
| [`building-accessible-ui`](https://github.com/microsoft/a11y-llm-eval/blob/main/config/skills/building-accessible-ui/SKILL.md) | Доступные интерфейсы, навигация с клавиатуры, ARIA и проверяемые правила WCAG. | **P1**, Microsoft |

**Разделение ответственности:** навык `playwright-cli` помогает агенту диагностировать UI, а **детерминированные Playwright/Vitest-тесты** выполняются из репозитория через `make check` и фоновый E2E watcher. Успех интерактивного агента не заменяет финальная проверка на конкретном commit. См. [политику E2E](#background-e2e).

### 18.4. Опциональные AI-функции и полностью нативные клиенты {#skills-optional-platform}

| Когда подключать | Навык / GitHub | Что делает |
|---|---|---|
| ИИ-агент Service | [`ai-sdk`](https://github.com/vercel/ai/blob/main/skills/use-ai-sdk/SKILL.md) — **P1, Vercel** | Vercel AI SDK: `ToolLoopAgent`, tools, потоковая передача, models, UI транспорт; сверяет API с установленной версией. |
| AI UI / Chat | [`ai-elements`](https://github.com/vercel/ai-elements/blob/main/skills/ai-elements/SKILL.md) — **P1, Vercel** | Компоненты сообщений, tool calls, потоковая передача и ввода для shadcn. |
| Нативные iOS/macOS | [`swiftui-expert-skill`](https://github.com/AvdLee/SwiftUI-Agent-Skill/blob/main/skills/swiftui-expert-skill/SKILL.md) — **P1** | SwiftUI, состояние, навигация, производительность и доступность. |
| Swift async/await | [`swift-concurrency`](https://github.com/AvdLee/Swift-Concurrency-Agent-Skill/blob/main/skills/swift-concurrency/SKILL.md) — **P1** | Изоляция акторов, `Sendable`, структурированная конкурентность и гонки данных. |
| Нативный Android | [`jetpack-compose-performance`](https://github.com/android/skills/blob/main/jetpack-compose/jetpack-compose-performance/SKILL.md) — **P1, Google** | Оптимизирует повторную композицию, списки, state и плавность Compose. |
| Тесты на устройствах Android | [`testing-setup`](https://github.com/android/skills/blob/main/testing/testing-setup/SKILL.md) — **P1, Google** | Настраивает тестовое окружение Android и проверки на эмуляторе/устройстве. |
| OAuth/OIDC | [`secure-oauth-oidc`](https://github.com/citypaul/.dotfiles/blob/main/claude/.claude/skills/secure-oauth-oidc/SKILL.md) — **Опционально** | PKCE, tokens, JWKS и защита процесс входа; применять вместе с официальными протоколами и негативные тесты. |
| OpenBao | [`openbao-general`](https://github.com/Getty/p5-www-openbao/blob/main/.claude/skills/openbao-general/SKILL.md) — **Опционально** | KV/Auth/API-приемы для интеграции с OpenBao; **не** полноценный инструкция по обеспечению безопасности сервера. |

Здесь **не выбраны** навыки из внутреннего репозитория RustFS: они предназначены преимущественно для разработки самого RustFS, а Go-клиенту достаточно AWS SDK for Go v2, контрактных тестов совместимости с S3 и официальной [документации RustFS](https://github.com/rustfs/rustfs). Отдельные навыки по React Native/Expo подключаются только при реальном выборе этой альтернативы, чтобы не конфликтовать с Wails/native стратегией.

### 18.5. Глобальная установка и использование {#skills-agents}

Все выбранные общие навыки устанавливаются **глобально** в `~/.agents/skills/` (Codex/Zed) и `~/.claude/skills/` (Claude). Orca использует навыки фактически запущенного агента. Не копировать общие навыки в `.go-product-platform`, не создавать проектные симлинки на общие навыки. Для установки на Mac см. `gpp setup-global --skills --graphify --orca`; для нового проекта — только `gpp init --project . --offline`. Проектный навык создается по необходимости в самом проекте и не публикуется глобально автоматически.

### 18.6. Маршрутизация навыков по типу изменения {#skills-routing}

| Изменение | Основные навыки | Доказательство корректности |
|---|---|---|
| Pure Go domain / modules | `golang-design-patterns` + `golang-testing` | Affected `go test`; архитектурный lint при изменении зависимостей |
| PostgreSQL / миграции | `golang-database` + `golang-security` | Реальный локальный PG, интеграционный тест, migration check |
| Goroutines / Обработчик River | `golang-concurrency` + `golang-testing` | Race detector, timeouts, idempotency/retry tests |
| `.proto` / Connect RPC | `protobuf` | `buf lint`, `buf breaking`, генерация, контрактные тесты |
| Wails 3 bridge | `wails` **после v3-адаптации** | Desktop IPC, smoke и platform permissions |
| React UI / дизайн-система | `shadcn` + `react-best-practices` | Vitest, typecheck, Playwright и visual/a11y checks |
| Data fetching / caching | `tanstack-query-development` | Query/mutation tests и проверка invalidation |
| Ошибка E2E | `systematic-debugging` + `playwright-cli` | Воспроизводимый тест и trace конкретного commit |
| AI tools / потоковая передача | `ai-sdk` | Tool schemas, mocks, agent evals и permission tests |
| iOS / Android | SwiftUI или Compose навык **только своей платформы** | Simulator/emulator + реальные device checks |

Параллельным агентам не нужно подключать все навыки одновременно. Для конкретной задачи загрузить **один основной** и максимум несколько узких дополнительных; независимый review и проверка результата запускаются отдельно. Это снижает расход контекста, уменьшает конфликты между инструкциями и ускоряет итерации.

### 18.7. Политика доверия и управления версиями {#skills-governance}

1. **Pin commit SHA / release**, хранить `SKILL.md` и его references/scripts в проверенной версии; `main` в таблице — ссылка для чтения, **не** зафиксированная dependency.
2. Проверять исполняемые скрипты, shell-команды, сетевые обращения и инструкции изменения конфигурации. Не давать сторонним навыкам доступ к учётным данным рабочей среды.
3. Контролировать **неявные обновления**: `web-design-guidelines` загружает текущие правила из сетевого источника при каждом ревью; для воспроизводимости заменить URL на фиксированный commit/локальную копию, прежде чем включать в автономный pipeline.
4. Учитывать **drift API**: особенно Wails 3, Connect-Go v2 и mobile SDK. Авторитетнее инструкций навыков — документация установленной версии, компилятор и проверяемый тест.
5. Любое обновление навык проходит тестовый fixture: агент решает типовую задачу → запускает standard gates → сравниваются исправления, regressions, latency и затраты токенов. Результат должен быть воспроизводим.
6. Контролировать, чтобы навык не заменял архитектурные правила: KISS, YAGNI, права, audit, isolation worktree и module владение задаются **в `AGENTS.md` и контрольных проверках качества**.

Внутренние надстройки, которые ещё **нужно реализовать**: `wails3-desktop`, `connectrpc-v2`, `mobile-connect-protobuf`, `local-native-devctl`, `modular-monolith-fitness`. Для них пока нет самостоятельных GitHub-ссылок: это проектные задачи, а не выдаваемые за готовые публичные навыки. Их инструкции должны быть короткими и ссылаться на существующие стандарты документа, чтобы не копировать всю архитектуру внутрь промптов.

