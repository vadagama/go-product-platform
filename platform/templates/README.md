---
id: "REF-templates"
kind: "reference"
status: "current"
owner: "maintainer"
related: ["../README.md", "../handbook/docs/20-artifact-contract.md"]
---

# Шаблоны документов продукта

Здесь только заготовки, которые init создаёт в продукте, и пример CI. Формат
остальных артефактов — SPEC, plan, tasks, ADR, LLD, api/data/events, debt,
initiative, capability map, product-readme — задают шаблоны
software-development-workflow: они приходят в продукт референсами
`.agents/references/software-development-workflow/templates/` и здесь не
дублируются. Соответствие источников — таблица в
[engineering-workflow.md](engineering-workflow.md).

| Шаблон | Куда в продукте | Когда создаётся |
|---|---|---|
| [engineering-workflow.md](engineering-workflow.md) | `docs/workflow.md` | init, шаг 1 |
| [hld-overview.md](hld-overview.md) | `docs/hld/README.md` | init, шаг 1 |
| [manual.md](manual.md) | `MANUAL.md` | init, шаг 4 |
| [agent-skills-registry.md](agent-skills-registry.md) | `docs/agent-skills.md` | init, шаг 5 |
| [ci/sdd-gitlab-ci.yml](ci/sdd-gitlab-ci.yml) | пайплайн продукта | при настройке CI, вливается явно |

## Почему HLD — свой шаблон, а не шаблон SDW

- Init создаёт HLD до копирования проектных референсов (шаг 7 чек-листа
  инициализации). Минимальный шаблон доступен в переносимом снимке платформы;
  расширенные шаблоны SDW устанавливаются во все профили, включая `custom`.
- Шаблоны SDW используют свой контракт метаданных (`schema_version`, `type`,
  `created/updated`); контракт продуктов — глава 20 руководства (`kind`,
  `status`, `owner`, `related`). Шаблон `hld-overview.md` уже конформен.
- Разделы шаблона совпадают со строкой HLD в таблице главы 20: контекст,
  компоненты, развёртывание, нефункциональные требования. Расширенный каркас —
  шаблон SDW `hld.md` — применяется при необходимости с адаптацией frontmatter
  под контракт главы 20.
