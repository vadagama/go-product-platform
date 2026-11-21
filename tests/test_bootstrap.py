"""Offline regression tests. They never fetch GitHub or modify actual user HOME."""
from __future__ import annotations

import json
import os
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
        subprocess.run(['git','init','-q',str(self.repo)],check=True)
        subprocess.run(['git','-C',str(self.repo),'config','user.email','test@example.test'],check=True)
        subprocess.run(['git','-C',str(self.repo),'config','user.name','test'],check=True)
        subprocess.run(['git','-C',str(self.repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.repo),'commit','-qm','first'],check=True)
        self.manifest = self.root / 'global-skills.json'
        self.manifest.write_text(json.dumps({'manifest_version':'15.0.0','sources':[
            {'key':'testrepo','repo':str(self.repo), 'skills':{'one':'skills/one','two':'skills/two'},'references':'references'}
        ]}))

    def call(self, *args, check=True):
        return subprocess.run([sys.executable,str(SCRIPT),*args],env=self.env,check=check,text=True,capture_output=True)

    def global_skills(self):
        self.call('setup-global','--skills','--manifest',str(self.manifest))

    def test_project_init_never_installs_shared_skills(self):
        self.call('init','--project',str(self.project),'--offline')
        self.assertTrue((self.project/'.go-product-platform/handbook/index.html').is_file())
        self.assertFalse((self.project/'.agents/skills').exists())
        self.assertFalse((self.project/'.claude/skills').exists())
        self.assertFalse((self.project/'.go-product-platform/vendor').exists())
        self.assertFalse((self.project/'.go-product-platform/skills').exists())
        self.assertTrue((self.project/'.go-product-platform/project-skills').is_dir())
        self.assertIn('user-global',(self.project/'go-product-platform.lock.json').read_text())
        self.assertEqual((self.project/'.gitignore').read_text().count('/.go-product-platform/'),1)
        self.assertEqual(subprocess.run(['git','-C',str(self.project),'check-ignore','-q','.go-product-platform/handbook/index.html']).returncode,0)

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
        self.assertEqual(json.loads((self.project/'go-product-platform.lock.json').read_text())['platform_version'],'15.0.0')

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
        self.assertTrue((self.home/'.local/share/gpp/15.0.0/platform/handbook/index.html').is_file())


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

    def test_wizard_cancellation_keeps_git_untouched(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), 'wizard', '--project', str(self.project),
                               '--allow-pipe'],
                              env=self.env, text=True, capture_output=True, input='n\n2\n\nn\n')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse((self.project / 'go-product-platform.lock.json').exists())
        self.assertFalse((self.project / 'AGENTS.md').exists())

    def test_wizard_can_activate_without_global_installation(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), 'wizard', '--project', str(self.project),
                               '--allow-pipe'],
                              env=self.env, text=True, capture_output=True, input='n\n1\n\ny\n')
        self.assertEqual(proc.returncode, 0, proc.stderr)
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
        self.assertEqual(lock['platform_version'], '15.0.0')
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
            self.assertIn('v15', text.lower())
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
