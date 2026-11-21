# Go Product Platform v17 — справочник команд для агента

Обычным пользователям достаточно попросить агента на естественном языке; **агент** выполняет эти команды, подтвердив намерение. Интерактивные пользователи могут запустить `gpp wizard --project .` в терминале.

| Действие агента | Только чтение / изменение | Команда |
|---|---|---|
| Отчёт о глобальных установках и активации | только чтение; сканирует выбранные глобальные расположения только с согласия | `gpp skills-inventory --project . --json` |
| Восстановить локальные игнорируемые материалы в worktree Orca | только локально, без глобальных и сетевых изменений | `gpp init --project . --offline` |
| Выбрать профиль проекта | отслеживаемое изменение проекта; запросить подтверждение | `gpp skills-activate --project . --profile desktop --approve` |
| Выбрать конкретные глобальные навыки по именам | отслеживаемое изменение проекта; запросить подтверждение | `gpp skills-activate --project . --names golang-testing,protobuf --approve` |
| Установить выбранные отсутствующие курируемые глобальные навыки | изменяет ~/.agents и ~/.claude; явное согласие | `gpp skills-install-global --names golang-testing,protobuf --approve` |
| Проверить глобальные Git-ревизии | только чтение, кроме записи плана; сетевое обращение к upstream | `gpp skills-check-updates --project . --selected-only --json --output .go-product-platform/update-plan.json` |
| Обновить зафиксированный снапшот Git-ревизий | изменяет **оба** глобальных хранилища навыков; явное согласие | `gpp skills-upgrade-global --plan .go-product-platform/update-plan.json --approve` |
| Проверить проект | проверяет активированные навыки и документацию worktree | `gpp doctor --project . --strict` |

- Глобальное обновление затрагивает несколько проектов. Изучите план и diff по SHA; требуется отдельное одобрение, помимо самой проверки.
- Upstream Git-ревизия может измениться после создания плана. Инструмент обновления отклоняет неодобренные SHA.
- Orca обновляется своим официальным механизмом обновления, Graphify — командой `uv tool upgrade graphifyy`; каждый способ — только с согласия.
- Проектный управляющий навык находится в `.go-product-platform/project-skills/go-project-platform-manager/SKILL.md`; по выбору навыков этого проекта всегда сверяйтесь с ним.

## Процесс продукта (SDD v17)

Исполняемых команд SDD больше нет: этапы и артефакты описывает
`docs/engineering/workflow.md` продукта, а главы 19–20 руководства — порядок и
формат. Агент:

| Операция | Как выполняется |
|---|---|
| Новая фича | Создать `docs/specifications/<SPEC-ID>/requirements.md` по контракту артефактов |
| Перед реализацией | Заполнить design.md, plan.md и tasks.md; зависимые фичи — ready/released |
| Проверки | Реальные команды продукта (unit/e2e/contract); команда и результат — в verification.md |
| Новый цикл | Изменение согласованных входов — пересогласование и свежие проверки; после выпуска — delta-spec с новым ID |
| Перед слиянием | Независимая сессия ревью; код и документы зафиксированы в Git |

High-риск и выпуск требуют фактического решения человека и записи ссылки на решение
в PR/журнале фичи. Никакие команды платформы не выполняют deploy.


## Опциональный UI canvas

```sh
gpp canvas-install --project . --source /path/to/reviewed/app-canvas --approve
# Существующий UI: добавить --app web; новый: --kit shadcn --color '#C2410C'.
python3 .canvas/board.py doctor
```

Источник — https://gitlab16.skiftrade.kz/design/app-canvas; перед запуском читать
`platform/references/canvas-installation.md` в стартовом наборе (после init —
`.go-product-platform/references/canvas-installation.md`). Offline-init canvas не ставит.
