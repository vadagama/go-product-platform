---
id: "REF-platform-materials"
description: "Карта материалов платформы: навыки, шаблоны, handbook, справочники установки, constitution и правила приоритета проектного набора. Читать, чтобы найти нужный документ платформы."
kind: "reference"
status: "current"
owner: "maintainer"
related: ["../README.md"]
---

# Go Product Platform — материалы платформы

Материалы платформы — md- и yaml-документы, связанные гиперссылками; в наборах
проектов допускаются и исполняемые скрипты. Настройку и сопровождение выполняет
агент по документам, подтверждая план у пользователя: вручную настраивать проект
в консоли не требуется. Состав набора продукта фиксирует `engineering.yaml`
в корне продукта.

| Путь | Описание |
|---|---|
| `skills/go-platform-bootstrap/` | Навык начальной настройки: SKILL.md (профили, установка, инициализация, критерии готовности) + references (опросник, источники навыков, операции агента, примеры AGENTS.md/CLAUDE.md) |
| `skills/go-project-platform-manager/` | Проектный управляющий навык: порядок установки, выбора и обновления набора через агента |
| `templates/` | Шаблоны init-документов и таблица соответствия артефактов навыкам; состав и границы — [templates/README.md](templates/README.md) |
| `handbook/` | Руководство — канонический Markdown-источник |
| `references/` | Инструкции установки: [platform-installation.md](references/platform-installation.md), [skills-installation.md](references/skills-installation.md), [canvas-installation.md](references/canvas-installation.md), [graphify-installation.md](references/graphify-installation.md) |
| `constitution.md` | Инженерные инварианты проекта |

Глобальные каталоги `~/.agents/skills/` и `~/.claude/skills/` служат источниками.
Согласованный набор копируется в `.agents/` и `.claude/` продукта, включая агентов
и референсы. Проектные версии имеют приоритет; их источники и ревизии фиксируются
в engineering.yaml продукта.

**Попросите агента:** «Покажи активные навыки этого проекта и предложи обновления, но ничего не устанавливай без моего подтверждения». Агент должен прочитать `AGENTS.md`, затем `.agents/skills/go-project-platform-manager/SKILL.md`.

Ни настройка продукта, ни работа в worktree сами по себе не разрешают установку,
обновление или сканирование глобальных навыков. Пользователь одобряет глобальные
изменения отдельно.
