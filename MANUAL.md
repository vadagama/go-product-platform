# Обслуживание репозитория платформы

Установите CLI и подключите проектные настройки Codex или Claude Code по [инструкции](platform/references/codebase-memory-installation.md). Для проверки из корня репозитория выполните:

```sh
codebase-memory-mcp cli index_repository --repo-path "$PWD"
codebase-memory-mcp cli list_projects
```

Возьмите имя текущего дерева из ответа и задайте переменную `project`. Проверьте индекс и найдите документ по заголовку:

```sh
codebase-memory-mcp cli index_status --project "$project"
codebase-memory-mcp cli search_graph --project "$project" --name-pattern 'Индексация и проверка'
```

После изменения исходников или документов повторите индексацию и проверьте результат по изменённому разделу. Область анализа ограничена корневым `.cbmignore`. В новом clone или worktree повторите команды из его корня.

## Проверки изменений платформы

Проверьте `git diff --check`, YAML и frontmatter, относительные ссылки затронутых документов и их переносимость в проектные каталоги навыков.
