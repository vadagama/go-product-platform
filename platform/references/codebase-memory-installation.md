---
id: "REF-codebase-memory-installation"
description: "Подключение MCP, индексация рабочего дерева и проверка поиска по коду и документации."
kind: "reference"
status: "current"
owner: "maintainer"
related: ["platform-installation.md", "../templates/manual.md"]
---

# codebase-memory-mcp

Для каждого выбранного клиента ADE зарегистрируйте stdio-сервер с именем и командой `codebase-memory-mcp`, без аргументов. В Codex используйте таблицу `[mcp_servers.codebase-memory-mcp]` в проектной `.codex/config.toml`, в Claude Code — объект `mcpServers` в `.mcp.json`. Сохраните остальные записи клиента. Перезапустите сессию и проверьте вызов `list_projects`.

Установите бинарный файл для ОС и архитектуры из [официального релиза](https://github.com/DeusData/codebase-memory-mcp/releases), сверив архив с опубликованным `checksums.txt`. Поместите исполняемый файл в PATH клиента. Для обновления повторите установку выбранной версии и перезапустите использующие её процессы. Зафиксируйте результат `codebase-memory-mcp --version` в MANUAL.md.

## Индексация и проверка

В корневом `.cbmignore` перечислите зависимости, кеши, секреты и дубли исходников. Включите контракты продукта, ADR, спецификации и рабочий код. Индекс хранится в локальном кеше. В новом worktree укажите его собственный абсолютный путь.

```sh
codebase-memory-mcp cli index_repository --repo-path "$PWD"
codebase-memory-mcp cli list_projects
```

Подставьте имя проекта, соответствующее этому пути, и реальное имя символа или заголовка документа.

```sh
codebase-memory-mcp cli index_status --project "$project"
codebase-memory-mcp cli search_graph --project "$project" --name-pattern "$pattern"
```

Проверьте, что запрос возвращает ожидаемый путь и раздел документа, а при наличии кода — также символ. После изменения повторите индексацию и тот же запрос. В активной MCP-сессии состояние автоматического наблюдения показывает `index_status`. Разовый запуск CLI требует явного обновления. Для проверки связей используйте `query_graph` и чтение исходников. Возможные связи документа с кодом требуют подтверждения по тексту.

## Переход с Graphify

Перенесите исключения в `.cbmignore`, проверьте покрытие и запросы. В действующих Git-хуках удаляйте только отмеченные блоки Graphify, сохраняя Canvas и пользовательские обработчики. Проверьте также старый вызов `graphify hook-check` в настройках ADE. Прежние локальные результаты можно сохранить вне области нового индекса.
