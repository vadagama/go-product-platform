"""Profile setup contracts. Commands are reviewed project code, never shell strings."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

CONTRACT = 'go-product-platform.setup.json'
BASE_TOOLS = ('git', 'go', 'buf', 'graphify')
BASE_COMPONENTS = ('go', 'contracts', 'database', 'environment')
PROFILES = {
    'go-api': (('psql',), ()),
    'web': (('psql', 'node', 'pnpm'), ('frontend', 'ui', 'e2e')),
    'ai': (('psql', 'node', 'pnpm'), ('frontend', 'ui', 'e2e', 'ai')),
    'desktop': (('node', 'pnpm', 'wails3'), ('frontend', 'ui', 'e2e', 'desktop')),
    'mobile-native': (('psql',), ('mobile',)),
    'custom': ((), ()),
}


def setup_plan(profile: str) -> dict:
    tools, components = PROFILES[profile]
    return {
        'schema_version': 1,
        'profile': profile,
        'setup': [],
        'skills': [],
        'tools': [{'name': name, 'argv': [name, {'go': 'version', 'graphify': '--help'}.get(name, '--version')]}
                  for name in (*BASE_TOOLS, *tools)],
        'components': [{'name': name, 'paths': [], 'checks': []}
                       for name in (*BASE_COMPONENTS, *components)],
    }


def inside(project: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise RuntimeError('Setup paths must be nonempty and relative to the product')
    path = (project / value).resolve()
    if not path.is_relative_to(project):
        raise RuntimeError('Setup path escapes product: ' + value)
    return path


def validate_command(project: Path, command: dict) -> None:
    if not isinstance(command, dict):
        raise RuntimeError('Setup command must be an object')
    argv = command.get('argv')
    if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x or '\x00' in x for x in argv):
        raise RuntimeError('Setup command needs a nonempty argv array of strings')
    inside(project, command.get('cwd', '.'))
    timeout = command.get('timeout', 300)
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise RuntimeError('Command timeout must be 1..3600 seconds')


def validate_plan(project: Path, plan: dict) -> None:
    if not isinstance(plan, dict) or plan.get('schema_version') != 1 or plan.get('profile') not in PROFILES:
        raise RuntimeError('Unsupported setup schema/profile')
    expected = setup_plan(plan['profile'])
    skills = plan.get('skills', [])
    if not isinstance(skills, list) or any(not isinstance(x, str) or not x for x in skills):
        raise RuntimeError('Setup skills must be an array of names')
    for group in ('tools', 'components'):
        entries = plan.get(group)
        if not isinstance(entries, list) or any(not isinstance(x, dict) or not isinstance(x.get('name'), str) for x in entries):
            raise RuntimeError('Invalid setup ' + group)
        names = [x['name'] for x in entries]
        if len(names) != len(set(names)) or not all(names):
            raise RuntimeError('Duplicate or empty setup names')
        missing = {x['name'] for x in expected[group]} - set(names)
        if missing:
            raise RuntimeError('Missing required ' + group + ': ' + ', '.join(sorted(missing)))
    for tool in plan['tools']:
        validate_command(project, tool)
    setup = plan.get('setup', [])
    if not isinstance(setup, list):
        raise RuntimeError('Setup must be a command array')
    for command in setup:
        validate_command(project, command)
    for component in plan['components']:
        paths, checks = component.get('paths'), component.get('checks')
        if not isinstance(paths, list) or not paths or not isinstance(checks, list) or not checks:
            raise RuntimeError('Component needs artifact paths and executable checks: ' + component['name'])
        for value in paths:
            inside(project, value)
        for command in checks:
            validate_command(project, command)


def execute(project: Path, command: dict) -> None:
    # Revalidate resolved paths immediately before execution (setup may add symlinks).
    validate_command(project, command)
    cwd = inside(project, command.get('cwd', '.'))
    print('[gpp] RUN ' + json.dumps(command['argv'], ensure_ascii=False), flush=True)
    try:
        subprocess.run(command['argv'], cwd=cwd, check=True, timeout=command.get('timeout', 300))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
        raise RuntimeError('Setup/check failed: ' + str(error)) from error


def check_ready(project: Path, plan: dict) -> None:
    validate_plan(project, plan)
    for tool in plan['tools']:
        execute(project, tool)
    for component in plan['components']:
        for value in component['paths']:
            path = inside(project, value)
            if not path.exists() or (path.is_file() and path.stat().st_size == 0):
                raise RuntimeError('Missing/empty artifact for ' + component['name'] + ': ' + value)
        for command in component['checks']:
            execute(project, command)
        print('[gpp] READY ' + component['name'], flush=True)
