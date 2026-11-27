---
id: "REF-gokg-installation"
description: "Установка GoKG и анализ зависимостей Go при разработке и модернизации."
kind: "reference"
status: "current"
owner: "maintainer"
related: ["platform-installation.md", "graphify-installation.md"]
---

# GoKG в Go-продукте

Подключать при появлении загружаемого Go-модуля. В репозитории с несколькими независимыми модулями выполнять команды из каталога нужного модуля. Graphify связывает требования, ADR и исходники. GoKG уточняет связи между Go-типами, реализациями интерфейсов и местами вызова.

Проверить существующий CLI командой `gokg version`. Для начальной установки из исходников используется Go 1.25.11 или новее. Записать фактическую версию в MANUAL.md продукта. [Документация выбранной версии](https://github.com/hungpdn/gokg/tree/v0.1.0-rc.1)

```sh
go install github.com/hungpdn/gokg/cmd/gokg@v0.1.0-rc.1
gokg version
```

Добавить `.gokg/` в .gitignore продукта и исключения .graphifyignore. Из корня модуля проверить загрузку пакетов и построить индекс с тестами.

```sh
go list ./...
gokg analyze --tests
gokg stats
gokg query 'MATCH (s:STRUCT)-[:IMPLEMENTS]->(i:INTERFACE) RETURN s.Name, i.Name LIMIT 20'
```

До рефакторинга найти реализации изменяемого интерфейса и проверить их в исходниках. После правок обновить индекс командой `gokg analyze --tests` и выполнить `gokg impact --depth 2`. Проверить статус свежести, сопоставить затронутые пакеты с контрактами и ADR через Graphify и запустить соответствующие тесты. Пустую выборку сверить с кодом. Для нового worktree повторить построение. Для интерактивных запросов через MCP использовать `gokg mcp` по stdio из того же каталога.
