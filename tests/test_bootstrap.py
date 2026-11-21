"""Offline regression tests. They never fetch GitHub or modify actual user HOME."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'installer/gpp.py'


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.project = self.root / 'product'
        self.project.mkdir()
        subprocess.run(['git','init','-q','-b','main',str(self.project)],check=True)
        self.home = self.root / 'mac-home'
        self.home.mkdir()
        self.env = {**os.environ,
                    'GPP_USER_HOME': str(self.home),
                    'GPP_CACHE_HOME': str(self.home / '.cache/gpp'),
                    'GPP_HOME': str(self.home / '.local/share/gpp'),
                    'GPP_BIN_DIR': str(self.home / '.local/bin')}
        self.repo = self.root / 'mock-remote-repo'
        (self.repo / 'skills/one').mkdir(parents=True)
        (self.repo / 'skills/two').mkdir(parents=True)
        (self.repo / 'references').mkdir()
        (self.repo / 'skills/one/SKILL.md').write_text('---\nname: one\ndescription: Test one\n---\n')
        (self.repo / 'skills/two/SKILL.md').write_text('---\nname: two\ndescription: Test two\n---\n')
        (self.repo / 'references/guide.md').write_text('Shared references')
        (self.repo / 'docs').mkdir()
        (self.repo / 'docs/workflow.md').write_text('Workflow fixture')
        subprocess.run(['git','init','-q',str(self.repo)],check=True)
        subprocess.run(['git','-C',str(self.repo),'config','user.email','test@example.test'],check=True)
        subprocess.run(['git','-C',str(self.repo),'config','user.name','test'],check=True)
        subprocess.run(['git','-C',str(self.repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.repo),'commit','-qm','first'],check=True)
        self.manifest = self.root / 'global-skills.json'
        self.manifest.write_text(json.dumps({'manifest_version':'15.0.0','sources':[
            {'key':'testrepo','repo':str(self.repo), 'skills':{'one':'skills/one','two':'skills/two'},'references':'references'}
        ], 'workflow': {'key': 'workflow', 'repo': str(self.repo), 'skills': {}, 'references': 'docs'}}))

    def call(self, *args, check=True):
        return subprocess.run([sys.executable,str(SCRIPT),*args],env=self.env,check=check,text=True,capture_output=True)

    def global_skills(self):
        self.call('setup-global','--skills','--manifest',str(self.manifest))

    def prepare_project_assets(self):
        self.global_skills()
        self.call('init', '--project', str(self.project), '--offline')
        lockpath = self.project / 'go-product-platform.lock.json'
        lock = json.loads(lockpath.read_text())
        lock['enabled_global_skills'] = ['one']
        lockpath.write_text(json.dumps(lock))
        return ('skills-project', '--project', str(self.project), '--manifest', str(self.manifest))

    def test_project_asset_review_install_portability_and_manual(self):
        args = self.prepare_project_assets()
        review = json.loads(self.call(*args, '--json').stdout)
        self.assertEqual(review['skills'][0]['name'], 'one')
        self.assertFalse((self.project / '.agents').exists())
        self.call(*args, '--approve')
        manual = self.project / 'MANUAL.md'
        manual.write_text(manual.read_text() + '\nРучные команды запуска\n')
        self.call(*args, '--approve')
        for root in ('.agents', '.claude'):
            self.assertFalse((self.project / root / 'skills/one').is_symlink())
            self.assertTrue((self.project / root / 'references/guide.md').is_file())
            self.assertTrue((self.project / root / 'references/software-development-workflow/docs/workflow.md').is_file())
            self.assertTrue((self.project / root / 'agents/product-reviewer.md').is_file())
        shutil.rmtree(self.home / '.agents')
        shutil.rmtree(self.home / '.claude')
        self.call('init', '--project', str(self.project), '--offline')
        self.call('doctor', '--project', str(self.project), '--strict')
        self.assertIn('Ручные команды запуска', manual.read_text())
        for name in ('AGENTS.md', 'CLAUDE.md'):
            self.assertIn('имеют приоритет', (self.project / name).read_text())
            self.assertIn('Обязательно соблюдайте флоу', (self.project / name).read_text())

    def test_project_assets_preserve_edits_and_preflight_both_roots(self):
        args = self.prepare_project_assets()
        conflict = self.project / '.claude/skills/one/SKILL.md'
        conflict.parent.mkdir(parents=True)
        conflict.write_text('user content')
        failure = self.call(*args, '--approve', check=False)
        self.assertNotEqual(failure.returncode, 0)
        self.assertEqual(conflict.read_text(), 'user content')
        self.assertFalse((self.project / '.agents').exists())
        conflict.unlink()
        self.call(*args, '--approve')
        conflict.write_text('edited after install')
        self.assertNotEqual(self.call(*args, '--approve', check=False).returncode, 0)
        self.assertEqual(conflict.read_text(), 'edited after install')
        self.assertNotEqual(self.call('doctor', '--project', str(self.project), '--strict', check=False).returncode, 0)

    def test_project_assets_reject_destination_symlink(self):
        args = self.prepare_project_assets()
        outside = self.root / 'outside-assets'
        outside.mkdir()
        (self.project / '.claude').symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.call(*args, '--approve', check=False).returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.project / '.agents').exists())

    def test_project_init_never_installs_shared_skills(self):
        self.call('init','--project',str(self.project),'--offline')
        self.assertFalse((self.project / 'AGENT.md').exists())
        self.assertTrue((self.project/'.go-product-platform/docs/index.html').is_file())
        self.assertFalse((self.project/'.agents/skills').exists())
        self.assertFalse((self.project/'.claude/skills').exists())
        self.assertFalse((self.project/'.go-product-platform/vendor').exists())
        self.assertFalse((self.project/'.go-product-platform/skills').exists())
        self.assertTrue((self.project/'.go-product-platform/project-skills').is_dir())
        self.assertIn('project-local',(self.project/'go-product-platform.lock.json').read_text())
        self.assertEqual((self.project/'.gitignore').read_text().count('/.go-product-platform/'),1)
        self.assertEqual(subprocess.run(['git','-C',str(self.project),'check-ignore','-q','.go-product-platform/docs/index.html']).returncode,0)

    def test_global_is_once_and_visible_in_both_agent_homes(self):
        self.global_skills()
        for name in ('one','two'):
            for dir in ('.agents','.claude'):
                self.assertTrue((self.home / dir / 'skills' / name / 'SKILL.md').is_file())
        self.assertTrue((self.home / '.agents/references/guide.md').is_file())
        self.assertTrue((self.home / '.claude/references/guide.md').is_file())
        lock = json.loads((self.home/'.agents/go-product-platform/global-skills.lock.json').read_text())
        self.assertEqual(len(lock['skills']),2)
        self.global_skills()  # idempotent, uses pinned local snapshot
        self.assertEqual(len(json.loads((self.home/'.agents/go-product-platform/global-skills.lock.json').read_text())['skills']),2)

    def test_global_conflict_does_not_overwrite_user_skill(self):
        existing = self.home/'.agents/skills/one'
        existing.mkdir(parents=True)
        (existing/'SKILL.md').write_text('user own skill')
        failure = self.call('setup-global','--skills','--manifest',str(self.manifest),check=False)
        self.assertNotEqual(failure.returncode,0)
        self.assertEqual((existing/'SKILL.md').read_text(),'user own skill')

    def test_new_worktree_has_docs_and_no_local_global_links(self):
        self.global_skills()
        self.call('init','--project',str(self.project))
        subprocess.run(['git','-C',str(self.project),'config','user.email','test@example.test'],check=True)
        subprocess.run(['git','-C',str(self.project),'config','user.name','test'],check=True)
        subprocess.run(['git','-C',str(self.project),'add','.gitignore','AGENTS.md','CLAUDE.md','orca.yaml','go-product-platform.lock.json'],check=True)
        subprocess.run(['git','-C',str(self.project),'commit','-qm','scaffold'],check=True)
        worktree = self.root / 'feature'
        subprocess.run(['git','-C',str(self.project),'worktree','add','-qb','feature/1',str(worktree)],check=True)
        self.call('init','--project',str(worktree),'--offline')
        self.assertTrue((worktree/'.go-product-platform/constitution.md').exists())
        self.assertFalse((worktree/'.agents/skills').exists())
        self.assertTrue((self.home/'.agents/skills/one/SKILL.md').exists())

    def test_existing_files_preserved(self):
        (self.project/'AGENTS.md').write_text('My rules\n')
        (self.project/'orca.yaml').write_text('scripts:\n  setup: |\n    echo my command\n')
        self.call('init','--project',str(self.project))
        self.assertIn('My rules',(self.project/'AGENTS.md').read_text())
        self.assertEqual((self.project/'orca.yaml').read_text(),'scripts:\n  setup: |\n    echo my command\n')
        self.assertTrue((self.project/'.go-product-platform/orca-integration.yaml').exists())

    def test_agent_bridges_are_russian_on_init_and_refresh(self):
        self.call('init', '--project', str(self.project), '--offline')
        expected = {
            'AGENTS.md': 'software-development-workflow',
            'CLAUDE.md': 'software-development-workflow',
        }
        generated = {}
        for name, phrase in expected.items():
            generated[name] = (self.project / name).read_text('utf-8')
            self.assertIn(phrase, generated[name])
            (self.project / name).write_text(
                '# Правила команды\n\n<!-- GPP:BEGIN -->\nOld English bridge\n'
                '<!-- GPP:END -->\n\nДополнительные правила.\n', encoding='utf-8')

        self.call('init', '--project', str(self.project), '--offline')
        refreshed = {}
        for name in expected:
            refreshed[name] = (self.project / name).read_text('utf-8')
            self.assertEqual(refreshed[name], '# Правила команды\n\n' +
                             generated[name].rstrip('\n') + '\n\nДополнительные правила.\n')
        self.call('init', '--project', str(self.project), '--offline')
        for name in expected:
            self.assertEqual((self.project / name).read_text('utf-8'), refreshed[name])

    def test_v13_migrate_removes_only_old_generated_links(self):
        self.global_skills()
        local = self.project/'.go-product-platform'
        (local/'skills/graphify').mkdir(parents=True)
        (local/'skills/graphify/SKILL.md').write_text('old graphify')
        (self.project/'.agents/skills').mkdir(parents=True)
        (self.project/'.claude/skills').mkdir(parents=True)
        (self.project/'.agents/skills/graphify').symlink_to('../../.go-product-platform/skills/graphify')
        (self.project/'.claude/skills/graphify').symlink_to('../../.go-product-platform/skills/graphify')
        # User's actual project-specific skill MUST be preserved.
        (self.project/'.agents/skills/project-special').mkdir()
        (self.project/'.agents/skills/project-special/SKILL.md').write_text('specific')
        (self.project/'.gitignore').write_text('/.go-product-platform/\n/.agents/skills/graphify\n')
        (self.project/'go-product-platform.lock.json').write_text(json.dumps({'platform_version':'13.0.0','addyosmani_commit':'1234'}))
        self.call('migrate','--project',str(self.project))
        self.assertFalse((self.project/'.agents/skills/graphify').exists())
        self.assertTrue((self.project/'.agents/skills/project-special/SKILL.md').exists())
        self.assertNotIn('/.agents/skills/graphify',(self.project/'.gitignore').read_text())
        self.assertEqual(json.loads((self.project/'go-product-platform.lock.json').read_text())['platform_version'],'17.0.0')

    def test_orca_global_dry_run_and_no_project_mutation(self):
        result = self.call('orca-install','--dry-run')
        self.assertEqual(sum('npx skills add' in x for x in result.stdout.splitlines()),7)
        self.assertFalse((self.project/'.agents').exists())

    def test_graphify_global_with_mock_cli(self):
        fake = self.root/'bin'; fake.mkdir()
        executable = fake/'graphify'
        executable.write_text('#!/bin/sh\n' +
            'if [ "$1" = install ]; then\n'
            '  mkdir -p "$HOME/.agents/skills/graphify" "$HOME/.claude/skills/graphify"\n'
            '  if [ "$3" = agents ]; then echo demo > "$HOME/.agents/skills/graphify/SKILL.md"; fi\n'
            '  if [ "$3" = claude ]; then echo demo > "$HOME/.claude/skills/graphify/SKILL.md"; fi\n'
            'fi\n')
        executable.chmod(0o755)
        self.env['PATH'] = str(fake) + os.pathsep + self.env['PATH']
        self.call('setup-global','--graphify')
        self.assertTrue((self.home/'.agents/skills/graphify/SKILL.md').is_file())
        self.assertTrue((self.home/'.claude/skills/graphify/SKILL.md').is_file())
        self.assertFalse((self.project/'.agents').exists())

    def test_cli_installer(self):
        self.call('install-cli')
        self.assertTrue((self.home/'.local/bin/gpp').is_file())
        self.assertTrue((self.home/'.local/share/gpp/17.0.0/platform/docs/index.html').is_file())

    def test_cli_registers_bootstrap_with_independent_runner(self):
        checkout = self.root / 'trusted starter'
        shutil.copytree(SCRIPT.parents[1], checkout,
                        ignore=shutil.ignore_patterns('.git', 'tests', '__pycache__'))
        subprocess.run([sys.executable, str(checkout / 'installer/gpp.py'), 'install-cli'],
                       env=self.env, check=True, capture_output=True)
        shutil.rmtree(checkout)
        for agent in ('.agents', '.claude'):
            skill = self.home / agent / 'skills/go-platform-bootstrap'
            self.assertTrue((skill / 'SKILL.md').is_file())
        runner = self.home / '.agents/skills/go-platform-bootstrap/scripts/gpp.py'
        result = subprocess.run([sys.executable, str(runner), 'init', '--project',
                                 str(self.project), '--offline'], cwd=self.root,
                                env={**self.env, 'PATH': '/usr/bin:/bin'},
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.project / 'docs/engineering/workflow.md').is_file())

    def test_install_cli_preserves_conflicting_bootstrap_skill(self):
        skill = self.home / '.claude/skills/go-platform-bootstrap'
        skill.mkdir(parents=True)
        (skill / 'SKILL.md').write_text('user content')
        result = self.call('install-cli', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((skill / 'SKILL.md').read_text(), 'user content')
        self.assertFalse((self.home / '.local/bin/gpp').exists())

    def test_cli_install_is_repeatable_and_quotes_runtime_path(self):
        self.env['GPP_HOME'] = str(self.home / 'platform with $literal and spaces')
        self.call('install-cli')
        link = self.home / '.agents/skills/go-platform-bootstrap'
        first = link.resolve()
        self.call('install-cli')
        self.assertEqual(first, link.resolve())
        result = subprocess.run([str(self.home / '.local/bin/gpp'), '--help'],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_skill_runtime_follows_relocated_installation(self):
        self.call('install-cli')
        old_bundle = self.home / '.local/share/gpp'
        self.env['GPP_HOME'] = str(self.home / 'new runtime')
        self.call('install-cli')
        shutil.rmtree(old_bundle)
        runner = self.home / '.agents/skills/go-platform-bootstrap/scripts/gpp.py'
        result = subprocess.run([sys.executable, str(runner), '--help'],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_readiness_rejects_documentation_only_project(self):
        self.call('init', '--project', str(self.project), '--offline')
        self.call('doctor', '--project', str(self.project), '--strict')
        result = self.call('doctor', '--project', str(self.project), '--ready', check=False)
        self.assertNotEqual(result.returncode, 0)

    def readiness_plan(self):
        plan = json.loads(self.call('init', '--setup', '--profile', 'go-api', '--json').stdout)
        for tool in plan['tools']:
            tool['argv'] = [sys.executable, '-c', 'print("test tool")']
        for component in plan['components']:
            path = 'checks/' + component['name']
            (self.project / path).parent.mkdir(exist_ok=True)
            (self.project / path).write_text('fixture')
            component['paths'] = [path]
            component['checks'] = [{'argv': [sys.executable, '-c', 'print("verified")'], 'cwd': '.'}]
        return plan

    def test_ready_runs_checks_and_propagates_failures(self):
        self.call('init', '--project', str(self.project), '--offline')
        self.call('skills-activate', '--project', str(self.project), '--names', 'go-platform-bootstrap', '--approve')
        self.call('skills-install-global', '--names', 'go-platform-bootstrap', '--approve')
        plan = self.readiness_plan()
        path = self.project / 'go-product-platform.setup.json'
        path.write_text(json.dumps(plan))
        result = self.call('doctor', '--project', str(self.project), '--ready', check=False)
        self.assertNotEqual(result.returncode, 0)  # profile differs, required skills missing
        self.call('skills-activate', '--project', str(self.project), '--profile', 'go-api', '--approve')
        # Isolated skill fixtures avoid GitHub and real global homes.
        lock = json.loads((self.project / 'go-product-platform.lock.json').read_text())
        for name in lock['enabled_global_skills']:
            for agent in ('.agents', '.claude'):
                skill = self.project / agent / 'skills' / name
                if not skill.exists():
                    skill.mkdir(parents=True)
                    (skill / 'SKILL.md').write_text('fixture')
        import hashlib
        lock['project_assets'] = {'files': {f'skills/{name}/SKILL.md': hashlib.sha256(b'fixture').hexdigest() for name in lock['enabled_global_skills']}}
        (self.project / 'go-product-platform.lock.json').write_text(json.dumps(lock))
        self.call('doctor', '--project', str(self.project), '--ready')
        valid_tool = plan['tools'][0]['argv']
        plan['tools'][0]['argv'] = ['gpp-test-missing-executable']
        path.write_text(json.dumps(plan))
        self.assertNotEqual(self.call('doctor', '--project', str(self.project), '--ready', check=False).returncode, 0)
        plan['tools'][0]['argv'] = valid_tool
        plan['components'][0]['checks'][0]['argv'] = [sys.executable, '-c', 'raise SystemExit(7)']
        path.write_text(json.dumps(plan))
        self.assertNotEqual(self.call('doctor', '--project', str(self.project), '--ready', check=False).returncode, 0)
        plan['components'] = plan['components'][1:]
        path.write_text(json.dumps(plan))
        self.assertNotEqual(self.call('doctor', '--project', str(self.project), '--ready', check=False).returncode, 0)

    def test_setup_plan_validation_before_mutation(self):
        plan = self.readiness_plan()
        plan['components'][0]['paths'] = ['../outside']
        path = self.root / 'plan.json'
        path.write_text(json.dumps(plan))
        args = ('init', '--project', str(self.project), '--setup-plan', str(path))
        self.assertNotEqual(self.call(*args, check=False).returncode, 0)
        self.assertNotEqual(self.call(*args, '--approve', check=False).returncode, 0)
        self.assertFalse((self.project / 'go-product-platform.lock.json').exists())

    def test_offline_setup_is_rejected_without_writes(self):
        plan = self.readiness_plan()
        path = self.root / 'plan.json'
        path.write_text(json.dumps(plan))
        result = self.call('init', '--project', str(self.project), '--offline',
                           '--setup-plan', str(path), '--approve', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.project / 'go-product-platform.lock.json').exists())
        self.assertFalse((self.home / '.agents').exists())

    def test_setup_applies_commands_installs_missing_skills_and_repeats(self):
        plan = self.readiness_plan()
        plan['profile'] = 'custom'
        plan['skills'] = ['one']
        plan['setup'] = [{'argv': [sys.executable, '-c',
                           'from pathlib import Path; Path("setup-ran").write_text("done")']}]
        # Graphify's network installer is covered separately. Supply its global fixture here.
        for agent in ('.agents', '.claude'):
            skill = self.home / agent / 'skills/graphify'
            skill.mkdir(parents=True)
            (skill / 'SKILL.md').write_text('fixture')
        self.call('init', '--project', str(self.project), '--offline')
        self.call('skills-activate', '--project', str(self.project), '--names', 'graphify,go-platform-bootstrap', '--approve')
        lockpath = self.project / 'go-product-platform.lock.json'
        lock = json.loads(lockpath.read_text()); lock['enabled_global_skills'].append('one'); lockpath.write_text(json.dumps(lock))
        plan['agent_assets'] = json.loads(self.call('skills-project', '--project', str(self.project), '--manifest', str(self.manifest), '--json').stdout)
        path = self.root / 'plan.json'
        path.write_text(json.dumps(plan))
        args = ('init', '--project', str(self.project), '--setup-plan', str(path),
                '--manifest', str(self.manifest), '--approve')
        self.call(*args)
        self.assertEqual((self.project / 'setup-ran').read_text(), 'done')
        self.assertTrue((self.home / '.agents/skills/one/SKILL.md').is_file())
        self.assertTrue((self.home / '.claude/skills/one/SKILL.md').is_file())
        self.assertEqual(json.loads((self.project / 'go-product-platform.setup.json').read_text()), plan)
        workflow = self.project / 'docs/engineering/workflow.md'
        workflow.write_text('user workflow')
        self.call(*args)
        self.assertEqual(workflow.read_text(), 'user workflow')
        (self.project / 'checks/go').unlink()
        result = self.call('doctor', '--project', str(self.project), '--ready', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing/empty artifact', result.stderr)

    def test_setup_stops_on_failure_without_saving_readiness_contract(self):
        plan = self.readiness_plan()
        plan['profile'] = 'custom'
        plan['setup'] = [{'argv': [sys.executable, '-c', 'raise SystemExit(9)']},
                         {'argv': [sys.executable, '-c', 'from pathlib import Path; Path("unexpected").touch()']}]
        path = self.root / 'plan.json'
        path.write_text(json.dumps(plan))
        result = self.call('init', '--project', str(self.project), '--setup-plan',
                           str(path), '--approve', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.project / 'unexpected').exists())
        self.assertFalse((self.project / 'go-product-platform.setup.json').exists())

    def test_setup_rejects_incomplete_profiles_and_escaping_cwd(self):
        for profile in ('go-api', 'web', 'desktop', 'mobile-native', 'ai', 'custom'):
            with self.subTest(profile=profile):
                plan = json.loads(self.call('init', '--setup', '--profile', profile, '--json').stdout)
                path = self.root / 'plan.json'
                path.write_text(json.dumps(plan))
                self.assertNotEqual(self.call('init', '--project', str(self.project), '--setup-plan',
                                              str(path), '--approve', check=False).returncode, 0)
        plan = self.readiness_plan()
        plan['setup'] = [{'argv': [sys.executable, '-c', 'raise SystemExit(0)'], 'cwd': '../'}]
        path.write_text(json.dumps(plan))
        self.assertNotEqual(self.call('init', '--project', str(self.project), '--setup-plan',
                                      str(path), '--approve', check=False).returncode, 0)
        self.assertFalse((self.project / 'go-product-platform.lock.json').exists())

    def test_setup_rejects_symlink_escape_and_bad_command_schema(self):
        plan = self.readiness_plan()
        (self.project / 'outside').symlink_to(self.root, target_is_directory=True)
        path = self.root / 'plan.json'
        for command in ({'argv': 'touch unexpected'}, {'argv': []},
                        {'argv': ['true'], 'timeout': 0}, {'argv': ['true'], 'cwd': 'outside'}):
            with self.subTest(command=command):
                plan['setup'] = [command]
                path.write_text(json.dumps(plan))
                result = self.call('init', '--project', str(self.project), '--setup-plan',
                                   str(path), '--approve', check=False)
                self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.project / 'go-product-platform.lock.json').exists())


    def test_project_manager_and_active_list_default(self):
        self.call('init', '--project', str(self.project), '--offline')
        manager = self.project / '.go-product-platform/project-skills/go-project-platform-manager/SKILL.md'
        self.assertTrue(manager.is_file())
        self.assertIn('skills-inventory', manager.read_text())
        self.assertIn('go-project-platform-manager', (self.project / 'AGENTS.md').read_text())
        self.assertTrue((self.project / '.go-product-platform/active-global-skills.md').is_file())
        self.assertFalse((self.project / '.agents/skills').exists())

    def test_inventory_and_selection_require_explicit_approval(self):
        self.call('init', '--project', str(self.project))
        inventory = json.loads(self.call('skills-inventory', '--project', str(self.project), '--json',
                                         '--manifest', str(self.manifest)).stdout)
        self.assertTrue(any(x['name'] == 'one' for x in inventory['skills']))
        self.assertEqual(inventory['active_global_skills'], [])
        refusal = self.call('skills-activate', '--project', str(self.project), '--names', 'one', check=False)
        self.assertNotEqual(refusal.returncode, 0)
        self.assertEqual(json.loads((self.project / 'go-product-platform.lock.json').read_text())['enabled_global_skills'], [])
        # Curated test 'one' not in bundled manifest: test real profile instead.
        self.call('skills-activate', '--project', str(self.project), '--profile', 'go-api', '--approve')
        updated = json.loads((self.project / 'go-product-platform.lock.json').read_text())
        self.assertIn('golang-testing', updated['enabled_global_skills'])
        self.assertFalse((self.project / '.agents/skills').exists())
        self.assertIn('выбран для проекта', (self.project / '.go-product-platform/active-global-skills.md').read_text())

    def test_global_skill_installs_require_approval(self):
        refused = self.call('skills-install-global', '--names', 'one', '--manifest', str(self.manifest), check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertFalse((self.home / '.agents/skills/one/SKILL.md').exists())
        self.call('skills-install-global', '--names', 'one', '--manifest', str(self.manifest), '--approve')
        self.assertTrue((self.home / '.agents/skills/one/SKILL.md').exists())
        self.assertFalse((self.home / '.agents/skills/two/SKILL.md').exists())
        self.assertTrue((self.home / '.claude/skills/one/SKILL.md').exists())

    def test_update_check_does_not_change_and_exact_sha_update(self):
        self.global_skills()
        lock_file = self.home / '.agents/go-product-platform/global-skills.lock.json'
        original = json.loads(lock_file.read_text())['repositories']['testrepo']['commit']
        (self.repo / 'skills/one/SKILL.md').write_text('---\nname: one\ndescription: Test changed version\n---\n')
        (self.repo / 'references/guide.md').write_text('Updated shared references')
        subprocess.run(['git', '-C', str(self.repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'commit', '-qm', 'next'], check=True)
        newsha = subprocess.run(['git', '-C', str(self.repo), 'rev-parse', 'HEAD'], check=True, text=True,
                                capture_output=True).stdout.strip()
        plan_path = self.root / 'updates.json'
        status_raw = self.call('skills-check-updates', '--project', str(self.project), '--manifest', str(self.manifest),
                               '--json', '--output', str(plan_path)).stdout
        status = json.loads(status_raw)
        self.assertEqual(status['sources'][0]['status'], 'update-available')
        self.assertEqual(status['sources'][0]['latest_sha'], newsha)
        self.assertEqual(json.loads(lock_file.read_text())['repositories']['testrepo']['commit'], original)
        refused = self.call('skills-upgrade-global', '--plan', str(plan_path), '--manifest', str(self.manifest), check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.call('skills-upgrade-global', '--plan', str(plan_path), '--manifest', str(self.manifest), '--approve')
        self.assertEqual(json.loads(lock_file.read_text())['repositories']['testrepo']['commit'], newsha)
        for base in ('.agents', '.claude'):
            self.assertIn('Test changed version', (self.home / base / 'skills/one/SKILL.md').read_text())
            self.assertEqual((self.home / base / 'references/guide.md').read_text(), 'Updated shared references')
        self.assertTrue((self.home / '.agents/go-product-platform/vendor/testrepo' / original).is_dir())
        self.assertTrue((self.home / '.agents/go-product-platform/vendor/testrepo' / newsha).is_dir())

    def test_remote_changed_after_approval_is_rejected(self):
        self.global_skills()
        (self.repo / 'skills/one/SKILL.md').write_text('---\nname: one\ndescription: version B\n---\n')
        subprocess.run(['git', '-C', str(self.repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'commit', '-qm', 'B'], check=True)
        plan_path = self.root / 'outdated-plan.json'
        self.call('skills-check-updates', '--manifest', str(self.manifest), '--json', '--output', str(plan_path))
        (self.repo / 'skills/one/SKILL.md').write_text('---\nname: one\ndescription: version C\n---\n')
        subprocess.run(['git', '-C', str(self.repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'commit', '-qm', 'C'], check=True)
        result = self.call('skills-upgrade-global', '--plan', str(plan_path), '--manifest', str(self.manifest),
                           '--approve', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('upstream HEAD changed', result.stderr)
        self.assertIn('Test one', (self.home / '.agents/skills/one/SKILL.md').read_text())

    def test_graphify_is_in_every_default_profile(self):
        self.call('init', '--project', str(self.project), '--offline')
        inventory = json.loads(self.call('skills-inventory', '--project', str(self.project), '--json').stdout)
        for profile in inventory['profile_options']:
            self.call('skills-activate', '--project', str(self.project), '--profile', profile, '--approve')
            lock = json.loads((self.project / 'go-product-platform.lock.json').read_text())
            self.assertIn('graphify', lock['enabled_global_skills'], profile)
        self.assertFalse((self.home / '.agents/skills/graphify').exists())

    def test_canvas_installer_requires_approval_and_forwards_options(self):
        source = self.root / 'canvas installer'
        (source / 'canvas').mkdir(parents=True)
        (source / 'canvas/install.py').write_text('# mock official module')
        (source / 'canvas_setup.py').write_text(
            'import json, sys\nfrom pathlib import Path\n'
            'Path("canvas-args.json").write_text(json.dumps(sys.argv[1:]))\n')
        args = ('canvas-install', '--project', str(self.project), '--source', str(source))
        refused = self.call(*args, check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertFalse((self.project / 'canvas-args.json').exists())
        self.call(*args, '--approve', '--app', 'apps/front end', '--tag', 'v2.1.0')
        self.assertEqual(json.loads((self.project / 'canvas-args.json').read_text()),
                         ['--project', str(self.project.resolve()), '--app', 'apps/front end', '--tag', 'v2.1.0'])
        (source / 'canvas_setup.py').write_text('raise SystemExit(7)')
        self.assertNotEqual(self.call(*args, '--approve', check=False).returncode, 0)

    def test_wizard_installs_selected_canvas_after_confirmation(self):
        source = self.root / 'canvas'
        (source / 'canvas').mkdir(parents=True)
        (source / 'canvas/install.py').write_text('# mock')
        (source / 'canvas_setup.py').write_text(
            'from pathlib import Path\nPath("canvas-installed").touch()\n')
        for answer in ('n', 'y'):
            proc = subprocess.run([sys.executable, str(SCRIPT), 'wizard', '--project',
                                   str(self.project), '--allow-pipe'], env=self.env,
                                  text=True, capture_output=True,
                                  input=f'n\n2\n\n{source}\n{answer}\n')
            self.assertEqual(proc.returncode == 0, answer == 'n', proc.stderr)
            self.assertEqual((self.project / 'canvas-installed').exists(), answer == 'y')
            if answer == 'y':
                self.assertIn('Install selected skill', proc.stderr)

    def test_canvas_missing_source_and_offline_init(self):
        failure = self.call('canvas-install', '--project', str(self.project),
                            '--source', str(self.root / 'missing'), '--approve', check=False)
        self.assertNotEqual(failure.returncode, 0)
        self.call('init', '--project', str(self.project), '--offline')
        self.assertFalse((self.project / '.canvas').exists())
        workflow = self.project / 'docs/engineering/workflow.md'
        self.assertIn('структура документации и workflow', workflow.read_text())
        workflow.write_text('User workflow')
        self.call('init', '--project', str(self.project), '--offline')
        self.assertEqual(workflow.read_text(), 'User workflow')

    def test_wizard_cancellation_keeps_git_untouched(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), 'wizard', '--project', str(self.project),
                               '--allow-pipe'],
                              env=self.env, text=True, capture_output=True, input='n\n2\n\n\nn\n')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse((self.project / 'go-product-platform.lock.json').exists())
        self.assertFalse((self.project / 'AGENTS.md').exists())

    def test_wizard_reports_missing_assets_without_global_installation(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), 'wizard', '--project', str(self.project),
                               '--allow-pipe'],
                              env=self.env, text=True, capture_output=True, input='n\n1\n\n\ny\n')
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('Install selected skill', proc.stderr)
        lock = json.loads((self.project / 'go-product-platform.lock.json').read_text())
        self.assertEqual(lock['skills_profile'], 'go-api')
        self.assertTrue((self.project / '.go-product-platform/project-skills/go-project-platform-manager/SKILL.md').exists())
        self.assertFalse((self.home / '.agents/skills/golang-testing').exists())

    def test_explicit_migration_from_v14_preserves_selection(self):
        (self.project / 'go-product-platform.lock.json').write_text(json.dumps({
            'platform_version': '14.0.0', 'enabled_global_skills': ['protobuf'],
            'skills_profile': 'custom', 'skills_scope': 'user-global',
        }))
        self.call('migrate', '--project', str(self.project))
        lock = json.loads((self.project / 'go-product-platform.lock.json').read_text())
        self.assertEqual(lock['platform_version'], '17.0.0')
        self.assertEqual(lock['enabled_global_skills'], ['protobuf'])
        self.assertTrue((self.project / '.go-product-platform/project-skills/go-project-platform-manager/SKILL.md').exists())


    def test_bootstrap_skill_installed_and_previous_managed_version_replaced(self):
        old = self.home / '.agents/go-product-platform/builtins/14.0.0/go-platform-bootstrap'
        old.mkdir(parents=True)
        (old / 'SKILL.md').write_text('---\nname: go-platform-bootstrap\ndescription: Previous platform\n---\n')
        for agent in ('.agents', '.claude'):
            target = self.home / agent / 'skills/go-platform-bootstrap'
            target.parent.mkdir(parents=True)
            target.symlink_to(os.path.relpath(old, target.parent), target_is_directory=True)
        self.call('skills-install-global', '--names', 'go-platform-bootstrap', '--approve', '--manifest', str(self.manifest))
        for agent in ('.agents', '.claude'):
            text = (self.home / agent / 'skills/go-platform-bootstrap/SKILL.md').read_text()
            self.assertIn('v17', text.lower())
        self.assertTrue((old / 'SKILL.md').exists())

    def test_no_read_of_global_skill_homes_when_init_or_wizard_declines_check(self):
        self.call('init', '--project', str(self.project), '--offline')
        self.call('skills-activate', '--project', str(self.project), '--profile', 'desktop', '--approve')
        # Status is not probed or cached during offline worktree init/profile selection.
        self.assertIn('выбран для проекта', (self.project / '.go-product-platform/active-global-skills.md').read_text())
        self.assertNotIn('available', (self.project / '.go-product-platform/active-global-skills.md').read_text())
        self.assertFalse((self.home / '.agents').exists())


if __name__ == '__main__':
    unittest.main()
