# new_and_edit_test.py
#
# Automated tests for the `new` and `edit` subcommands, focusing on --print-paths behavior.
from seano_cli_tests.util import rmrf
import os
import subprocess
import sys
import tempfile
import unittest


def invokeSeano(args, cwd, env=None):
    '''
    Invokes seano with the given arguments in the given cwd, capturing stdout separately.
    Returns (returncode, stdout_text).
    '''
    p = subprocess.Popen(
        [sys.executable, '-m', 'seano_cli.cli'] + args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    stdout, stderr = p.communicate()

    for line in stderr.decode('utf-8').splitlines():
        sys.stderr.write('TEST OUTPUT PLEASE DISREGARD    %s\n' % (line,))

    return p.returncode, stdout.decode('utf-8')


class NewAndEditTest(unittest.TestCase):
    maxDiff = None

    class TempDir(object):
        def __enter__(self):
            self.workdir = tempfile.mkdtemp(prefix='zarf_seano_new_and_edit_test_')
            return self.workdir

        def __exit__(self, exc_type, exc_val, exc_tb):
            rmrf(self.workdir)

    def _init_db(self, workdir):
        rc, _ = invokeSeano(['init'], cwd=workdir)
        self.assertEqual(0, rc, 'seano init failed')

    def _init_git(self, workdir):
        env = dict(os.environ)
        env.update({'GIT_AUTHOR_NAME': 'Test', 'GIT_AUTHOR_EMAIL': 'test@example.com',
                    'GIT_COMMITTER_NAME': 'Test', 'GIT_COMMITTER_EMAIL': 'test@example.com'})
        subprocess.check_call(['git', 'init'], cwd=workdir, env=env)
        subprocess.check_call(['git', 'add', '.'], cwd=workdir, env=env)
        subprocess.check_call(['git', 'commit', '-m', 'init'], cwd=workdir, env=env)

    def testNewPrintPaths(self):
        with self.TempDir() as workdir:
            self._init_db(workdir)
            rc, stdout = invokeSeano(['new', '--print-paths'], cwd=workdir)
            self.assertEqual(0, rc)
            lines = stdout.splitlines()
            self.assertEqual(1, len(lines), 'Expected exactly one path on stdout, got: %r' % stdout)
            path = lines[0]
            self.assertTrue(path.endswith('.yaml'), 'Expected a .yaml path, got: %r' % path)
            self.assertTrue(os.path.isfile(path), 'Path does not exist on disk: %r' % path)

    def testNewDefaultBehaviorDoesNotPrint(self):
        with self.TempDir() as workdir:
            self._init_db(workdir)
            env = dict(os.environ)
            env['EDITOR'] = 'true'
            rc, stdout = invokeSeano(['new'], cwd=workdir, env=env)
            self.assertEqual(0, rc)
            self.assertEqual('', stdout, 'Expected no stdout when --print-paths is absent')

    def testEditPrintPaths(self):
        with self.TempDir() as workdir:
            self._init_db(workdir)
            self._init_git(workdir)

            rc, stdout = invokeSeano(['new', '--print-paths'], cwd=workdir)
            self.assertEqual(0, rc)
            created_path = stdout.strip()
            self.assertTrue(created_path, 'seano new --print-paths produced no output')

            rc, stdout = invokeSeano(['edit', '--print-paths'], cwd=workdir)
            self.assertEqual(0, rc)
            edited_paths = stdout.splitlines()
            self.assertIn(created_path, edited_paths,
                          'Expected %r in edit --print-paths output, got: %r' % (created_path, stdout))


if __name__ == '__main__':
    unittest.main()
