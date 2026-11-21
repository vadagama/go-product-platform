#!/usr/bin/env python3
"""Go Product Platform: global shared skills, interactive setup and agent-managed project selection.

Python 3.10+ standard library. Third-party skill instructions/scripts are never executed.
Plain `init --offline` never installs shared skills. Approved `init --setup-plan`
also prepares the selected stack and missing global skills.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import project_assets

from readiness import CONTRACT, check_ready, execute, setup_plan, validate_plan

VERSION = '17.0.0'
HERE = Path(__file__).resolve().parent.parent
USER_HOME = Path(os.environ.get('GPP_USER_HOME', str(Path.home()))).expanduser().resolve()
AGENT_ROOT = USER_HOME / '.agents'
CLAUDE_ROOT = USER_HOME / '.claude'
GLOBAL_PLATFORM = AGENT_ROOT / 'go-product-platform'
GLOBAL_LOCK = GLOBAL_PLATFORM / 'global-skills.lock.json'
CACHE_ROOT = Path(os.environ.get('GPP_CACHE_HOME', str(USER_HOME / '.cache/go-product-platform'))).expanduser()
HOME_ROOT = Path(os.environ.get('GPP_HOME', str(USER_HOME / '.local/share/go-product-platform'))).expanduser()
ADDY_KEY = 'addyosmani'
ORCA_URL = 'https://github.com/stablyai/orca'
ORCA_SKILLS = ('orca-cli', 'orchestration', 'computer-use', 'orca-linear', 'orca-emulator', 'orca-emulator-android', 'orca-per-workspace-env')
OLD_SKILLS = ('go-platform-bootstrap', 'graphify', 'spec-driven-development', 'test-driven-development', 'incremental-implementation', 'code-review-and-quality', 'code-simplification', 'source-driven-development', 'security-and-hardening')


def say(msg: str) -> None:
    print(f'[gpp] {msg}')


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, capture: bool = False):
    try:
        return subprocess.run(cmd, cwd=cwd, env=env, check=True, text=True,
                              stdout=subprocess.PIPE if capture else None,
                              stderr=subprocess.PIPE if capture else None)
    except (subprocess.CalledProcessError, OSError) as error:
        raise RuntimeError(f'Command failed {cmd}: {error}') from error


def json_load(path: Path, fallback: dict | None = None) -> dict:
    return json.loads(path.read_text('utf-8')) if path.is_file() else (fallback or {})


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                     prefix='.gpp-', suffix='.json', delete=False) as out:
        temporary = Path(out.name)
        out.write(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')
    try:
        if path == GLOBAL_LOCK:
            temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def add_lines(path: Path, lines: list[str]) -> None:
    old = path.read_text('utf-8') if path.exists() else ''
    missing = [line for line in lines if line not in old.splitlines()]
    if missing:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as out:
            if old and not old.endswith('\n'):
                out.write('\n')
            out.write(''.join(line + '\n' for line in missing))


def ensure_block(path: Path, content: str) -> None:
    begin, end = '<!-- GPP:BEGIN -->', '<!-- GPP:END -->'
    old = path.read_text('utf-8') if path.exists() else ''
    newblock = f'{begin}\n{content.strip()}\n{end}'
    if begin in old and end in old:
        before, after_begin = old.split(begin, 1)
        _, after = after_begin.split(end, 1)
        new = before + newblock + after
    elif begin in old or end in old:
        raise RuntimeError(f'Invalid bridge markers: {path}')
    else:
        new = old.rstrip() + ('\n\n' if old.strip() else '') + newblock + '\n'
    if new != old:
        path.write_text(new, encoding='utf-8')


def assert_git(project: Path) -> None:
    if not project.is_dir():
        raise RuntimeError(f'Project directory not found: {project}')
    root = run(['git', '-C', str(project), 'rev-parse', '--show-toplevel'], capture=True).stdout.strip()
    if Path(root).resolve() != project:
        raise RuntimeError(f'Operate at Git project root {root}, not {project}')


def manifest_path(args) -> Path:
    return Path(args.manifest).expanduser().resolve() if getattr(args, 'manifest', None) else HERE / 'platform/manifests/global-skills.json'


def load_manifest(path: Path) -> dict:
    data = json_load(path)
    if not isinstance(data.get('sources'), list):
        raise RuntimeError(f'Invalid global skills manifest: {path}')
    seen = set()
    for source in data['sources'] + ([data['workflow']] if data.get('workflow') else []):
        key = source['key']
        if '/' in key or key.startswith('.') or key in seen:
            raise RuntimeError(f'Unsafe or duplicate source key: {key}')
        seen.add(key)
        for subpath in [source.get('references'), source.get('agents'), *source.get('resources', [])]:
            if subpath and (Path(subpath).is_absolute() or '..' in Path(subpath).parts):
                raise RuntimeError(f'Unsafe resource path: {subpath}')
        for name, subpath in source['skills'].items():
            parts = Path(subpath).parts
            if not name or '/' in name or name.startswith('.') or '..' in parts or Path(subpath).is_absolute():
                raise RuntimeError(f'Unsafe skill path {name}: {subpath}')
    return data


def make_link(dst: Path, source: Path) -> bool:
    if not (source / 'SKILL.md').is_file():
        say(f'MISSING source {source / "SKILL.md"}')
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    # Avoid taking ownership of pre-existing user-installed content.
    if dst.is_symlink():
        if dst.resolve() == source.resolve():
            return True
        say(f'CONFLICT: not replacing existing skill link: {dst}')
        return False
    if dst.exists():
        say(f'CONFLICT: not replacing existing skill directory: {dst}')
        return False
    dst.symlink_to(os.path.relpath(source, dst.parent), target_is_directory=True)
    return True


def both_global(name: str, source: Path) -> bool:
    return all(make_link(folder / 'skills' / name, source) for folder in (AGENT_ROOT, CLAUDE_ROOT))


def link_refs(source: Path) -> None:
    refs = source / 'references'
    if not refs.is_dir():
        return
    for root in (AGENT_ROOT, CLAUDE_ROOT):
        dst = root / 'references'
        if not dst.exists() and not dst.is_symlink():
            dst.symlink_to(os.path.relpath(refs, root), target_is_directory=True)
        elif dst.is_symlink() and dst.resolve() == refs.resolve():
            continue
        else:
            say(f'NOTE: {dst} already exists. Verify Addy skills ../../references links manually.')


def cache_source(source: dict, *, offline: bool = False, refresh: bool = False) -> tuple[Path, str]:
    key = source['key']
    previous = json_load(GLOBAL_LOCK).get('repositories', {}).get(key, {})
    pinned = source.get('revision') or previous.get('commit')
    if pinned and not refresh:
        snapshot = GLOBAL_PLATFORM / 'vendor' / key / pinned
        if snapshot.is_dir():
            return snapshot, pinned
    cache = CACHE_ROOT / 'source-checkouts' / key
    if cache.exists() and refresh and not offline:
        shutil.rmtree(cache)
    if not cache.exists():
        if offline:
            raise RuntimeError(f'Offline source missing: {key}. Run online `gpp setup-global --skills` once.')
        cache.parent.mkdir(parents=True, exist_ok=True)
        # Sparse shallow clone avoids downloading whole frontend/Android monorepos.
        run(['git', 'clone', '--depth', '1', '--filter=blob:none', '--sparse', source['repo'], str(cache)])
        if source.get('revision'):
            run(['git', '-C', str(cache), 'fetch', '--depth', '1', 'origin', source['revision']])
            run(['git', '-C', str(cache), 'checkout', '--detach', 'FETCH_HEAD'])
        selected = list(source['skills'].values()) + source.get('resources', [])
        if source.get('agents'):
            selected.append(source['agents'])
        if source.get('references'):
            selected.append(source['references'])
        # Git cone sparse checkout accepts directories; retain shared resources.
        run(['git', '-C', str(cache), 'sparse-checkout', 'set', *selected])
    sha = run(['git', '-C', str(cache), 'rev-parse', 'HEAD'], capture=True).stdout.strip()
    if pinned and sha != pinned and not refresh:
        raise RuntimeError(f'{key}: pinned SHA {pinned} not in local cache; do not silently upgrade.')
    snapshot = GLOBAL_PLATFORM / 'vendor' / key / sha
    if not snapshot.is_dir():
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(cache, snapshot, ignore=shutil.ignore_patterns('.git'))
    return snapshot, sha


def install_curated(args) -> None:
    manifest = load_manifest(manifest_path(args))
    if args.dry_run:
        for entry in manifest['sources']:
            say(f'WOULD INSTALL from {entry["repo"]}: {", ".join(entry["skills"])}')
        return
    lock = json_load(GLOBAL_LOCK, {'platform_version': VERSION, 'repositories': {}, 'skills': {}})
    lock.setdefault('repositories', {})
    lock.setdefault('skills', {})
    problems = []
    selected_names = {n.strip() for n in getattr(args, 'names', '').split(',') if n.strip()}
    for entry in manifest['sources']:
        if selected_names and not (set(entry['skills']) & selected_names):
            continue
        try:
            source, sha = cache_source(entry, offline=args.offline, refresh=args.refresh)
            for name, rel in entry['skills'].items():
                if selected_names and name not in selected_names:
                    continue
                full = (source / rel).resolve()
                if not full.is_relative_to(source.resolve()) or not (full / 'SKILL.md').is_file():
                    raise RuntimeError(f'{name}: expected SKILL.md missing at {source / rel}')
                if not both_global(name, full):
                    raise RuntimeError(f'{name}: global installation collision')
                lock['skills'][name] = {'source': entry['key'], 'commit': sha, 'path': rel}
            if entry.get('references'):
                link_refs(source)
            lock['repositories'][entry['key']] = {'repo': entry['repo'], 'commit': sha}
            save_json(GLOBAL_LOCK, lock)
        except (RuntimeError, OSError) as error:
            problems.append(str(error))
            say(f'ERROR: {error}')
            if not args.continue_on_error:
                raise
    if problems:
        raise RuntimeError(f'{len(problems)} global source(s) failed. See errors above.')
    say(f'Global skill installation complete: {len(lock["skills"])} curated entries.')


def global_bootstrap_skill(bundle: Path | None = None) -> bool:
    check_bootstrap_destinations()
    bundle = bundle or install_cli_bundle()
    source = bundle / 'platform/skills/go-platform-bootstrap'
    if not (source / 'SKILL.md').is_file():
        raise RuntimeError('Bootstrap skill missing from starter kit')
    digest = hashlib.sha256()
    for path in sorted(source.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            digest.update(str(path.relative_to(source)).encode())
            digest.update(path.read_bytes())
    installed = GLOBAL_PLATFORM / 'builtins' / VERSION / digest.hexdigest()[:16] / 'go-platform-bootstrap'
    if not installed.exists():
        installed.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, installed)
    # Keep the bundle outside skill discovery: it contains other SKILL.md files.
    (installed / 'runtime.path').write_text(str(bundle.resolve()) + '\n', encoding='utf-8')
    destinations = [root / 'skills/go-platform-bootstrap' for root in (AGENT_ROOT, CLAUDE_ROOT)]
    # Only replace old versioned, GPP-owned symlinks. Never take over user files.
    check_bootstrap_destinations()
    for dst in destinations:
        if dst.is_symlink() and dst.resolve() != installed.resolve():
            tmp = dst.parent / '.go-platform-bootstrap.gpp-new'
            if tmp.exists() or tmp.is_symlink():
                raise RuntimeError('Conflicting temporary bootstrap symlink: '+str(tmp))
            tmp.symlink_to(os.path.relpath(installed, dst.parent), target_is_directory=True)
            os.replace(tmp, dst)
        else:
            make_link(dst, installed)
    return all((dst / 'SKILL.md').is_file() for dst in destinations)


def check_bootstrap_destinations() -> None:
    for root in (AGENT_ROOT, CLAUDE_ROOT):
        dst = root / 'skills/go-platform-bootstrap'
        if dst.is_symlink():
            if not dst.resolve().is_relative_to((GLOBAL_PLATFORM / 'builtins').resolve()):
                raise RuntimeError(f'Global bootstrap skill is not GPP-managed: {dst}')
        elif dst.exists():
            raise RuntimeError(f'Refusing to overwrite pre-existing bootstrap skill directory: {dst}')


def install_graphify(args) -> None:
    if args.dry_run:
        say('WOULD RUN uv tool install graphifyy (only if CLI missing)')
        say('WOULD RUN graphify install --platform agents; graphify install --platform claude (GLOBAL, never --project)')
        return
    binary = shutil.which('graphify')
    if binary is None:
        if not shutil.which('uv'):
            raise RuntimeError('Graphify requires uv: brew install uv')
        run(['uv', 'tool', 'install', 'graphifyy'])
        binary = shutil.which('graphify')
        if not binary:
            raise RuntimeError('graphify not in PATH after uv tool install; add ~/.local/bin to PATH')
    env = os.environ.copy()
    env['HOME'] = str(USER_HOME)
    run([binary, 'install', '--platform', 'agents'], env=env)
    run([binary, 'install', '--platform', 'claude'], env=env)
    for root in (AGENT_ROOT, CLAUDE_ROOT):
        if not (root / 'skills/graphify/SKILL.md').is_file():
            raise RuntimeError(f'Graphify not installed into {root / "skills/graphify"}')
    say('Graphify global skills ready for Codex/Zed and Claude.')


def orca_install(args) -> None:
    if args.dry_run:
        for name in ORCA_SKILLS:
            print(f'npx skills add {ORCA_URL} --skill {name} --global')
        say('If Orca CLI is installed, prefer: orca skills install --skill ... --agent claude,codex')
        return
    if shutil.which('orca'):
        cmd = ['orca', 'skills', 'install']
        for name in ORCA_SKILLS:
            cmd += ['--skill', name]
        cmd += ['--agent', 'claude,codex']
        run(cmd)
    else:
        if not shutil.which('npx'):
            raise RuntimeError('Install Orca CLI or Node.js/npm with npx to install Orca skills.')
        for name in ORCA_SKILLS:
            run(['npx', 'skills', 'add', ORCA_URL, '--skill', name, '--global', '--yes'])
    missing = []
    for name in ORCA_SKILLS:
        a, c = AGENT_ROOT / 'skills' / name, CLAUDE_ROOT / 'skills' / name
        if (a / 'SKILL.md').is_file() and not (c / 'SKILL.md').is_file():
            # Orca owns lightweight single-file stubs; preserve normal Orca updates.
            shutil.copytree(a, c, symlinks=False)
        elif (c / 'SKILL.md').is_file() and not (a / 'SKILL.md').is_file():
            shutil.copytree(c, a, symlinks=False)
        if not (a / 'SKILL.md').is_file() or not (c / 'SKILL.md').is_file():
            missing.append(name)
    if missing:
        raise RuntimeError('Orca skills missing in global directories: ' + ', '.join(missing))
    say('Seven Orca skills installed in both user-global skill directories.')


def setup_global(args) -> None:
    if not (args.skills or args.orca or args.graphify):
        raise RuntimeError('Select at least one: --skills, --orca, --graphify')
    if args.dry_run:
        if args.skills:
            install_curated(args)
            say('WOULD INSTALL go-platform-bootstrap globally')
        if args.graphify:
            install_graphify(args)
        if args.orca:
            orca_install(args)
        return
    if args.skills:
        if not global_bootstrap_skill():
            raise RuntimeError('Cannot register global bootstrap skill; existing conflict')
        install_curated(args)
    if args.graphify:
        install_graphify(args)
    if args.orca:
        orca_install(args)


def copy_platform(project: Path) -> Path:
    target = project / '.go-product-platform'
    target.mkdir(exist_ok=True)
    # Offline scaffold excludes skills; approved setup installs them separately.
    shutil.copytree(HERE / 'platform', target, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('skills', 'vendor', '__pycache__'))
    (target / 'graphify/out').mkdir(parents=True, exist_ok=True)
    (target / 'project-skills').mkdir(exist_ok=True)
    project_manager = target / 'project-skills/go-project-platform-manager'
    if not project_manager.exists():
        shutil.copytree(HERE / 'platform/project-skill-templates/go-project-platform-manager', project_manager)
    (target / 'tools').mkdir(exist_ok=True)
    shutil.copy2(Path(__file__).resolve(), target / 'tools/gpp.py')
    shutil.copy2(Path(__file__).resolve().with_name('readiness.py'), target / 'tools/readiness.py')
    shutil.copy2(Path(__file__).resolve().with_name('project_assets.py'), target / 'tools/project_assets.py')
    alias = project / 'graphify-out'
    if not alias.exists() and not alias.is_symlink():
        alias.symlink_to('.go-product-platform/graphify/out', target_is_directory=True)
    return target


def write_bridge(project: Path) -> None:
    bridge = """## Правила агентной работы
- Ведите AGENTS.md и CLAUDE.md полностью на русском языке: заголовки, пояснения, правила и новые разделы. Сохраняйте без перевода только команды, пути, имена файлов, названия продуктов и технические идентификаторы. При настройке существующего продукта переведите и остальные разделы этих файлов, сохраняя смысл и силу всех пользовательских правил.
- Обязательно соблюдайте флоу разработки из **software-development-workflow**. Перед изменением прочитайте `.agents/references/software-development-workflow/docs/workflow.md`, карту `.agents/references/software-development-workflow/docs/upstream.md` и `docs/engineering/workflow.md` продукта.
- Используйте проектные навыки из `.agents/skills/` (Codex) и `.claude/skills/` (Claude), роли из `agents/` и материалы из `references/` этих каталогов. Эти версии имеют приоритет над одноимёнными глобальными навыками. Применяйте навыки по характеру задачи; не отменяйте обязательные проверки процесса.
- Порядок работы: контекст → уточнение требований → проектирование → планирование → реализация → проверка → независимое ревью → выпуск → развитие. Выполняйте применимые согласования и проверки software-development-workflow.
- Храните требования, HLD/LLD/ADR, контракты и доказательства проверок в Git продукта; обновляйте затронутую документацию вместе с кодом. Не выдумывайте результаты или согласования.
- Настройка и запуск описаны в `MANUAL.md`. Состав и происхождение проектного набора зафиксированы в `go-product-platform.lock.json`.
- Для управления набором читайте `.agents/skills/go-project-platform-manager/SKILL.md`. Перед установкой или обновлением покажите структурированный список навыков, источников, версий, агентов и референсов для согласования. Глобальное обновление не обновляет проектные копии.
- Если проектные материалы отсутствуют, завершите согласованную установку; не подменяйте их молча глобальными версиями. `gpp init --offline` восстанавливает только локальную документацию платформы.
"""
    for name in ('AGENTS.md', 'CLAUDE.md'):
        ensure_block(project / name, bridge)
    write_manual(project)


def write_manual(project: Path) -> None:
    plan = json_load(project / CONTRACT)
    lines = ["# Настройка проекта", "", "## Первоначальная подготовка",
             "Откройте этот репозиторий в Codex/Claude и вызовите go-platform-bootstrap. "
             "Выберите стек, согласуйте таблицу проектных навыков, агентов, референсов и команды установки.",
             "", "## Агентные материалы",
             "В Git хранятся .agents/ и .claude/: skills, agents, references. "
             "Приоритет имеют проектные версии. Обязательно соблюдайте флоу software-development-workflow "
             "из .agents/references/software-development-workflow/docs/workflow.md.",
             "", "## Восстановление и проверка", "```sh", "gpp init --project . --offline",
             "gpp doctor --project . --ready", "```",
             "Проверка ready выполняет команды из согласованного go-product-platform.setup.json.",
             "", "## Окружение и установка",
             "Секреты задавайте через окружение; не добавляйте их в Git или команды плана."]
    for command in plan.get('setup', []):
        lines.append('- Каталог `' + command.get('cwd', '.') + '`: `' + shlex.join(command['argv']) + '`')
    for component in plan.get('components', []):
        lines.append('### ' + component['name'])
        lines.append('Файлы: ' + ', '.join('`' + x + '`' for x in component['paths']))
        for command in component['checks']:
            lines.append('- Проверка из `' + command.get('cwd', '.') + '`: `' + shlex.join(command['argv']) + '`')
    lines += ['', '## Обновление навыков',
              'Сформируйте `gpp skills-project --project . --json`, согласуйте список, затем '
              'выполните `gpp skills-project --project . --approve`. Изменённые вручную материалы сохраняются: '
              'при конфликте установщик остановится. Закоммитьте оба каталога и lock-файл.',
              'Инструкции запуска приложений, настройки БД и имена переменных окружения дополняйте '
              'по фактическому стеку вне блока GPP; не указывайте непроверенные команды.']
    ensure_block(project / 'MANUAL.md', '\n'.join(lines))


def orca_config(project: Path) -> None:
    file = project / 'orca.yaml'
    expected = '''scripts:
  setup: |
    gpp init --project . --offline
  archive: |
    gpp clean --project . --worktree
setupAgentStartupPolicy: wait-for-setup
'''
    if not file.exists():
        file.write_text(expected, encoding='utf-8')
    elif 'gpp init' not in file.read_text('utf-8'):
        say(f'Preserving existing {file}; merge .go-product-platform/orca-integration.yaml manually')
        (project / '.go-product-platform/orca-integration.yaml').write_text(expected, encoding='utf-8')


def lock_project(project: Path) -> None:
    file = project / 'go-product-platform.lock.json'
    current = json_load(file)
    if current and current.get('platform_version') != VERSION:
        raise RuntimeError('Project pins different platform version. Run `gpp migrate --project .` to v17.')
    current.update({
        'platform_version': VERSION,
        'skills_scope': 'project-local',
        'skills_locations': ['.agents/skills', '.claude/skills'],
        'global_skills_manifest_version': VERSION,
    })
    current.pop('addyosmani_commit', None)
    current.pop('addyosmani_repo', None)
    current.pop('graphify_project_skill', None)
    current.pop('orca_skills_scope', None)
    current.setdefault('skills_profile', None)
    current.setdefault('enabled_global_skills', [])
    save_json(file, current)


def seed_docs(project: Path) -> None:
    """Idempotent: create absent baseline product docs, never replace user content."""
    workflow = project / 'docs/engineering/workflow.md'
    if not workflow.exists():
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text('''---
id: "POLICY-sdd"
kind: "policy"
status: "draft"
owner: "maintainer"
related: []
standard: 1
task_source: "markdown"
---

# Правила разработки с агентами

Обязательная основа продукта — структура документации и workflow Go Product Platform
(главы 19–20 руководства). Адаптации фиксируются в этом документе с обоснованием.
Документы продукта хранятся в Git под docs/, материалы платформы — в .go-product-platform/.

Порядок: specify → design → plan → implement → verify → review → ready → released.
Каждая фича находится в `docs/specifications/<SPEC-ID>/`: requirements, design, plan, tasks,
verification, review. Артефакты — обычный Markdown с YAML frontmatter (контракт — глава 20
руководства); исполняемых ворот нет, дисциплину обеспечивают эти правила, ревью и Git-история.

Прежде чем писать код, зафиксируйте требования с уникальными AC-ID, границы и влияние на
документацию; затем дизайн (решение, альтернативы, риски) и план с вертикальными срезами-задачами
(T-ID, зависимости, проверка каждого среза). Не разбивайте фичу на очереди «вся БД», «весь
backend», «весь frontend».

Доказательства: запускайте реальные проверки (unit/e2e/contract) и фиксируйте команду, результат
и покрытие AC в verification.md. Старый зелёный отчёт не считается доказательством нового
кандидата: после смены кода, документов или ребейза проверки прогоняются заново. Изменение
утверждённых требований/дизайна/плана означает новый цикл с пересогласованием; для выпущенных
фич создавайте delta-spec с новым ID и related на исходную SPEC.

Автономия: low/medium-риск в согласованном объёме агент проходит сам. Высокий риск (разрушительные
миграции, границы доверия, архитектура) и любой выпуск требуют фактического решения человека;
агент не выдумывает одобрения и не понижает риск. Ревью выполняет другая сессия/человек с отдельным
контекстом; ревьюер не исправляет код сам.

Один владелец фичи и один пишущий агент на worktree; параллелизм — между независимыми фичами.
tasks.md — единственный список задач; не создавайте второй источник истины. Принятые ADR не
переписываются: новое решение — новый ADR с supersedes. Не выдавайте draft HLD за реализованную
архитектуру. API — .proto, данные — миграции; Markdown описывает семантику, а не копирует схемы.
''', encoding='utf-8')
    overview = project / 'docs/architecture/hld/overview.md'
    if not overview.exists():
        overview.parent.mkdir(parents=True, exist_ok=True)
        overview.write_text('''---
id: "HLD-product"
kind: "hld"
status: "draft"
owner: "maintainer"
related: []
---

# Архитектура продукта — черновик

## Контекст

TODO: заполнить по контексту продукта.

## Компоненты

TODO: заполнить по контексту продукта.

## Развёртывание

TODO: заполнить по контексту продукта.

## Нефункциональные требования

TODO: заполнить по контексту продукта.
''', encoding='utf-8')


def init(args) -> None:
    if getattr(args, 'offline', False) and (getattr(args, 'setup', False) or getattr(args, 'setup_plan', None)):
        raise RuntimeError('--offline cannot be combined with setup options; use plain init --offline')
    if getattr(args, 'setup', False):
        if getattr(args, 'setup_plan', None):
            raise RuntimeError('Choose --setup or --setup-plan, not both')
        if not args.profile:
            raise RuntimeError('--setup requires --profile')
        plan = setup_plan(args.profile)
        plan['skills'] = [n.strip() for n in getattr(args, 'names', '').split(',') if n.strip()]
        plan['agent_assets'] = project_asset_plan([*PROFILE_DEFAULTS[args.profile], *plan['skills']], load_manifest(manifest_path(args)))
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    if getattr(args, 'setup_plan', None):
        apply_setup(args)
        return
    if getattr(args, 'profile', None) or getattr(args, 'json', False) or getattr(args, 'names', ''):
        raise RuntimeError('--profile/--json require --setup')
    project = Path(args.project).expanduser().resolve()
    assert_git(project)
    lock = json_load(project / 'go-product-platform.lock.json')
    if lock and lock.get('platform_version') != VERSION:
        raise RuntimeError('Existing project uses v' + str(lock.get('platform_version')) + '. Run `gpp migrate --project .` explicitly.')
    target = copy_platform(project)
    add_lines(project / '.gitignore', ['# Go Product Platform: per-worktree generated materials', '/.go-product-platform/', '/graphify-out', '/graphify-out/'])
    seed_docs(project)
    write_bridge(project)
    orca_config(project)
    lock_project(project)
    write_active_skills(project)
    save_json(target / 'install-manifest.json', {
        'platform_version': VERSION,
        'installed_at': datetime.now(timezone.utc).isoformat(),
        'skills_scope': 'project-local',
        'project_specific_skills': 'not installed by default',
        'global_dirs': [str(AGENT_ROOT / 'skills'), str(CLAUDE_ROOT / 'skills')],
    })
    say(f'Project initialized: {project} (v{VERSION}); local project manager ready; agent instructions and MANUAL ready; run approved setup to install project assets.')
    if not (AGENT_ROOT / 'skills/go-platform-bootstrap/SKILL.md').is_file():
        say('Global skills not yet installed; run once: gpp setup-global --skills --graphify --orca')


def owned_old_symlink(link: Path, project: Path) -> bool:
    if not link.is_symlink():
        return False
    # Inspect original target, not whether it still exists.
    return (link.parent / os.readlink(link)).resolve().is_relative_to((project / '.go-product-platform').resolve())


def migrate(args) -> None:
    project = Path(args.project).expanduser().resolve()
    assert_git(project)
    lock = json_load(project / 'go-product-platform.lock.json')
    if lock.get('platform_version') in ('14.0.0', '15.0.0', '16.0.0'):
        save_json(project / 'go-product-platform.lock.json', {
            **lock, 'platform_version': VERSION,
            'global_skills_manifest_version': VERSION,
            'migration_from': lock['platform_version'],
        })
        init(argparse.Namespace(project=str(project)))
        stale = project / '.go-product-platform/tools/sdd.py'
        if stale.is_file():
            stale.unlink()
        say('Migrated to v17; existing skills and product documentation preserved.')
        return
    if lock.get('platform_version') != '13.0.0':
        raise RuntimeError('Migration supports v13/v14/v15/v16 -> v17; project has ' + str(lock.get('platform_version')))
    if not (AGENT_ROOT / 'skills/go-platform-bootstrap/SKILL.md').is_file() and not args.allow_missing_global:
        raise RuntimeError('Install global skills first: gpp setup-global --skills --graphify --orca; then migrate.')
    local = project / '.go-product-platform'
    # Unlink ONLY v13-managed generated project entries, never project-created skills.
    for name in OLD_SKILLS:
        for folder in ('.agents/skills', '.claude/skills'):
            link = project / folder / name
            if owned_old_symlink(link, project):
                link.unlink()
    for root in ('.agents/references', '.claude/references'):
        link = project / root
        if owned_old_symlink(link, project):
            link.unlink()
    # Any v13 generated directories are ignored; preserve unexpected user data.
    for rel in ['vendor/addyosmani-agent-skills', 'skills/go-platform-bootstrap', 'skills/graphify', *('skills/' + n for n in OLD_SKILLS)]:
        path = local / rel
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
    for d in ['.agents/skills', '.claude/skills']:
        folder = project / d
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    ignore = project / '.gitignore'
    if ignore.exists():
        old = ignore.read_text('utf-8').splitlines()
        generated = {f'/{prefix}/skills/{name}' for prefix in ('.agents','.claude') for name in OLD_SKILLS}
        generated |= {'/.agents/references', '/.claude/references'}
        ignore.write_text('\n'.join(line for line in old if line not in generated) + '\n', encoding='utf-8')
    save_json(project / 'go-product-platform.lock.json', {
        'platform_version': VERSION, 'skills_scope': 'project-local',
        'skills_locations': ['~/.agents/skills','~/.claude/skills'],
        'global_skills_manifest_version': VERSION,
        'migration_from': '13.0.0',
    })
    init(argparse.Namespace(project=str(project)))
    say('Migrated v13 -> v17; project-global skill links removed, project-specific material preserved.')


def graph_build(args) -> None:
    project = Path(args.project).expanduser().resolve()
    assert_git(project)
    binary = shutil.which('graphify')
    if not binary:
        raise RuntimeError('Graphify missing; use gpp setup-global --graphify')
    (project / '.go-product-platform/graphify/out').mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['GRAPHIFY_OUT'] = '.go-product-platform/graphify/out'
    run([binary, '.', '--no-viz'], cwd=project, env=env)


def install_cli_bundle() -> Path:
    target = HOME_ROOT / VERSION
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.resolve() != HERE.resolve():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(HERE, target, ignore=shutil.ignore_patterns('dist', 'tests', '__pycache__', '.git'))
    b = Path(os.environ.get('GPP_BIN_DIR', str(USER_HOME / '.local/bin'))).expanduser()
    b.mkdir(parents=True, exist_ok=True)
    script = b / 'gpp'
    script.write_text(f'#!/bin/sh\nexec python3 {shlex.quote(str(target / "installer/gpp.py"))} "$@"\n', encoding='utf-8')
    script.chmod(0o755)
    say(f'gpp CLI ready at {script}')
    return target


def install_cli(_args) -> None:
    check_bootstrap_destinations()
    target = install_cli_bundle()
    if not global_bootstrap_skill(target):
        raise RuntimeError('Cannot register global bootstrap skill')
    say('go-platform-bootstrap registered in ~/.agents/skills and ~/.claude/skills')


def apply_setup(args) -> None:
    if not args.approve:
        raise RuntimeError('Setup plan execution requires --approve after user authorization')
    project = Path(args.project).expanduser().resolve()
    assert_git(project)
    plan = json_load(Path(args.setup_plan).expanduser().resolve())
    validate_plan(project, plan)
    names = sorted(set(PROFILE_DEFAULTS[plan['profile']]) | set(plan.get('skills', [])))
    manifest = load_manifest(manifest_path(args))
    curated = catalog_all(manifest)
    unknown = set(names) - set(curated) - set(ORCA_SKILLS) - {'graphify', 'go-platform-bootstrap'}
    if unknown:
        raise RuntimeError('Unknown setup skills: ' + ', '.join(sorted(unknown)))
    if plan.get('agent_assets') != project_asset_plan(names, manifest):
        raise RuntimeError('Review and include the current structured agent_assets list before setup')
    # Check version before executing any project commands or touching global state.
    current = json_load(project / 'go-product-platform.lock.json')
    if current and current.get('platform_version') != VERSION:
        raise RuntimeError('Migrate the product explicitly before setup')
    init(argparse.Namespace(project=str(project)))
    for command in plan.get('setup', []):
        execute(project, command)
    activate_skills(project, plan['profile'], names, manifest)
    missing = [name for name in names if not all(global_installed(name).values())]
    selected = [name for name in missing if name in curated or name == 'go-platform-bootstrap']
    if selected:
        global_install_selected(argparse.Namespace(names=','.join(selected), approve=True, manifest=args.manifest))
    external = sorted(set(missing) & (set(ORCA_SKILLS) | {'graphify'}))
    if external:
        install_external_selected(argparse.Namespace(names=','.join(external), approve=True))
    install_project_assets(project, manifest)
    save_json(project / CONTRACT, plan)
    write_manual(project)
    doctor(argparse.Namespace(project=str(project), manifest=args.manifest, strict=True, ready=True))


def doctor(args) -> None:
    project = Path(args.project).expanduser().resolve()
    assert_git(project)
    main = json_load(project / 'go-product-platform.lock.json')
    manifest = load_manifest(manifest_path(args))
    expected = set(main.get('enabled_global_skills', []))
    ready = getattr(args, 'ready', False)
    checks = {
        'project platform docs': (project / '.go-product-platform/docs/index.html').is_file(),
        'gitignore platform path': '/.go-product-platform/' in (project / '.gitignore').read_text('utf-8') if (project / '.gitignore').exists() else False,
        'project bridge': (project / 'AGENTS.md').is_file() and (project / 'CLAUDE.md').is_file(),
        'Orca setup': (project / 'orca.yaml').is_file() and 'gpp init' in (project / 'orca.yaml').read_text('utf-8'),
        'project scope lock': main.get('skills_scope') == 'project-local',
        'no v13 project vendor': not (project / '.go-product-platform/vendor/addyosmani-agent-skills').exists(),
        'no default project global links': all(not (project / x / 'skills' / n).is_symlink()
                                              for x in ('.agents','.claude') for n in OLD_SKILLS),
        'workflow doc present': (project / 'docs/engineering/workflow.md').is_file(),
        'HLD overview present': (project / 'docs/architecture/hld/overview.md').is_file(),
        'platform version matches CLI': main.get('platform_version') == VERSION,
        'project-specific manager present': (project / '.go-product-platform/project-skills/go-project-platform-manager/SKILL.md').is_file(),
    }
    missing = sorted(n for n in expected if not all((project / p / 'skills' / n / 'SKILL.md').is_file() for p in project_assets.ROOTS))
    if ready or main.get('project_assets'):
        checks['project asset integrity'] = project_assets.healthy(project, main.get('project_assets', {}).get('files', {}))
    checks['manual present'] = (project / 'MANUAL.md').is_file()
    checks['all selected skills in both project directories'] = not missing
    if ready:
        profile = main.get('skills_profile')
        checks['profile selected with required skills'] = (
            profile in PROFILE_DEFAULTS and set(PROFILE_DEFAULTS[profile]).issubset(expected))
    for label, ok in checks.items():
        print(f'{"OK  " if ok else "MISS"} {label}')
    if missing:
        say('Missing project skills: ' + ', '.join(missing))
    if (args.strict or ready) and not all(checks.values()):
        raise RuntimeError('Doctor failed: see MISS items above.')
    if ready:
        plan = json_load(project / CONTRACT)
        validate_plan(project, plan)
        if plan.get('profile') != main.get('skills_profile'):
            raise RuntimeError('Setup contract missing or profile differs: ' + CONTRACT)
        if not set(plan.get('skills', [])).issubset(expected):
            raise RuntimeError('Setup contract skills are not activated')
        check_ready(project, plan)
        say('Product setup verified with fresh checks; this is not release approval.')


def clean(_args) -> None:
    say('Non-destructive archive hook; local databases and outputs remain until explicitly cleaned by devctl.')


# v17 retains user-confirmed global skills inventory, activation and immutable updates.
PROFILE_DEFAULTS = {
    'go-api': ('go-platform-bootstrap', 'golang-design-patterns', 'golang-database', 'golang-testing', 'golang-security', 'go-architecture-review', 'protobuf', 'systematic-debugging'),
    'web': ('go-platform-bootstrap', 'golang-design-patterns', 'golang-database', 'golang-testing', 'protobuf', 'shadcn', 'react-best-practices', 'playwright-cli', 'systematic-debugging'),
    'desktop': ('go-platform-bootstrap', 'golang-design-patterns', 'golang-testing', 'protobuf', 'wails', 'shadcn', 'playwright-cli', 'systematic-debugging'),
    'mobile-native': ('go-platform-bootstrap', 'golang-testing', 'protobuf', 'swiftui-expert-skill', 'swift-concurrency', 'jetpack-compose-performance', 'testing-setup'),
    'ai': ('go-platform-bootstrap', 'golang-testing', 'protobuf', 'ai-sdk', 'ai-elements', 'security-and-hardening'),
    'custom': ('go-platform-bootstrap',),
}
WORKFLOW_SKILLS = ('spec-driven-development', 'planning-and-task-breakdown', 'incremental-implementation', 'test-driven-development', 'code-review-and-quality', 'documentation-and-adrs', 'context-engineering', 'git-workflow-and-versioning')
for _profile in PROFILE_DEFAULTS:
    PROFILE_DEFAULTS[_profile] = ('graphify', *PROFILE_DEFAULTS[_profile])
    if _profile != 'custom':
        PROFILE_DEFAULTS[_profile] = tuple(dict.fromkeys((*WORKFLOW_SKILLS, *PROFILE_DEFAULTS[_profile])))

SKILL_DESCRIPTIONS = {
    'go-platform-bootstrap': 'Установка платформы, создание worktree и обновление навыков',
    'graphify': 'Построение графа исходников и архитектурных связей',
    'orca-cli': 'Работа с окнами, worktrees и окружениями Orca',
    'orchestration': 'Управление несколькими агентами и задачами',
    'computer-use': 'Управление desktop-интерфейсами',
    'orca-linear': 'Работа с задачами Linear',
    'orca-emulator': 'Управление iOS Simulator',
    'orca-emulator-android': 'Управление Android Emulator',
    'orca-per-workspace-env': 'Изоляция окружения каждого worktree',
    'golang-design-patterns': 'Паттерны и архитектура Go без переусложнения',
    'golang-database': 'PostgreSQL, запросы, транзакции, пулы',
    'golang-testing': 'Unit, integration, fuzz и table-driven tests',
    'go-architecture-review': 'Проверка границ Go-модулей',
    'protobuf': 'Protobuf, Buf, совместимость API-контрактов',
    'wails': 'Go + Wails: desktop и доступ к системным API',
    'shadcn': 'Компоненты UI, design tokens, доступность',
    'react-best-practices': 'React-композиция и производительность',
    'playwright-cli': 'Агентное браузерное тестирование',
    'ai-sdk': 'Vercel AI SDK, tools, агентные циклы',
}


def project_selection(project: Path) -> tuple[str | None, list[str]]:
    current = json_load(project / 'go-product-platform.lock.json')
    return current.get('skills_profile'), list(current.get('enabled_global_skills', []))


def catalog_all(manifest: dict) -> dict:
    result = {}
    for repo in manifest['sources']:
        for name in repo['skills']:
            result[name] = repo
    return result


def global_installed(name: str) -> dict:
    return {
        'agents': (AGENT_ROOT / 'skills' / name / 'SKILL.md').is_file(),
        'claude': (CLAUDE_ROOT / 'skills' / name / 'SKILL.md').is_file(),
    }


def inventory_data(args) -> dict:
    manifest = load_manifest(manifest_path(args))
    known = catalog_all(manifest)
    project = Path(args.project).expanduser().resolve() if getattr(args, 'project', None) else None
    profile, active = project_selection(project) if project and (project / '.git').exists() or (project and (project / 'go-product-platform.lock.json').exists()) else (None, [])
    skill_names = sorted(set(known) | set(ORCA_SKILLS) | {'graphify', 'go-platform-bootstrap'})
    discovered = set()
    for home in (AGENT_ROOT, CLAUDE_ROOT):
        folder = home / 'skills'
        if folder.is_dir():
            discovered.update(x.name for x in folder.iterdir() if x.is_dir() and (x / 'SKILL.md').is_file())
    skill_names = sorted(set(skill_names) | discovered)
    lock = json_load(GLOBAL_LOCK)
    return {
        'platform_version': VERSION,
        'global_locations': [str(AGENT_ROOT / 'skills'), str(CLAUDE_ROOT / 'skills')],
        'project': str(project) if project else None,
        'selected_profile': profile,
        'active_global_skills': active,
        'profile_options': {name: list(skills) for name, skills in PROFILE_DEFAULTS.items()},
        'skills': [
            {'name': name, 'description': SKILL_DESCRIPTIONS.get(name, name.replace('-', ' ')),
             'origin': known[name]['repo'] if name in known else ('orca' if name in ORCA_SKILLS else 'external/unmanaged'),
             'status': global_installed(name), 'active': name in active,
             'managed': name in lock.get('skills', {})}
            for name in skill_names
        ],
    }


def skills_inventory(args):
    data = inventory_data(args)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    say('Глобальные skills: ~/.agents/skills и ~/.claude/skills')
    for item in data['skills']:
        status = 'OK' if all(item['status'].values()) else 'MISSING'
        enabled = ' *' if item['active'] else ''
        print(f'  {status:<7} {item["name"]}{enabled} — {item["description"]}')
    if data['selected_profile']:
        say(f'Профиль: {data["selected_profile"]}; активных: {len(data["active_global_skills"])}')


def activate_skills(project: Path, profile: str | None, names: list[str], manifest: dict | None = None) -> None:
    assert_git(project)
    manifest = manifest if manifest is not None else load_manifest(HERE / 'platform/manifests/global-skills.json')
    all_names = set(catalog_all(manifest)) | set(ORCA_SKILLS) | {'graphify', 'go-platform-bootstrap'}
    unknown = sorted(set(names) - all_names)
    if unknown:
        raise RuntimeError('Unknown skills: ' + ', '.join(unknown))
    if profile is not None and profile not in PROFILE_DEFAULTS:
        raise RuntimeError('Unknown profile: ' + profile)
    file = project / 'go-product-platform.lock.json'
    current = json_load(file)
    if current.get('platform_version') != VERSION:
        raise RuntimeError('Initialize or migrate project to current platform before selecting skills.')
    current['skills_profile'] = profile
    current['enabled_global_skills'] = sorted(set(names))
    save_json(file, current)
    write_active_skills(project)


def write_active_skills(project: Path) -> None:
    profile, active = project_selection(project)
    target = project / '.go-product-platform' / 'active-global-skills.md'
    target.parent.mkdir(parents=True, exist_ok=True)
    content = [
        '# Выбранные проектные навыки',
        '', f'Profile: `{profile or "not selected"}`',
        '', 'Use the installed project skills first, as needed by the current task.',
        'Install the approved selection into .agents and .claude with skills-project --approve.', '',
    ]
    for skill in active:
        content.append(f'- `{skill}` — выбран для проекта; наличие проверять только с разрешения пользователя')
    if not active:
        content.append('No skills selected yet. Ask the user to choose an activation profile.')
    target.write_text('\n'.join(content) + '\n', encoding='utf-8')


def skills_activate(args):
    if not args.approve:
        raise RuntimeError('Activation requires --approve after the user confirms the project selection.')
    project = Path(args.project).expanduser().resolve()
    current_profile, current_names = project_selection(project)
    if args.profile is not None and args.names:
        raise RuntimeError('Choose either --profile or --names (not both).')
    if args.add and args.remove:
        raise RuntimeError('Choose --add or --remove, not both.')
    profile = args.profile if args.profile is not None else (current_profile or 'custom')
    names = list(PROFILE_DEFAULTS[profile]) if args.profile else [n.strip() for n in args.names.split(',') if n.strip()]
    if args.add:
        names = sorted(set(current_names) | set(names))
    if args.remove:
        names = sorted(set(current_names) - set(names))
    activate_skills(project, profile, names)
    say(f'Activated {len(names)} global skills in product profile {profile}. No global files changed.')


def remote_head(repo: str) -> str:
    command = run(['git', 'ls-remote', repo, 'HEAD'], capture=True)
    if not command.stdout.strip():
        raise RuntimeError(f'Git remote did not return HEAD for {repo}')
    sha = command.stdout.strip().split()[0]
    if len(sha) not in (40, 64) or not all(c in '0123456789abcdef' for c in sha):
        raise RuntimeError(f'Invalid Git SHA from remote: {repo}')
    return sha


def check_updates_data(args) -> dict:
    manifest = load_manifest(manifest_path(args))
    lock = json_load(GLOBAL_LOCK)
    project = Path(args.project).expanduser().resolve() if args.project else None
    _, active = project_selection(project) if project else (None, [])
    scope = set(active) if args.selected_only else set(lock.get('skills', {}))
    sources = []
    for entry in manifest['sources']:
        names = sorted(name for name in entry['skills'] if name in scope)
        if not names:
            continue
        installed = lock.get('repositories', {}).get(entry['key'], {}).get('commit')
        record = {'key': entry['key'], 'repo': entry['repo'], 'skills': names,
                  'installed_sha': installed, 'latest_sha': None, 'status': 'not-managed' if not installed else 'unknown'}
        if installed and not args.offline:
            try:
                latest = remote_head(entry['repo'])
                record['latest_sha'] = latest
                record['status'] = 'update-available' if latest != installed else 'current'
            except RuntimeError as err:
                record['status'] = 'unavailable'
                record['error'] = str(err)
        sources.append(record)
    return {
        'platform_version': VERSION, 'checked_at': datetime.now(timezone.utc).isoformat(),
        'mode': 'offline' if args.offline else 'remote-head', 'selected_only': args.selected_only,
        'sources': sources, 'external_tools': [
            {'name': 'orca', 'update_method': 'Orca Settings > Agents > Update skills or `orca skills update --skill NAME` after user approval'},
            {'name': 'graphify', 'update_method': '`uv tool upgrade graphifyy` after user approval'},
        ],
    }


def skills_check_updates(args):
    data = check_updates_data(args)
    if args.output:
        out = Path(args.output).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        save_json(out, data)
        if not args.json:
            say(f'План проверки сохранён: {out}')
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    for source in data['sources']:
        short = (source['installed_sha'] or 'none')[:12]
        latest = (source['latest_sha'] or 'unknown')[:12]
        print(f'{source["key"]:<24} {source["status"]:<19} {short} -> {latest}')
    say('Обновление не выполнялось. Для любых изменений требуется согласие пользователя.')


def installed_source_references(entry: dict, snapshot: Path, sha: str, requested: set[str]) -> list[tuple[str, Path]]:
    res = []
    for name, rel in entry['skills'].items():
        if name not in requested:
            continue
        path = (snapshot / rel).resolve()
        if not path.is_relative_to(snapshot.resolve()) or not (path / 'SKILL.md').is_file():
            raise RuntimeError('Skill source missing for ' + name)
        res.append((name, path))
    return res


def safe_repoint(skill: str, target: Path, entry: dict, old_sha: str | None) -> None:
    """Replace only the symlink owned by this platform, never user-managed dirs."""
    for root in (AGENT_ROOT, CLAUDE_ROOT):
        dst = root / 'skills' / skill
        if dst.is_symlink():
            real = dst.resolve()
            expected_root = GLOBAL_PLATFORM / 'vendor' / entry['key']
            if not real.is_relative_to(expected_root.resolve()):
                raise RuntimeError(f'Refusing to replace a foreign global skill: {dst}')
            if old_sha and not real.is_relative_to((expected_root / old_sha).resolve()):
                raise RuntimeError(f'Unexpected currently installed version: {dst}')
        elif dst.exists():
            raise RuntimeError(f'Refusing to replace user-owned directory: {dst}')


def atomic_repoint(names_targets: list[tuple[str, Path]], entry: dict, old_sha: str | None) -> None:
    # Preflight every path before making changes.
    for name, target in names_targets:
        safe_repoint(name, target, entry, old_sha)
    changes = []
    try:
        for name, target in names_targets:
            for root in (AGENT_ROOT, CLAUDE_ROOT):
                dst = root / 'skills' / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                previous = os.readlink(dst) if dst.is_symlink() else None
                tmp = dst.parent / ('.' + name + '.gpp-new')
                if tmp.exists() or tmp.is_symlink():
                    raise RuntimeError(f'Temporary skill link already exists: {tmp}')
                tmp.symlink_to(os.path.relpath(target, dst.parent), target_is_directory=True)
                os.replace(tmp, dst)
                changes.append((dst, previous))
    except Exception:
        for dst, previous in reversed(changes):
            if previous:
                if dst.is_symlink():
                    dst.unlink()
                dst.symlink_to(previous, target_is_directory=True)
            elif dst.is_symlink():
                dst.unlink()
        raise


def upgrade_from_plan(args):
    if not args.approve:
        raise RuntimeError('Updating global skills requires --approve and user confirmation.')
    plan = json_load(Path(args.plan).expanduser().resolve())
    if plan.get('platform_version') != VERSION:
        raise RuntimeError('Update plan generated for a different platform version.')
    manifest = load_manifest(manifest_path(args))
    entries = {e['key']: e for e in manifest['sources']}
    lock = json_load(GLOBAL_LOCK)
    any_changes = False
    requested_sources = {x.strip() for x in getattr(args, 'sources', '').split(',') if x.strip()}
    plan_sources = {row['key'] for row in plan.get('sources', [])}
    if requested_sources - plan_sources:
        raise RuntimeError('Unknown sources not in the approved plan: ' + ', '.join(sorted(requested_sources - plan_sources)))
    for row in plan.get('sources', []):
        if requested_sources and row['key'] not in requested_sources:
            continue
        if row['status'] != 'update-available':
            continue
        key = row['key']
        entry = entries.get(key)
        if not entry or entry['repo'] != row['repo']:
            raise RuntimeError(f'Manifest changed for {key}; regenerate update plan.')
        pinned = lock.get('repositories', {}).get(key, {}).get('commit')
        if pinned != row['installed_sha']:
            raise RuntimeError(f'{key}: installed SHA changed after plan generation; regenerate.')
        to_sha = row['latest_sha']
        if not to_sha or remote_head(entry['repo']) != to_sha:
            raise RuntimeError(f'{key}: upstream HEAD changed; regenerate plan and confirm new SHA.')
        names = {name for name, sk in lock.get('skills', {}).items() if sk.get('source') == key}
        if not names:
            continue
        newpath = GLOBAL_PLATFORM / 'vendor' / key / to_sha
        if not newpath.exists():
            cache = CACHE_ROOT / 'updates' / key / to_sha
            if not cache.exists():
                cache.parent.mkdir(parents=True, exist_ok=True)
                run(['git', 'clone', '--depth', '1', '--filter=blob:none', '--sparse', entry['repo'], str(cache)])
                run(['git', '-C', str(cache), 'sparse-checkout', 'set', *list(entry['skills'].values()), *([entry['references']] if entry.get('references') else [])])
            observed = run(['git', '-C', str(cache), 'rev-parse', 'HEAD'], capture=True).stdout.strip()
            if observed != to_sha:
                raise RuntimeError(f'{key}: checkout {observed} differs from approved SHA {to_sha}.')
            newpath.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(cache, newpath, ignore=shutil.ignore_patterns('.git'))
        targets = installed_source_references(entry, newpath, to_sha, names)
        atomic_repoint(targets, entry, pinned)
        if entry.get('references'):
            newrefs = newpath / entry['references']
            if not newrefs.is_dir():
                raise RuntimeError(f'{key}: shared references missing')
            for root in (AGENT_ROOT, CLAUDE_ROOT):
                dst = root / 'references'
                if dst.is_symlink():
                    expected_root = GLOBAL_PLATFORM / 'vendor' / key
                    if dst.resolve().is_relative_to(expected_root.resolve()):
                        tmp = root / '.references.gpp-new'
                        if tmp.exists() or tmp.is_symlink():
                            raise RuntimeError(f'Temporary shared reference link already exists: {tmp}')
                        tmp.symlink_to(os.path.relpath(newrefs, dst.parent), target_is_directory=True)
                        os.replace(tmp, dst)
        for name, _ in targets:
            lock['skills'][name] = {'source': key, 'commit': to_sha, 'path': entry['skills'][name]}
        lock['repositories'][key] = {'repo': entry['repo'], 'commit': to_sha}
        lock.setdefault('history', []).append({'source': key, 'from': pinned, 'to': to_sha, 'at': datetime.now(timezone.utc).isoformat()})
        save_json(GLOBAL_LOCK, lock)
        say(f'Обновлены {key}: {pinned[:12]} -> {to_sha[:12]} (оба глобальных каталога).')
        any_changes = True
    if not any_changes:
        say('Нет выбранных обновлений, ничего не изменено.')


def global_install_selected(args):
    if not args.approve:
        raise RuntimeError('Global installation requires --approve after user confirmation.')
    manifest = load_manifest(manifest_path(args))
    catalog = catalog_all(manifest)
    chosen = [v.strip() for v in args.names.split(',') if v.strip()]
    unknown = sorted(set(chosen) - set(catalog) - {'go-platform-bootstrap'})
    if unknown:
        raise RuntimeError('Unknown curated skills (Orca/Graphify have their own installers): ' + ', '.join(unknown))
    if not chosen:
        raise RuntimeError('No global skill names selected.')
    if 'go-platform-bootstrap' in chosen:
        if not global_bootstrap_skill():
            raise RuntimeError('Could not install global bootstrap skill')
    curated = [name for name in chosen if name in catalog]
    if not curated:
        return
    args.names = ','.join(curated)
    args.dry_run, args.offline, args.refresh, args.continue_on_error = False, False, False, False
    install_curated(args)



def install_external_selected(args):
    if not args.approve:
        raise RuntimeError('External global skill installation requires explicit approval.')
    selected = {v.strip() for v in args.names.split(',') if v.strip()}
    unknown = selected - set(ORCA_SKILLS) - {'graphify'}
    if unknown:
        raise RuntimeError('Unknown official external skills: ' + ', '.join(sorted(unknown)))
    if 'graphify' in selected:
        install_graphify(argparse.Namespace(dry_run=False))
    orca = sorted(selected & set(ORCA_SKILLS))
    if orca:
        if shutil.which('orca'):
            command = ['orca','skills','install']
            for name in orca:
                command.extend(['--skill',name])
            command.extend(['--agent','claude-code,codex'])
            run(command)
        elif shutil.which('npx'):
            for name in orca:
                run(['npx','skills','add',ORCA_URL,'--skill',name,'--global','--yes'])
        else:
            raise RuntimeError('Orca CLI or npx is required for Orca skill installation.')
        not_present = [name for name in orca if not all(global_installed(name).values())]
        if not_present:
            raise RuntimeError('Not installed in both global directories: '+', '.join(not_present))


def update_external_selected(args):
    if not args.approve:
        raise RuntimeError('Updating Orca/Graphify requires explicit approval.')
    selected = {v.strip() for v in args.names.split(',') if v.strip()}
    unknown = selected - set(ORCA_SKILLS) - {'graphify'}
    if unknown:
        raise RuntimeError('Unknown external skills: ' + ', '.join(sorted(unknown)))
    if 'graphify' in selected:
        if not shutil.which('uv'):
            raise RuntimeError('uv is required for Graphify upgrades.')
        run(['uv', 'tool', 'upgrade', 'graphifyy'])
    orca = sorted(selected & set(ORCA_SKILLS))
    if orca:
        if shutil.which('orca'):
            command = ['orca','skills','update']
            for name in orca:
                command.extend(['--skill',name])
            run(command)
        elif shutil.which('npx'):
            run(['npx','skills','update',*orca,'--global','-y'])
        else:
            raise RuntimeError('Orca CLI or npx is required for updates.')


def ask(prompt: str, default: bool = False) -> bool:
    suffix = ' [Y/n] ' if default else ' [y/N] '
    while True:
        value = input(prompt + suffix).strip().lower()
        if not value:
            return default
        if value in ('y', 'yes', 'д', 'да'):
            return True
        if value in ('n', 'no', 'н', 'нет'):
            return False
        print('Введите y или n.')


def install_canvas(args):
    """Delegate to an explicitly selected, reviewed official canvas checkout."""
    if not args.approve:
        raise RuntimeError('Canvas installation requires --approve after reviewing the source and installation plan.')
    project = Path(args.project).expanduser().resolve()
    assert_git(project)
    source = Path(args.source).expanduser().resolve()
    installer = source / 'canvas_setup.py'
    if not installer.is_file() or not (source / 'canvas/install.py').is_file():
        raise RuntimeError('Expected a reviewed app-canvas checkout with canvas_setup.py and canvas/install.py.')
    cmd = [sys.executable, str(installer), '--project', str(project)]
    for name in ('app', 'kit', 'color', 'tag'):
        value = getattr(args, name, None)
        if value:
            cmd.extend(['--' + name, value])
    run(cmd, cwd=project)
    say('Canvas installer completed. Follow its next steps; run python3 .canvas/board.py doctor before use.')


def wizard(args):
    if not sys.stdin.isatty() and not args.allow_pipe:
        raise RuntimeError('Interactive wizard needs a TTY. Agents should use `skills-inventory --json` and explicitly confirmed apply commands.')
    project = Path(args.project).expanduser().resolve()
    assert_git(project)
    manifest = load_manifest(manifest_path(args))
    catalog = catalog_all(manifest)
    print('\n=== Go Product Platform — мастер установки ===')
    print('Можно подключить: Go, API/Buf, React/UI, Wails, Mobile, AI, тестирование, Graphify и Orca.')
    print('Выбранные skills, агенты и референсы устанавливаются в .agents и .claude продукта.')
    check_globals = ask('Проверить наличие глобальных навыков?', True)
    if check_globals:
        data = inventory_data(argparse.Namespace(project=str(project), manifest=args.manifest))
        present = sum(all(s['status'].values()) for s in data['skills'])
        print(f'Найдено {present}/{len(data["skills"])} навыков в обоих глобальных каталогах.')
        for s in data['skills']:
            if not all(s['status'].values()):
                print(f'  - {s["name"]}: отсутствует в одном или обоих каталогах')
    print('\nПрофили:')
    options = list(PROFILE_DEFAULTS)
    for idx, (name, members) in enumerate(PROFILE_DEFAULTS.items(), 1):
        print(f'  {idx}. {name} ({len(members)} рекомендованных skills)')
    answer = input('Номер профиля [2]: ').strip() or '2'
    if not answer.isdigit() or not 1 <= int(answer) <= len(options):
        raise RuntimeError('Некорректный номер профиля.')
    profile = options[int(answer) - 1]
    chosen = list(PROFILE_DEFAULTS[profile])
    print('\nБудут установлены ПРОЕКТНЫЕ skills (с агентами и референсами):')
    for name in chosen:
        print(f'  - {name}: {SKILL_DESCRIPTIONS.get(name, name)}')
    extras = input('Дополнительные skills через запятую (или Enter): ').strip()
    if extras:
        chosen.extend(v.strip() for v in extras.split(',') if v.strip())
    invalid = set(chosen) - (set(catalog) | set(ORCA_SKILLS) | {'graphify', 'go-platform-bootstrap'})
    if invalid:
        raise RuntimeError('Неизвестные skills: ' + ', '.join(sorted(invalid)))
    missing = [name for name in sorted(set(chosen)) if not all(global_installed(name).values())] if check_globals else []
    to_install = []
    external_installs = []
    bootstrap_install = False
    if check_globals and missing:
        print('Не найдены глобально:', ', '.join(missing))
        for name in missing:
            if name in catalog:
                print('   GitHub:', catalog[name]['repo'], '→', name)
        if ask('Установить недостающие curated skills глобально?', False):
            to_install = [n for n in missing if n in catalog]
            bootstrap_install = 'go-platform-bootstrap' in missing
        unhandled = sorted(set(missing) & (set(ORCA_SKILLS) | {'graphify'}))
        if unhandled and ask('Установить выбранные Orca/Graphify skills глобально их официальным инструментом?', False):
            external_installs = unhandled
    wants_updates = False
    if check_globals and ask('Проверить версии уже установленных skills в GitHub? (требуется сеть)', False):
        updates = check_updates_data(argparse.Namespace(manifest=args.manifest, project=str(project), selected_only=False, offline=False))
        for s in updates['sources']:
            print(f'  {s["key"]}: {s["status"]} {str(s["installed_sha"] or "")[:12]} -> {str(s["latest_sha"] or "")[:12]}')
        wants_updates = bool([s for s in updates['sources'] if s['status'] == 'update-available']) and ask('Установить показанные обновления после подтверждения?', False)
    print('Canvas для UI: https://gitlab16.skiftrade.kz/design/app-canvas')
    print('Установка может скачать Node.js, зависимости и настроить адаптеры агентов. Сначала проверьте исходники.')
    canvas_source = input('Путь к проверенному клону app-canvas (Enter — без canvas): ').strip()
    print('\nИТОГ:')
    print(f'  Проект: {project}\n  Профиль: {profile}\n  Активные skills: {", ".join(sorted(set(chosen))) or "нет"}')
    print(f'  Глобально установить: {", ".join(to_install + external_installs + (["go-platform-bootstrap"] if bootstrap_install else [])) or "нет"}')
    print(f'  Обновления глобальных skills: {"да" if wants_updates else "нет"}')
    print(f'  Canvas: {canvas_source or "не устанавливать"}')
    print(json.dumps(project_asset_plan(chosen, manifest), ensure_ascii=False, indent=2))
    if not ask('Применить этот план?', False):
        say('Отменено; глобальные skills и проект не менялись.')
        return
    lock = json_load(project / 'go-product-platform.lock.json')
    if lock and lock.get('platform_version') != VERSION:
        raise RuntimeError('Проект другой версии; сначала выполните явную миграцию.')
    init(argparse.Namespace(project=str(project)))
    activate_skills(project, profile, chosen)
    if to_install or bootstrap_install:
        global_install_selected(argparse.Namespace(names=','.join(to_install + (["go-platform-bootstrap"] if bootstrap_install else [])), approve=True, manifest=args.manifest))
    if external_installs:
        install_external_selected(argparse.Namespace(names=','.join(external_installs), approve=True))
    if to_install or external_installs or bootstrap_install:
        write_active_skills(project)
    if wants_updates:
        planpath = project / '.go-product-platform/global-skills-update-plan.json'
        save_json(planpath, updates)
        upgrade_from_plan(argparse.Namespace(plan=str(planpath), approve=True, manifest=args.manifest))
    if canvas_source:
        install_canvas(argparse.Namespace(project=str(project), source=canvas_source, approve=True))
    install_project_assets(project, manifest)
    say('Мастер завершён. В следующий раз просто попросите агента проверить или обновить навыки.')



def project_asset_plan(names: list[str], manifest: dict) -> dict:
    catalog = catalog_all(manifest)
    selected_sources = {catalog[name]['key']: catalog[name] for name in names if name in catalog}
    supporting_assets = []
    for key, source in sorted(selected_sources.items()):
        resources = [('references', source.get('references')), ('agents', source.get('agents'))]
        resources += [(path, path) for path in source.get('resources', [])]
        for destination, path in resources:
            if path:
                supporting_assets.append({
                    'source': source['repo'], 'source_key': key, 'source_path': path,
                    'revision': source.get('revision', 'pinned global snapshot'),
                    'paths': [f'{root}/{destination}' for root in project_assets.ROOTS],
                })
    return {
        'supporting_assets': supporting_assets,
        'locations': ['.agents', '.claude'],
        'skills': [{'name': name, 'purpose': SKILL_DESCRIPTIONS.get(name, name.replace('-', ' ')),
                    'source': catalog[name]['repo'] if name in catalog else 'installed external tool / platform',
                    'revision': catalog[name].get('revision', 'pinned global snapshot') if name in catalog else 'content hash',
                    'paths': [f'{root}/skills/{name}' for root in project_assets.ROOTS]}
                   for name in sorted(set(names))] + [{'name': 'go-project-platform-manager', 'purpose': 'Управление проектными навыками и настройкой платформы', 'revision': VERSION, 'source': 'go-product-platform', 'paths': [f'{root}/skills/go-project-platform-manager' for root in project_assets.ROOTS]}],
        'agents': ['product-developer', 'product-reviewer'],
        'references': ['supporting files of each selected skill', 'go-product-platform',
                       manifest.get('workflow', {'error': 'workflow source not configured'})],
        'policy': 'Проектные копии имеют приоритет. Установка только после согласования этого списка.',
    }


def install_project_assets(project: Path, manifest: dict) -> None:
    _, names = project_selection(project)
    catalog = catalog_all(manifest)
    files, sources = {}, {}
    global_lock = json_load(GLOBAL_LOCK)
    for name in names:
        source = AGENT_ROOT / 'skills' / name
        if not (source / 'SKILL.md').is_file():
            raise RuntimeError(f'Install selected skill before project copy: {name}')
        if name == 'go-platform-bootstrap':
            prefix = 'skills/go-platform-bootstrap'
            project_assets.collect(HERE / 'platform/skills/go-platform-bootstrap', prefix, files)
            project_assets.collect(HERE / 'installer', 'references/go-platform-runtime/installer', files)
            project_assets.collect(HERE / 'platform', 'references/go-platform-runtime/platform', files)
        else:
            project_assets.collect(source.resolve(), 'skills/' + name, files)
        entry = catalog.get(name)
        if entry:
            pinned = global_lock.get('skills', {}).get(name)
            if not pinned:
                raise RuntimeError(f'Missing provenance for selected skill: {name}')
            if entry.get('revision') and pinned['commit'] != entry['revision']:
                raise RuntimeError(f'{name}: installed revision differs from approved manifest')
            snapshot = GLOBAL_PLATFORM / 'vendor' / entry['key'] / pinned['commit']
            if not source.resolve().is_relative_to(snapshot.resolve()):
                raise RuntimeError(f'{name}: installed source differs from lock')
            sources[entry['key']] = {'repo': entry['repo'], 'commit': pinned['commit']}
            if entry.get('references'):
                project_assets.collect(snapshot / entry['references'], 'references', files)
            if entry.get('agents'):
                project_assets.collect(snapshot / entry['agents'], 'agents', files)
            for resource in entry.get('resources', []):
                project_assets.collect(snapshot / resource, resource, files)
        else:
            sources[name] = {'origin': 'installed external tool / platform', 'path': str(source.resolve())}
    workflow = manifest.get('workflow')
    if not workflow:
        raise RuntimeError('Manifest must configure software-development-workflow')
    snapshot, sha = cache_source(workflow)
    if not (snapshot / 'docs/workflow.md').is_file():
        raise RuntimeError('software-development-workflow docs/workflow.md missing')
    project_assets.collect(snapshot, 'references/software-development-workflow', files)
    sources[workflow['key']] = {'repo': workflow['repo'], 'commit': sha}
    project_assets.collect(HERE / 'platform/references', 'references/go-product-platform', files)
    project_assets.collect(HERE / 'platform/handbook', 'references/go-product-platform/handbook', files)
    project_assets.collect(HERE / 'platform/project-agents', 'agents', files)
    project_assets.collect(HERE / 'platform/project-skill-templates/go-project-platform-manager',
                           'skills/go-project-platform-manager', files)
    lockfile = project / 'go-product-platform.lock.json'
    lock = json_load(lockfile)
    hashes = project_assets.install(project, files, lock.get('project_assets', {}).get('files', {}))
    lock['project_assets'] = {'sources': sources, 'files': hashes}
    save_json(lockfile, lock)
    write_bridge(project)
    say('Project skills, agents and references installed in .agents and .claude.')


def skills_project(args) -> None:
    project = Path(args.project).expanduser().resolve()
    assert_git(project)
    manifest = load_manifest(manifest_path(args))
    _, names = project_selection(project)
    if not names:
        raise RuntimeError('Select a project skill profile first')
    print(json.dumps(project_asset_plan(names, manifest), ensure_ascii=False, indent=2))
    if args.approve:
        install_project_assets(project, manifest)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Go Product Platform v17 (agent docs, skills, artifact contract)')
    commands = p.add_subparsers(dest='command', required=True)
    canvas = commands.add_parser('canvas-install', help='Install optional UI canvas from a reviewed app-canvas checkout')
    canvas.add_argument('--project', default='.')
    canvas.add_argument('--source', required=True, help='Reviewed local clone of https://gitlab16.skiftrade.kz/design/app-canvas')
    canvas.add_argument('--approve', action='store_true')
    for option in ('app', 'kit', 'color', 'tag'):
        canvas.add_argument('--' + option)
    canvas.set_defaults(handler=install_canvas)
    pa = commands.add_parser('skills-project', help='Review/install portable project skills, agents and references')
    pa.add_argument('--project', default='.')
    pa.add_argument('--manifest')
    pa.add_argument('--json', action='store_true')
    pa.add_argument('--approve', action='store_true')
    pa.set_defaults(handler=skills_project)
    commands.add_parser('install-cli').set_defaults(handler=install_cli)
    g = commands.add_parser('setup-global', help='Once per macOS account: shared skills and tools')
    for flag in ('skills','graphify','orca','dry-run','offline','refresh','continue-on-error'):
        g.add_argument('--'+flag, action='store_true')
    g.add_argument('--manifest', help='Override skills manifest (explicit trusted source for tests)')
    g.add_argument('--names', default='', help='Install only listed skill names (from matched sources)')
    g.set_defaults(handler=setup_global)
    o = commands.add_parser('orca-install', help='Install Orca skills into both user-global folders')
    o.add_argument('--dry-run', action='store_true'); o.set_defaults(handler=orca_install)
    i = commands.add_parser('init', help='Initialize platform docs; optionally apply an approved product setup plan')
    i.add_argument('--project', default='.')
    i.add_argument('--offline', action='store_true', help='Restore materials without network/global writes; incompatible with setup options')
    i.add_argument('--setup', action='store_true', help='Print a profile setup contract to complete and review (no writes)')
    i.add_argument('--profile', choices=list(PROFILE_DEFAULTS))
    i.add_argument('--names', default='', help='Additional skills for the setup preview')
    i.add_argument('--json', action='store_true', help='Machine-readable setup contract; use with --setup')
    i.add_argument('--setup-plan', help='Apply a reviewed JSON setup contract, including its commands and missing global skills')
    i.add_argument('--approve', action='store_true')
    i.add_argument('--manifest')
    i.set_defaults(handler=init)
    m = commands.add_parser('migrate', help='Explicit migration v13/v14/v15/v16 to v17 and global-skills model')
    m.add_argument('--project', default='.')
    m.add_argument('--allow-missing-global', action='store_true', help='Use only for offline troubleshooting')
    m.set_defaults(handler=migrate)
    d = commands.add_parser('doctor', help='Validate project and global skill locations')
    d.add_argument('--project', default='.')
    d.add_argument('--manifest')
    d.add_argument('--strict', action='store_true')
    d.add_argument('--ready', action='store_true', help='Require profile skills and execute trusted product setup checks')
    d.set_defaults(handler=doctor)
    gr = commands.add_parser('graph-build')
    gr.add_argument('--project', default='.'); gr.set_defaults(handler=graph_build)
    si = commands.add_parser('skills-inventory', help='Read-only JSON inventory for agents and wizard')
    si.add_argument('--project', default='.')
    si.add_argument('--manifest')
    si.add_argument('--json', action='store_true')
    si.set_defaults(handler=skills_inventory)
    sa = commands.add_parser('skills-activate', help='Select existing global skills for this project, without copying')
    sa.add_argument('--project', default='.')
    sa.add_argument('--profile', choices=list(PROFILE_DEFAULTS))
    sa.add_argument('--names', default='')
    sa.add_argument('--add', action='store_true')
    sa.add_argument('--remove', action='store_true')
    sa.add_argument('--approve', action='store_true', help='Only after user confirmation')
    sa.set_defaults(handler=skills_activate)
    su = commands.add_parser('skills-check-updates', help='Read-only remote revision check; creates exact-SHA plan')
    su.add_argument('--project', default='.')
    su.add_argument('--manifest')
    su.add_argument('--offline', action='store_true')
    su.add_argument('--selected-only', action='store_true')
    su.add_argument('--json', action='store_true')
    su.add_argument('--output')
    su.set_defaults(handler=skills_check_updates)
    sg = commands.add_parser('skills-install-global', help='Install selected curated skills globally with user approval')
    sg.add_argument('--names', required=True)
    sg.add_argument('--approve', action='store_true')
    sg.add_argument('--manifest')
    sg.set_defaults(handler=global_install_selected)
    sx = commands.add_parser('skills-upgrade-global', help='Apply exact-SHA previously approved update plan')
    sx.add_argument('--plan', required=True)
    sx.add_argument('--manifest')
    sx.add_argument('--approve', action='store_true')
    sx.add_argument('--sources', default='', help='Comma-separated subset of source keys in update plan')
    sx.set_defaults(handler=upgrade_from_plan)
    se = commands.add_parser('skills-install-external', help='Official global Orca/Graphify install after user approval')
    se.add_argument('--names', required=True)
    se.add_argument('--approve', action='store_true')
    se.set_defaults(handler=install_external_selected)
    seu = commands.add_parser('skills-update-external', help='Official global Orca/Graphify updates after user approval')
    seu.add_argument('--names', required=True)
    seu.add_argument('--approve', action='store_true')
    seu.set_defaults(handler=update_external_selected)
    sw = commands.add_parser('wizard', help='Interactive first-run questionnaire (not used in Orca worktree hooks)')
    sw.add_argument('--project', default='.')
    sw.add_argument('--manifest')
    sw.add_argument('--allow-pipe', action='store_true', help='For automated tests only')
    sw.set_defaults(handler=wizard)
    c = commands.add_parser('clean')
    c.add_argument('--project', default='.')
    c.add_argument('--worktree', action='store_true'); c.set_defaults(handler=clean)
    return p


if __name__ == '__main__':
    try:
        args = parser().parse_args()
        args.handler(args)
    except (RuntimeError, ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(f'[gpp] ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
