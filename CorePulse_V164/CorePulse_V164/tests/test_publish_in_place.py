"""Git real en repositorios temporales; TODOS los push se interceptan sin red."""
import ast
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from core import developer_publisher as publisher


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='corepulse-publisher-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root/'clon con nombre cualquiera'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'CorePulse Test')
        self.git('config', 'user.email', 'test@example.invalid')
        for name in publisher.PROTECTED_REPO_DIRS:
            (self.repo/name).mkdir()
            (self.repo/name/'keep.txt').write_text(name)
        self.old = self.repo/'CorePulse_V136'
        self.old.mkdir()
        (self.old/'main.py').write_text('old')
        self.git('add', '.')
        self.git('commit', '-m', 'base')
        self.base = self.git('rev-parse', 'HEAD')
        self.git('switch', '-c', 'maxi/corepulse-v128')
        self.git('remote', 'add', 'origin', 'https://example.invalid/team/project.git')
        self.git('update-ref', 'refs/remotes/origin/maxi/corepulse-v128', self.base)
        self.source = self.repo/'v161'
        (self.source/'core').mkdir(parents=True)
        (self.source/'main.py').write_text('current')
        (self.source/'core/version.py').write_text('VERSION="161"')
        (self.source/'archivo español.txt').write_text('utf8')
        self.addCleanup(patch.stopall)
        patch.object(publisher, 'source_root', lambda: self.source).start()
        patch.object(publisher, 'data_path', lambda *parts: self.root/'appdata'/Path(*parts)).start()
        self.real_git = publisher._run_git
        self.pushes = []
        self.fail_push = self.fail_commit = False
        def intercepted(repo, *args, **kwargs):
            if 'push' in args:
                self.pushes.append(args)
                if self.fail_push:
                    raise publisher.PublishError('simulated push rejected')
                self.git('update-ref', 'refs/remotes/origin/maxi/corepulse-v128', self.git('rev-parse', 'HEAD'))
                return subprocess.CompletedProcess(args, 0, 'simulated push OK', '')
            if args and args[0] == 'commit' and self.fail_commit:
                raise publisher.PublishError('simulated commit rejected')
            return self.real_git(repo, *args, **kwargs)
        patch.object(publisher, '_run_git', intercepted).start()

    def git(self, *args):
        proc = subprocess.run(['git', '-C', str(self.repo), *args], text=True, encoding='utf-8', capture_output=True,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if proc.returncode:
            raise AssertionError(proc.stderr)
        return proc.stdout.strip()

    def inspect(self):
        return publisher.inspect_publish_context(self.repo)

    def publish(self):
        ctx = self.inspect()
        return publisher.publish_current_version(self.repo, 'publish test', expected_context=ctx)

    def assert_phases(self):
        for name in publisher.PROTECTED_REPO_DIRS:
            self.assertEqual((self.repo/name/'keep.txt').read_text(), name)
            self.assertEqual(self.git('show', 'HEAD:'+name+'/keep.txt'), name)

    def test_detects_running_folder_and_explicit_push_destination(self):
        ctx = self.inspect()
        self.assertTrue(ctx['can_publish'], ctx['blockers'])
        self.assertEqual(ctx['publish_folder'], 'v161')
        self.assertIn('v161/archivo español.txt', ctx['planned_files'])
        result = self.publish()
        self.assertTrue(result['ok'])
        self.assertEqual(result['publish_folder'], 'v161')
        self.assertFalse((self.repo/'CorePulse_V161').exists())
        self.assertEqual(self.git('show', 'HEAD:v161/main.py'), 'current')
        self.assertEqual(self.git('diff', '--cached', '--name-only'), '')
        self.assertIn('refs/heads/maxi/corepulse-v128:refs/heads/maxi/corepulse-v128', self.pushes[0])
        self.assertEqual(result['release_assets'], {})
        self.assert_phases()

    def test_missing_old_version_does_not_block(self):
        shutil.rmtree(self.old)
        self.assertTrue(self.inspect()['can_publish'])
        self.publish()
        self.assertNotIn('CorePulse_V136', self.git('ls-tree', '-d', '--name-only', 'HEAD'))
        self.assertFalse(self.old.exists())
        self.assert_phases()

    def test_dirty_and_staged_old_content_is_preserved(self):
        (self.old/'main.py').write_text('staged-only work')
        self.git('add', 'CorePulse_V136/main.py')
        (self.old/'main.py').write_text('working-tree work')
        (self.old/'extra.txt').write_text('local untracked')
        result = self.publish()
        self.assertEqual((self.old/'main.py').read_text(), 'working-tree work')
        self.assertEqual((self.old/'extra.txt').read_text(), 'local untracked')
        backup = Path(result['staged_backup'])
        self.assertIn('staged-only work', (backup/'old-versions-staged.patch').read_text(encoding='utf-8'))
        self.assertTrue((backup/'index.before').exists())
        self.assert_phases()

    def test_staged_unrelated_or_phase_blocks_without_touching_index(self):
        for name in ('outside.txt', 'FASE 1/keep.txt'):
            with self.subTest(name=name):
                (self.repo/name).write_text('foreign staged')
                self.git('add', '--', name)
                before = (self.repo/'.git/index').read_bytes()
                self.assertFalse(self.inspect()['can_publish'])
                with self.assertRaises(publisher.PublishError): self.publish()
                self.assertEqual((self.repo/'.git/index').read_bytes(), before)
                self.git('restore', '--staged', '--', name)
        self.assertFalse(self.pushes)

    def test_unstaged_foreign_changes_remain_uncommitted(self):
        (self.repo/'FASE 2/keep.txt').write_text('local phase work')
        (self.repo/'personal.txt').write_text('unrelated')
        self.publish()
        self.assertEqual((self.repo/'FASE 2/keep.txt').read_text(), 'local phase work')
        self.assertEqual(self.git('show', 'HEAD:FASE 2/keep.txt'), 'FASE 2')
        self.assertIn('personal.txt', self.git('ls-files', '--others', '--exclude-standard'))

    def test_commit_failure_restores_exact_user_index_and_keeps_files(self):
        self.git('add', '--', 'v161/main.py')
        before = (self.repo/'.git/index').read_bytes()
        self.fail_commit = True
        with self.assertRaises(publisher.PublishError): self.publish()
        self.assertEqual((self.repo/'.git/index').read_bytes(), before)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)
        self.assertTrue(self.old.exists())
        self.assertFalse((self.repo/'.git/index.lock').exists())
        self.assertFalse(self.pushes)

    def test_failed_push_can_retry_without_duplicate_commit(self):
        self.fail_push = True
        with self.assertRaisesRegex(publisher.PublishError, 'permanece local'): self.publish()
        commit = self.git('rev-parse', 'HEAD')
        self.assertNotEqual(commit, self.base)
        self.fail_push = False
        self.publish()
        self.assertEqual(self.git('rev-parse', 'HEAD'), commit)
        self.assertEqual(len(self.pushes), 2)

    def test_review_cannot_publish_to_changed_branch_or_remote(self):
        ctx = self.inspect()
        self.git('remote', 'set-url', 'origin', 'https://example.invalid/other.git')
        with self.assertRaisesRegex(publisher.PublishError, 'cambió'):
            publisher.publish_current_version(self.repo, 'message', expected_context=ctx)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)
        self.assertFalse(self.pushes)

    def test_protected_branches_and_missing_phase_block(self):
        for branch in ('main', 'master', 'trunk'):
            self.git('checkout', '-B', branch)
            self.assertFalse(self.inspect()['can_publish'])
        self.git('checkout', 'maxi/corepulse-v128')
        (self.repo/'FASE 3').rename(self.repo/'phase saved')
        self.assertFalse(self.inspect()['can_publish'])
        self.assertFalse(self.pushes)

    def test_v_number_old_names_removed_only_from_index(self):
        old = self.repo/'V155'
        old.mkdir(); (old/'work.txt').write_text('old work')
        self.git('add', '--', 'V155'); self.git('commit', '-m', 'old version')
        self.publish()
        self.assertEqual((old/'work.txt').read_text(), 'old work')
        self.assertNotIn('V155', self.git('ls-tree', '-d', '--name-only', 'HEAD'))

    def test_pending_foreign_commit_blocks_push(self):
        (self.repo/'FASE 1/keep.txt').write_text('committed foreign')
        self.git('add', '--', 'FASE 1'); self.git('commit', '-m', 'foreign')
        self.assertFalse(self.inspect()['can_publish'])
        self.assertFalse(self.pushes)

    def test_existing_index_lock_is_not_removed(self):
        lock = self.repo/'.git/index.lock'; lock.write_text('owned by another process')
        with self.assertRaises(publisher.PublishError): self.publish()
        self.assertEqual(lock.read_text(), 'owned by another process')
        self.assertFalse(self.pushes)

    def test_selection_does_not_silently_choose_neighbor_clone(self):
        folder = self.root/'not a repository'; folder.mkdir()
        self.assertFalse(publisher.inspect_publish_context(folder)['can_publish'])


if __name__ == '__main__':
    unittest.main()
