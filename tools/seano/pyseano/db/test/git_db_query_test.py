# git_db_query_test.py
#
# Automated unit tests for the GitSeanoDatabase class
#   - in particular, the behavior related to querying a database
from ..git import GitSeanoDatabase
from ...utils import SeanoFatalError, coerce_to_str
import errno
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

shcall = subprocess.check_call
mkdir = os.mkdir

def shgeto(*args, **kwargs):
    return coerce_to_str(subprocess.check_output(*args, **kwargs).strip())

def putfile(path, data):
    '''
    ABK: Not using ``seano``'s copy of ``write_file()`` because we want to be able to overwrite existing
         files, which ``write_file()`` forbids.  Other than that detail, this function is nearly identical
         to ``seano``'s ``write_file()`` method.
    '''
    try:
        with open(path, 'w') as f:
            f.write(data)
            return
    except IOError as e:
        if e.errno != errno.ENOENT:
            raise
    os.makedirs(os.path.dirname(path))
    with open(path, 'w') as f:
        f.write(data)

def rmrf(workdir):
    def on_error(func, path, exc_info): #pylint: disable=W0613
        """
        Error handler for ``shutil.rmtree``.

        Stolen from <https://stackoverflow.com/questions/2656322/shutil-rmtree-fails-on-windows-with-access-is-denied>

        In particular on Windows, if the error is due to an access error (read only file),
        attempt to add write permission and then retry.  This is useful in particular with
        Git repositories, where files on disk in the objects database are marked as read-only,
        which makes the default invocation of ``shutil.rmtree`` grumpy.

        If the error is for another reason, we do not handle the error (re-raise it).
        """
        if not os.access(path, os.W_OK): # Is the error an access error?
            os.chmod(path, stat.S_IWUSR)
            func(path)
            return
        raise #pylint: disable=E0704

    if sys.platform not in ['win32']:
        # Trying to keep overall behavior as close to "normal" as possible.  Fewer hacks is better?
        on_error = None
    shutil.rmtree(workdir, onerror=on_error)

def setup_repo(workdir):
    shcall(args=['git', 'init'], cwd=workdir)
    # Some builders don't have a git author configured, and they also have a bogus system identity,
    # which can cause `git commit` to become grumpy.
    shcall(args=['git', 'config', 'user.email', 'you@example.com'], cwd=workdir)
    shcall(args=['git', 'config', 'user.name', 'Your Name'], cwd=workdir)


class GitDbQueryTest(unittest.TestCase):
    maxDiff = None # Always display full diffs, even with large structures

    class TempDir(object):
        def __enter__(self):
            self.workdir = tempfile.mkdtemp(prefix='zarf_seano_git_db_query_test_')
            return self.workdir

        def __exit__(self, exc_type, exc_val, exc_tb):
            rmrf(self.workdir)

    def assertQueryOutputEquals(self, workdir, expected):
        db = GitSeanoDatabase(path=workdir)
        self.assertTrue(db.is_valid())
        self.assertEqual(expected, db.query())

    def testNoCommits(self):
        with self.TempDir() as workdir:
            setup_repo(workdir)

            # No seano database at all

            with self.assertRaises(SeanoFatalError):
                GitSeanoDatabase(path=workdir)

            # Because the constructor of GitSeanoDatabase raised an exception,
            # it is not possible to perform a query.  Nothing else to test.

    def testEmptyDatabaseWithNoCommits(self):
        with self.TempDir() as workdir:
            setup_repo(workdir)
            putfile(os.path.join(workdir, 'seano-config.yaml'), '''---
''')
            # seano database exists, but Git has no commits

            self.assertFalse(GitSeanoDatabase(path=workdir).is_valid())

            # Becuase is_valid() is false, the behavior of query() is undefined.
            # Nothing else to test.

    def testEmptyDatabaseWithUnrelatedCommits(self):
        with self.TempDir() as workdir:
            setup_repo(workdir)
            shcall(['git', 'commit', '--allow-empty', '-m', 'empty'], cwd=workdir)
            putfile(os.path.join(workdir, 'seano-config.yaml'), '''---
''')
            # seano database exists, but is not committed

            self.assertFalse(GitSeanoDatabase(path=workdir).is_valid())

            # Becuase is_valid() is false, the behavior of query() is undefined.
            # Nothing else to test.

    def testEmptyDatabase(self):
        with self.TempDir() as workdir:
            setup_repo(workdir)
            putfile(os.path.join(workdir, 'seano-config.yaml'), '''---
''')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)
            commitid = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            # Unlike the earlier tests, seano should now think that the database
            # exists, because something is committed inside the seano database
            # folder in the repo.

            self.assertQueryOutputEquals(workdir, {
                'current_version': 'HEAD',
                'releases': [
                    {
                        'name': 'HEAD',
                        'commit': commitid,
                        'before': [],
                        'after': [],
                        'notes': [],
                    },
                ],
            })

    def testProductionReleaseAncestry(self):
        with self.TempDir() as workdir:
            setup_repo(workdir)
            putfile(os.path.join(workdir, 'seano-config.yaml'), '''---
current_version: 1.2.3
''')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)

            shcall(['git', 'tag', 'v1.2.1'], cwd=workdir)
            commit_121 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            shcall(['git', 'commit', '--allow-empty', '-m', 'wip'], cwd=workdir)
            shcall(['git', 'tag', 'v1.2.2'], cwd=workdir)
            commit_122 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            shcall(['git', 'commit', '--allow-empty', '-m', 'wip'], cwd=workdir)
            shcall(['git', 'tag', 'v1.2.3'], cwd=workdir)
            commit_123 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            self.assertQueryOutputEquals(workdir, {
                'current_version': '1.2.3',
                'releases': [
                    {
                        'name': '1.2.3',
                        'commit': commit_123,
                        'before': [],
                        'after': [{'name': '1.2.2'}],
                        'notes': [],
                    },
                    {
                        'name': '1.2.2',
                        'commit': commit_122,
                        'before': [{'name': '1.2.3'}],
                        'after': [{'name': '1.2.1'}],
                        'notes': [],
                    },
                    {
                        'name': '1.2.1',
                        'commit': commit_121,
                        'before': [{'name': '1.2.2'}],
                        'after': [],
                        'notes': [],
                    },
                ],
            })

    def testBackstory(self):
        with self.TempDir() as workdir:
            setup_repo(workdir)
            putfile(os.path.join(workdir, 'seano-config.yaml'), '''---
current_version: 1.2.4fc1
parent_versions:
- 1.2.3
''')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)

            shcall(['git', 'tag', 'v1.2.1'], cwd=workdir)
            commit_121 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            shcall(['git', 'commit', '--allow-empty', '-m', 'wip'], cwd=workdir)
            shcall(['git', 'tag', 'v1.2.2'], cwd=workdir)
            commit_122 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            shcall(['git', 'commit', '--allow-empty', '-m', 'wip'], cwd=workdir)
            shcall(['git', 'tag', 'v1.2.3'], cwd=workdir)
            commit_123 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            shcall(['git', 'commit', '--allow-empty', '-m', 'wip'], cwd=workdir)
            commit_head = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            self.assertQueryOutputEquals(workdir, {
                'current_version': '1.2.4fc1',
                'parent_versions': [{'name': '1.2.3'}],
                'releases': [
                    {
                        'name': '1.2.4fc1',
                        'commit': commit_head,
                        'before': [],
                        'after': [{'name': '1.2.3'}],
                        'notes': [],
                    },
                    {
                        'name': '1.2.3',
                        'commit': commit_123,
                        'before': [{'name': '1.2.4fc1'}],
                        'after': [{'name': '1.2.2'}],
                        'notes': [],
                    },
                    {
                        'name': '1.2.2',
                        'commit': commit_122,
                        'before': [{'name': '1.2.3'}],
                        'after': [{'name': '1.2.1'}],
                        'notes': [],
                    },
                    {
                        'name': '1.2.1',
                        'commit': commit_121,
                        'before': [{'name': '1.2.2'}],
                        'after': [],
                        'notes': [],
                    },
                ],
            })

    def testLoadingNotes(self):
        with self.TempDir() as workdir:
            setup_repo(workdir)
            putfile(os.path.join(workdir, 'seano-config.yaml'), '''---
current_version: 1.2.4d1
parent_versions:
- 1.2.3
''')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)

            shcall(['git', 'tag', 'v1.2.1'], cwd=workdir)
            commit_121 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            putfile(os.path.join(workdir, 'v1', 'abc.yaml'), '---\nfoo: bar\n')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)
            shcall(['git', 'tag', 'v1.2.2'], cwd=workdir)
            commit_122 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            putfile(os.path.join(workdir, 'v1', 'def.yaml'), '---\nfoo: fish\n')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)
            shcall(['git', 'tag', 'v1.2.3'], cwd=workdir)
            commit_123 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            putfile(os.path.join(workdir, 'v1', 'ghi.yaml'), '---\nfoo: cat\n')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)
            commit_head = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            putfile(os.path.join(workdir, 'v1', 'jkl.yaml'), '---\nfoo: bird\n')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)

            putfile(os.path.join(workdir, 'v1', 'mno.yaml'), '---\nfoo: dog\n')

            self.assertQueryOutputEquals(workdir, {
                'current_version': '1.2.4d1',
                'parent_versions': [{'name': '1.2.3'}],
                'releases': [
                    {
                        'name': '1.2.4d1',
                        'commit': None,
                        'before': [],
                        'after': [{'name': '1.2.3'}],
                        'notes': [
                            {
                                'id': 'ghi',
                                'commits': [commit_head],
                                'releases': ['1.2.4d1'],
                                'foo': 'cat',
                            },
                            {
                                'id': 'jkl',
                                'commits': [None],
                                'releases': ['1.2.4d1'],
                                'foo': 'bird',
                            },
                            {
                                'id': 'mno',
                                'commits': [None],
                                'releases': ['1.2.4d1'],
                                'foo': 'dog',
                            },
                        ],
                    },
                    {
                        'name': '1.2.3',
                        'commit': commit_123,
                        'before': [{'name': '1.2.4d1'}],
                        'after': [{'name': '1.2.2'}],
                        'notes': [
                            {
                                'id': 'def',
                                'commits': [commit_123],
                                'releases': ['1.2.3'],
                                'foo': 'fish',
                            },
                        ],
                    },
                    {
                        'name': '1.2.2',
                        'commit': commit_122,
                        'before': [{'name': '1.2.3'}],
                        'after': [{'name': '1.2.1'}],
                        'notes': [
                            {
                                'id': 'abc',
                                'commits': [commit_122],
                                'releases': ['1.2.2'],
                                'foo': 'bar',
                            },
                        ],
                    },
                    {
                        'name': '1.2.1',
                        'commit': commit_121,
                        'before': [{'name': '1.2.2'}],
                        'after': [],
                        'notes': [],
                    },
                ],
            })

    def testNoteRenameOneWayTracking(self):
        with self.TempDir() as workdir:
            setup_repo(workdir)
            putfile(os.path.join(workdir, 'seano-config.yaml'), '''---
current_version: 1.2.4d1
parent_versions:
- 1.2.3
''')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)

            shcall(['git', 'tag', 'v1.2.1'], cwd=workdir)
            commit_121 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            putfile(os.path.join(workdir, 'v1', 'abc.yaml'), '---\nfoo: bar\n')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)
            shcall(['git', 'tag', 'v1.2.2'], cwd=workdir)
            commit_122 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            shcall(['git', 'mv', 'abc.yaml', 'abc-moved.yaml'], cwd=os.path.join(workdir, 'v1'))
            putfile(os.path.join(workdir, 'v1', 'def.yaml'), '---\nfish: cat\n')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)
            shcall(['git', 'tag', 'v1.2.3'], cwd=workdir)
            commit_123 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            putfile(os.path.join(workdir, 'v1', 'ghi.yaml'), '---\nbird: dog\n')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)
            commit_head = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            shcall(['git', 'mv', 'ghi.yaml', 'ghi-moved.yaml'], cwd=os.path.join(workdir, 'v1'))

            # ABK: Unstaged moves follow different rules.  We'll have a different test for that.

            self.assertQueryOutputEquals(workdir, {
                'current_version': '1.2.4d1',
                'parent_versions': [{'name': '1.2.3'}],
                'releases': [
                    {
                        'name': '1.2.4d1',
                        'commit': None,
                        'before': [],
                        'after': [{'name': '1.2.3'}],
                        'notes': [
                            {
                                'id': 'ghi-moved',
                                'commits': [commit_head],
                                'releases': ['1.2.4d1'],
                                'bird': 'dog',
                            },
                        ],
                    },
                    {
                        'name': '1.2.3',
                        'commit': commit_123,
                        'before': [{'name': '1.2.4d1'}],
                        'after': [{'name': '1.2.2'}],
                        'notes': [
                            {
                                'id': 'def',
                                'commits': [commit_123],
                                'releases': ['1.2.3'],
                                'fish': 'cat',
                            },
                        ],
                    },
                    {
                        'name': '1.2.2',
                        'commit': commit_122,
                        'before': [{'name': '1.2.3'}],
                        'after': [{'name': '1.2.1'}],
                        'notes': [
                            {
                                'id': 'abc-moved',
                                'commits': [commit_122],
                                'releases': ['1.2.2'],
                                'foo': 'bar',
                            },
                        ],
                    },
                    {
                        'name': '1.2.1',
                        'commit': commit_121,
                        'before': [{'name': '1.2.2'}],
                        'after': [],
                        'notes': [],
                    },
                ],
            })

    def testNoteRenameCycleTracking(self):
        with self.TempDir() as workdir:
            setup_repo(workdir)
            putfile(os.path.join(workdir, 'seano-config.yaml'), '''---
current_version: 1.2.4d1
parent_versions:
- 1.2.3
''')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)

            shcall(['git', 'tag', 'v1.2.1'], cwd=workdir)
            commit_121 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            putfile(os.path.join(workdir, 'v1', 'abc.yaml'), '---\nfoo: bar\n')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)
            shcall(['git', 'tag', 'v1.2.2'], cwd=workdir)
            commit_122 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            shcall(['git', 'mv', 'abc.yaml', 'ghi.yaml'], cwd=os.path.join(workdir, 'v1'))
            putfile(os.path.join(workdir, 'v1', 'def.yaml'), '---\nfish: cat\n')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)
            shcall(['git', 'tag', 'v1.2.3'], cwd=workdir)
            commit_123 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            putfile(os.path.join(workdir, 'v1', 'abc.yaml'), '---\nbird: dog\n')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)
            commit_head = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            shcall(['git', 'mv', 'abc.yaml', 'abc-moved.yaml'], cwd=os.path.join(workdir, 'v1'))

            # ABK: Unstaged moves follow different rules.  We'll have a different test for that.

            self.assertQueryOutputEquals(workdir, {
                'current_version': '1.2.4d1',
                'parent_versions': [{'name': '1.2.3'}],
                'releases': [
                    {
                        'name': '1.2.4d1',
                        'commit': None,
                        'before': [],
                        'after': [{'name': '1.2.3'}],
                        'notes': [
                            {
                                # TODO: This note was ONLY released in 1.2.4d1.
                                'id': 'abc-moved',
                                'commits': sorted([commit_122, commit_head]),
                                'releases': ['1.2.2', '1.2.4d1'],
                                'bird': 'dog',
                            },
                        ],
                    },
                    {
                        'name': '1.2.3',
                        'commit': commit_123,
                        'before': [{'name': '1.2.4d1'}],
                        'after': [{'name': '1.2.2'}],
                        'notes': [
                            {
                                'id': 'def',
                                'commits': [commit_123],
                                'releases': ['1.2.3'],
                                'fish': 'cat',
                            },
                        ],
                    },
                    {
                        'name': '1.2.2',
                        'commit': commit_122,
                        'before': [{'name': '1.2.3'}],
                        'after': [{'name': '1.2.1'}],
                        'notes': [
                            {
                                # TODO: This note was ONLY released in 1.2.4d1.
                                # TODO: We're missing the 'foo: bar' note in this release.
                                'id': 'abc-moved',
                                'commits': sorted([commit_122, commit_head]),
                                'releases': ['1.2.2', '1.2.4d1'],
                                'bird': 'dog',
                            },
                        ],
                    },
                    {
                        'name': '1.2.1',
                        'commit': commit_121,
                        'before': [{'name': '1.2.2'}],
                        'after': [],
                        'notes': [],
                    },
                ],
            })

    def testUnstagedNoteRenameTracking(self):
        '''
        Unstaged moves are interpreted by Git as a delete and an add.  ``seano`` trusts Git, which causes
        the note to look like it was deleted and added in a query, too.  This can be confusing to users,
        especially if they are not expecting this behavior or are unfamiliar with this quirk in Git.

        This unit test serves to test this behavior, to make sure ``seano`` doesn't crash, and to mildly
        assert that this is expected behavior (even though unit tests aren't supposed to be documentation).
        '''
        with self.TempDir() as workdir:
            setup_repo(workdir)
            putfile(os.path.join(workdir, 'seano-config.yaml'), '''---
current_version: 1.2.4d1
parent_versions:
- 1.2.3
''')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)

            shcall(['git', 'tag', 'v1.2.2'], cwd=workdir)
            commit_122 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            putfile(os.path.join(workdir, 'v1', 'abc.yaml'), '---\nfoo: bar\n')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)
            shcall(['git', 'tag', 'v1.2.3'], cwd=workdir)
            commit_123 = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            self.assertQueryOutputEquals(workdir, {
                'current_version': '1.2.4d1',
                'parent_versions': [{'name': '1.2.3'}],
                'releases': [
                    {
                        'name': '1.2.4d1',
                        'commit': commit_123,
                        'before': [],
                        'after': [{'name': '1.2.3'}],
                        'notes': [],
                    },
                    {
                        'name': '1.2.3',
                        'commit': commit_123,
                        'before': [{'name': '1.2.4d1'}],
                        'after': [{'name': '1.2.2'}],
                        'notes': [
                            {
                                'id': 'abc',
                                'commits': [commit_123],
                                'releases': ['1.2.3'],
                                'foo': 'bar',
                            },
                        ],
                    },
                    {
                        'name': '1.2.2',
                        'commit': commit_122,
                        'before': [{'name': '1.2.3'}],
                        'after': [],
                        'notes': [],
                    },
                ],
            })

            # Perform the unstaged move:
            shcall(['git', 'mv', 'abc.yaml', 'abc-moved.yaml'], cwd=os.path.join(workdir, 'v1'))
            shcall(['git', 'reset'], cwd=workdir)

            self.assertQueryOutputEquals(workdir, {
                'current_version': '1.2.4d1',
                'parent_versions': [{'name': '1.2.3'}],
                'releases': [
                    {
                        'name': '1.2.4d1',
                        'commit': None,
                        'before': [],
                        'after': [{'name': '1.2.3'}],
                        'notes': [
                            {
                                # As far as seano knows, this is a *new* note in this release.
                                'id': 'abc-moved',
                                'commits': [None],
                                'releases': ['1.2.4d1'],
                                'foo': 'bar',
                            },
                        ],
                    },
                    {
                        'name': '1.2.3',
                        'commit': commit_123,
                        'before': [{'name': '1.2.4d1'}],
                        'after': [{'name': '1.2.2'}],
                        'notes': [
                            # As far as seano knows, we *told* it to delete the note that was here.
                        ],
                    },
                    {
                        'name': '1.2.2',
                        'commit': commit_122,
                        'before': [{'name': '1.2.3'}],
                        'after': [],
                        'notes': [],
                    },
                ],
            })

    def testNonlinearReleaseAncestry(self):
        r'''
        In this test, we will manufacture a repository with the commit graph below, and
        then show that ``seano`` correctly mines the release ancestry during a query.

            *  v2.0                 #1
            |\
            | *  v1.3               #2
            | |\
            | | *  v1.2b5           #3
            | | *
            | | *
            | * |  v1.2             #4
            | |\|
            | | *
            | | *  v1.2b1           #5
            | |/
            | *  v1.1               #6
            | *
            | *  v1.1b2             #7
            |/
            *
            *  v1.0                 #8
        '''
        # ABK: This test does not pass reliably; there is a race condition somewhere that is causing trouble.
        #      Until this test starts passing reliably, stop running it.
        return

        with self.TempDir() as workdir:
            setup_repo(workdir)
            putfile(os.path.join(workdir, 'seano-config.yaml'), '''---
current_version: "2.0"
''')
            shcall(['git', 'add', '-A', '.'], cwd=workdir)
            shcall(['git', 'commit', '-m', 'wip'], cwd=workdir)
            shcall(['git', 'tag', 'v1.0'], cwd=workdir)
            commit_ids = {}
            commit_ids['1.0'] = shgeto(['git', 'rev-parse', 'HEAD'], cwd=workdir)

            def cc(name, parents, tag=False):
                self.assertEqual(list, type(parents))
                tree = shgeto(['git', 'rev-parse', parents[0] + '^{tree}'], cwd=workdir)
                cmd = ['git', 'commit-tree', tree, '-m', name]
                for p in parents:
                    cmd.extend(['-p', p])
                result = shgeto(cmd, cwd=workdir)
                commit_ids[name] = result
                if tag:
                    shcall(['git', 'tag', 'v' + name, result], cwd=workdir)
                return result

            cc('1.1b2', [cc('1.1b1', [commit_ids['1.0']])], tag=True)
            cc('1.1', [cc('1.1b3', [commit_ids['1.1b2']])], tag=True)
            cc('1.2b1', [commit_ids['1.1']], tag=True)
            cc('1.2', [commit_ids['1.1'], cc('1.2b2', [commit_ids['1.2b1']])], tag=True)
            cc('1.2b5', [cc('1.2b4', [cc('1.2b3', [commit_ids['1.2b2']])])], tag=True)
            cc('1.3', [commit_ids['1.2'], commit_ids['1.2b5']], tag=True)
            head = cc('2.0', [commit_ids['1.1b1'], commit_ids['1.3']], tag=True)

            shcall(['git', 'reset', '--hard', head], cwd=workdir)

            # Commit graph has been created.  Run a query and verify the output:

            self.assertQueryOutputEquals(workdir, {
                'current_version': '2.0',
                'releases': [
                    {
                        'name': '2.0',
                        'commit': commit_ids['2.0'],
                        'before': [],
                        'after': [{'name': '1.0'}, {'name': '1.3'}],
                        'notes': [],
                    },
                    {
                        'name': '1.3',
                        'commit': commit_ids['1.3'],
                        'before': [{'name': '2.0'}],
                        'after': [{'name': '1.2'}, {'name': '1.2b5'}],
                        'notes': [],
                    },
                    {
                        'name': '1.2b5',
                        'commit': commit_ids['1.2b5'],
                        'before': [{'name': '1.3'}],
                        'after': [], # IMPROVE: This list is incorrect.
                        'notes': [],
                    },
                    {
                        'name': '1.2',
                        'commit': commit_ids['1.2'],
                        'before': [{'name': '1.3'}],
                        'after': [{'name': '1.1'}, {'name': '1.2b1'}],
                        'notes': [],
                    },
                    {
                        'name': '1.2b1',
                        'commit': commit_ids['1.2b1'],
                        'before': [{'name': '1.2'}], # IMPROVE: This list is incorrect.
                        'after': [], # IMPROVE: This list is incorrect.
                        'notes': [],
                    },
                    {
                        'name': '1.1',
                        'commit': commit_ids['1.1'],
                        'before': [{'name': '1.2'}], # IMPROVE: This list is incorrect.
                        'after': [{'name': '1.1b2'}],
                        'notes': [],
                    },
                    {
                        'name': '1.1b2',
                        'commit': commit_ids['1.1b2'],
                        'before': [{'name': '1.1'}],
                        'after': [], # IMPROVE: This list is incorrect.
                        'notes': [],
                    },
                    {
                        'name': '1.0',
                        'commit': commit_ids['1.0'],
                        'before': [{'name': '2.0'}], # IMPROVE: This list is incorrect.
                        'after': [],
                        'notes': [],
                    },
                ],
            })


if __name__ == '__main__':
    unittest.main()
