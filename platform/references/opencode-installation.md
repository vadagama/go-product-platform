---
id: "REF-opencode-installation"
description: "Подключение OpenCode к продукту: общие навыки, AGENTS.md, модели по ролям, адаптеры и проверка версии."
kind: "reference"
status: "current"
owner: "maintainer"
related: ["model-harness-configuration.md", "skills-installation.md"]
---

# OpenCode

OpenCode — поддерживаемый харнес платформы рядом с Codex и Claude Code.
Инструкции ниже сверены с официальной документацией 2026-11-24; перед установкой
проверить версию CLI и схему этой версии. V1/V2 различаются: не смешивать их
поля конфигурации и пути agents.

## Общие материалы и адаптер

- Общие правила продукта — корневой AGENTS.md. Не создавать OPENCODE.md с копией
  правил. Обнаружение описано в [Instructions](https://opencode.ai/docs/instructions/).
- Общий набор — `.agents/skills/`, референсы — `.agents/references/`.
  OpenCode обнаруживает Agent Skills; не требуется третья копия платформы.
  Проверить конфликты одноимённых навыков с `.claude/skills/`, `.opencode/skills/`
  и явно настроенными источниками. Правила приоритета —
  [Skills](https://opencode.ai/docs/skills/). Более приоритетная старая копия
  не должна незаметно подменять проектную ревизию.
- В `.opencode/` хранить только нативные адаптеры/команды. Персоны в
  `.agents/agents/` — материалы, а не автоматически работающие OpenCode agents.
- При подключении Impeccable проверить сборку `.opencode` выбранной ревизии;
  добавить требуемый upstream адаптер команды в `.opencode/commands/`, если он
  нужен этой версии. Не дублировать одноимённый skill без необходимости.

## Настройка

1. Проверить `opencode --version` и доступные команды через help. Если CLI нет,
   включить установку по [официальной инструкции](https://opencode.ai/docs/) в план.
2. Подключить выбранного провайдера штатным способом. По текущей документации
   это `/connect`, каталог — `/models`; агент готовит конфигурацию, пользователь
   проходит интерактивную авторизацию, если она необходима. Секреты не просить
   в чате и не писать в Git. DeepSeek/GLM/Claude выбираются по реально доступным
   provider/model ID, а не по предположению о названии.
3. Создать или дополнить один проектный `opencode.json`/`opencode.jsonc`.
   Начальная форма — [шаблон](../templates/opencode.json); он задаёт только схему,
   не готовую модель. Значения модели и назначения брать из `ai.assignments`.
4. Для ролей OpenCode создать нативные agents установленной версии. Для V2
   документация описывает `.opencode/agents/<role>.md` либо `agents` в JSONC.
   Использовать [шаблон роли V2](../templates/opencode-agent.md), заменив placeholders.
   Указать description, mode и model `provider/model`; поддерживаемый variant
   задаётся по схеме. Роль чтения/ревью ограничить соответствующими permissions.
   Не создавать одновременно две конфигурации одного агента. Формат сверять с
   [Agents](https://opencode.ai/docs/agents/) и [Config](https://opencode.ai/docs/config/).
5. В body каждого агента указать роль, чтение AGENTS.md, engineering.yaml,
   соответствующих skills и SPEC/docs/ui. Общие правила не копировать целиком.
   Согласованные нативные определения и конфиг коммитятся вместе с профилем;
   credentials, caches и session state — нет.

Сопоставление ролей: documentation → documentation, code → code-development,
ui → ui-development, code_review → code-review, design_review → design-review,
requirements → requirements, architecture → architecture. Это рекомендуемые ID
адаптеров, а не встроенные имена OpenCode. Создавать только назначенные OpenCode
роли; роли другого харнеса передаются по общему handoff-контракту.

В конфиге можно задать default model, но это не заменяет назначения каждой роли.
Выбор в существующей сессии может иметь приоритет: после перенастройки проверить
фактическую модель нового запуска. Точный provider/model и способ запуска
подтверждаются по [Models](https://opencode.ai/docs/models/); аутентификация — по
[Providers](https://opencode.ai/docs/providers/).

## Проверка и обновление

Проверить конфигурацию по схеме установленной версии, обнаружение AGENTS и skills,
запуск каждого уникального назначения, модель и доступные инструменты. Дизайн-ревью
должно получать снимки/рендер, а не только исходники. Проверка без credentials
подтверждает лишь статическую конфигурацию. Записать версии и результаты в MANUAL.

Обновления и смена моделей — через
[перенастройку продукта](model-harness-configuration.md#перенастройка-существующего-продукта).
Глобальная `~/.config/opencode/` не меняется при проектной настройке. Сохранить
пользовательские providers, agents, permissions и MCP; повторный запуск не должен
дублировать записи. Смена UI-режима не удаляет OpenCode и его настройки.
