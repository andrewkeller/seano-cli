# generic_db_import_test.py
#
# Automated unit tests for the GenericSeanoDatabase class
#   - in particular, the behavior related to importing notes from an extern database
from ..generic import GenericSeanoDatabase
from ...utils import write_existing_file
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

mkdir = os.mkdir
rmrf = shutil.rmtree

def ensure_native_newlines(txt):
    return os.linesep.join(txt.splitlines()) + os.linesep


def fw(path_components, data):
    '''
    Quick shorthand for writing a file to disk and creating the folders
    necessary to get there.
    '''
    write_existing_file(os.path.join(*path_components), data)


def cat_tree(path):
    '''
    Returns a human-readable string describing an entire folder tree on disk.
    Allows us to "assert" that a folder contains the correct data.
    '''
    result = []
    for root, directories, filenames in os.walk(path):
        for f in filenames:
            filepath = os.path.join(root, f)
            # ABK: Deliberately circumventing Python's "Universal Newline" logic
            with open(filepath, 'rb') as stream:
                data = stream.read().decode('utf-8')
            result.append((os.path.relpath(filepath, path).replace('\\', '/'), data))
    result.sort()
    return os.linesep.join(['%s:%s%s' % (p, os.linesep, d) for p, d in result])


def invokeSeano(args, cwd):
    '''
    Invokes seano with the given arguments in the given cwd.

    Exists only to edit stdout as it is seen.  We don't want the output of this
    unit test to be confused with output from the project's proper invocations
    of seano.

    Considered just swallowing stdout, but we would like to see it to make sure
    it looks right.
    '''
    p = subprocess.Popen(['python', os.path.abspath('seano')] + args,
                         cwd=cwd,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output, _ = p.communicate()

    for line in output.decode('utf-8').splitlines():
        sys.stderr.write('TEST OUTPUT PLEASE DISREGARD    %s\n' % (line,))

    return p.returncode


class GenericDbImportTest(unittest.TestCase):
    maxDiff = None # Always display full diffs, even with large structures

    class TempDir(object):
        def __enter__(self):
            self.workdir = tempfile.mkdtemp(prefix='zarf_seano_generic_db_import_test_')
            return self.workdir

        def __exit__(self, exc_type, exc_val, exc_tb):
            rmrf(self.workdir)

    def testExternNotesNotImported(self):
        with self.TempDir() as workdir:

            srcdbp = os.path.join(workdir, 'src')
            dstdbp = os.path.join(workdir, 'dst')

            fw([srcdbp, '.seano'], 'seano-db: .\n')
            fw([srcdbp, 'seano-config.yaml'], '---\n')
            fw([srcdbp, 'v1', 'abc.extern-foo.yaml'], '---\nkey: value1\n')
            fw([srcdbp, 'v1', 'def.extern-foo.yaml'], '---\nkey: value2\n')

            fw([dstdbp, '.seano'], 'seano-db: .\n')
            fw([dstdbp, 'seano-config.yaml'], '---\n')
            fw([dstdbp, 'v1', 'ghi.yaml'], '---\nkey: value3\n')
            fw([dstdbp, 'v1', 'jkl.yaml'], '---\nkey: value4\n')

            self.assertEqual(0, invokeSeano(args=['import', 's:../src'], cwd=dstdbp))

            self.assertEqual(ensure_native_newlines('''.seano:
seano-db: .

seano-config.yaml:
---

v1/ghi.yaml:
---
key: value3

v1/jkl.yaml:
---
key: value4
'''), cat_tree(dstdbp))

    def testImportAllFirstTime(self):
        with self.TempDir() as workdir:

            srcdbp = os.path.join(workdir, 'src')
            dstdbp = os.path.join(workdir, 'dst')

            fw([srcdbp, '.seano'], 'seano-db: .\n')
            fw([srcdbp, 'seano-config.yaml'], '---\n')
            fw([srcdbp, 'v1', 'abc.yaml'], '---\nkey: value1\n')
            fw([srcdbp, 'v1', 'def.yaml'], '---\nkey: value2\n')

            fw([dstdbp, '.seano'], 'seano-db: .\n')
            fw([dstdbp, 'seano-config.yaml'], '---\n')
            fw([dstdbp, 'v1', 'ghi.yaml'], '---\nkey: value3\n')
            fw([dstdbp, 'v1', 'jkl.yaml'], '---\nkey: value4\n')

            self.assertEqual(0, invokeSeano(args=['import', 's:../src'], cwd=dstdbp))

            self.assertEqual(ensure_native_newlines('''.seano:
seano-db: .

seano-config.yaml:
---

v1/ab/c.extern-s.yaml:
---
x-seano-relpath-to-original: ../src/v1/abc.yaml
x-seano-sha1-of-original: f1d608f9ca51263d82e3cc492bad44c513db3369

######## NOTICE ########
# This note is a *copy* of a note from an external database.
# You probably want to edit the original rather than this
# copy, so that other projects inherit your change.
---
key: value1

v1/de/f.extern-s.yaml:
---
x-seano-relpath-to-original: ../src/v1/def.yaml
x-seano-sha1-of-original: 02413f5b4ac871271f76276858c8a5b10edbf8a9

######## NOTICE ########
# This note is a *copy* of a note from an external database.
# You probably want to edit the original rather than this
# copy, so that other projects inherit your change.
---
key: value2

v1/ghi.yaml:
---
key: value3

v1/jkl.yaml:
---
key: value4
'''), cat_tree(dstdbp))

            # And for good measure, also test incremental imports:

            fw([dstdbp, 'v1', 'ab', 'c.extern-s.yaml'], '''---
x-seano-relpath-to-original: ../src/v1/abc.yaml
x-seano-sha1-of-original: f1d608f9ca51263d82e3cc492bad44c513db3369

ha-ha: I can actually put anything here because the hash didn't change
''')

            fw([srcdbp, 'v1', 'def.yaml'], '''---
# This note actually did change, and should sync
''')

            self.assertEqual(0, invokeSeano(args=['import', 's:../src'], cwd=dstdbp))

            self.assertEqual(ensure_native_newlines('''.seano:
seano-db: .

seano-config.yaml:
---

v1/ab/c.extern-s.yaml:
---
x-seano-relpath-to-original: ../src/v1/abc.yaml
x-seano-sha1-of-original: f1d608f9ca51263d82e3cc492bad44c513db3369

ha-ha: I can actually put anything here because the hash didn't change

v1/de/f.extern-s.yaml:
---
x-seano-relpath-to-original: ../src/v1/def.yaml
x-seano-sha1-of-original: 8e8987ffdeb83e2e0a97b8682f7b95948bc06209

######## NOTICE ########
# This note is a *copy* of a note from an external database.
# You probably want to edit the original rather than this
# copy, so that other projects inherit your change.
---
# This note actually did change, and should sync

v1/ghi.yaml:
---
key: value3

v1/jkl.yaml:
---
key: value4
'''), cat_tree(dstdbp))


if __name__ == '__main__':
    unittest.main()
