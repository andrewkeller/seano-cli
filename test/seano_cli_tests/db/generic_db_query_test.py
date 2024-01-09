# generic_db_query_test.py
#
# Automated unit tests for the GenericSeanoDatabase class
#   - in particular, the behavior related to querying a database
from seano_cli.db.generic import GenericSeanoDatabase
import os
import shutil
import tempfile
import unittest

mkdir = os.mkdir
rmrf = shutil.rmtree


class GenericDbQueryTest(unittest.TestCase):
    maxDiff = None # Always display full diffs, even with large structures

    class TempDir(object):
        def __enter__(self):
            self.workdir = tempfile.mkdtemp(prefix='zarf_seano_generic_db_query_test_')
            return self.workdir

        def __exit__(self, exc_type, exc_val, exc_tb):
            rmrf(self.workdir)

    def run_test(self, seano_config_data=None, seano_notes_data=None, check_query=None):
        '''
        ABK: This test does not stress the config annex because, conceptually, it's just an
        annex of seano-config.yaml, and for the sake of unit tests, there's no reason to not
        just put everything inside seano-config.yaml.
        '''
        with self.TempDir() as workdir:
            config_path = os.path.join(workdir, 'seano-config.yaml')
            notes_path = os.path.join(workdir, 'v1')

            if seano_config_data is not None:
                with open(config_path, 'w') as f:
                    f.write(seano_config_data)

            mkdir(notes_path)

            for note_id, note_data in (seano_notes_data or {}).items():
                note_path = os.path.join(notes_path, note_id + '.yaml')
                with open(note_path, 'w') as f:
                    f.write(note_data)

            db = GenericSeanoDatabase(path=workdir)

            if isinstance(check_query, type) and issubclass(check_query, Exception):
                try:
                    query = db.query()
                except check_query as e:
                    return # Good (expected) exception
                self.fail('While opening a GenericSeanoDatabase: expected %s but found %s' % (
                          check_query.__name__, db))
            query = db.query()

            if check_query is not None:
                check_query(query)

    def testEmpty(self):
        config = '''---
'''
        expected = {
            'current_version': 'HEAD',
            'releases': [
                {
                    'name': 'HEAD',
                    'before': [],
                    'after': [],
                    'notes': [],
                },
            ],
        }
        self.run_test(seano_config_data=config, check_query=lambda found: self.assertEqual(expected, found))

    def testProductionReleaseAncestry(self):
        config = '''---
current_version: 1.2.3

releases:
- name:  1.2.3
  after: 1.2.2
- name:  1.2.2
  after: 1.2.1
- name:  1.2.1
'''
        expected = {
            'current_version': '1.2.3',
            'releases': [
                {
                    'name': '1.2.3',
                    'before': [],
                    'after': [{'name': '1.2.2'}],
                    'notes': [],
                },
                {
                    'name': '1.2.2',
                    'before': [{'name': '1.2.3'}],
                    'after': [{'name': '1.2.1'}],
                    'notes': [],
                },
                {
                    'name': '1.2.1',
                    'before': [{'name': '1.2.2'}],
                    'after': [],
                    'notes': [],
                },
            ],
        }
        self.run_test(seano_config_data=config, check_query=lambda found: self.assertEqual(expected, found))

    def testPrereleaseAncestry(self):
        config = '''---
current_version: 1.2.4a5

parent_versions:
- 1.2.3

releases:
- name:  1.2.3
  after: 1.2.2
- name:  1.2.2
  after: 1.2.1
- name:  1.2.1
'''
        expected = {
            'current_version': '1.2.4a5',
            'parent_versions': [{'name': '1.2.3'}],
            'releases': [
                {
                    'name': '1.2.4a5',
                    'before': [],
                    'after': [{'name': '1.2.3'}],
                    'notes': [],
                },
                {
                    'name': '1.2.3',
                    'before': [{'name': '1.2.4a5'}],
                    'after': [{'name': '1.2.2'}],
                    'notes': [],
                },
                {
                    'name': '1.2.2',
                    'before': [{'name': '1.2.3'}],
                    'after': [{'name': '1.2.1'}],
                    'notes': [],
                },
                {
                    'name': '1.2.1',
                    'before': [{'name': '1.2.2'}],
                    'after': [],
                    'notes': [],
                },
            ],
        }
        self.run_test(seano_config_data=config, check_query=lambda found: self.assertEqual(expected, found))

    def testDoublyLinkingReleases(self):
        config = '''---
current_version: 1.2.3

releases:
- name:  1.2.3
  after: 1.2.2
- name:  1.2.2
- name:  1.2.1
  before: 1.2.2
'''
        expected = {
            'current_version': '1.2.3',
            'releases': [
                {
                    'name': '1.2.3',
                    'before': [],
                    'after': [{'name': '1.2.2'}],
                    'notes': [],
                },
                {
                    'name': '1.2.2',
                    'before': [{'name': '1.2.3'}],
                    'after': [{'name': '1.2.1'}],
                    'notes': [],
                },
                {
                    'name': '1.2.1',
                    'before': [{'name': '1.2.2'}],
                    'after': [],
                    'notes': [],
                },
            ],
        }
        self.run_test(seano_config_data=config, check_query=lambda found: self.assertEqual(expected, found))

    def testLoadingNotes(self):
        config = '''---
current_version: 1.2.3

releases:
- name:  1.2.3
  after: 1.2.2
- name:  1.2.2
  after: 1.2.1
- name:  1.2.1
'''
        note123 = '''---
releases:
- 1.2.3
foo: bar
'''
        note456 = '''---
fish: cat
'''
        note789 = '''---
releases: 1.2.1
bird: dog
'''
        ghost_note = '''---
releases: 1.2.4
x-seano-is-ghost: true
'''
        expected = {
            'current_version': '1.2.3',
            'releases': [
                {
                    'name': '1.2.3',
                    'before': [],
                    'after': [{'name': '1.2.2'}],
                    'notes': [
                        {
                            'id': '123',
                            'releases': ['1.2.3'],
                            'foo': 'bar',
                        },
                        {
                            'id': '456',
                            'releases': ['1.2.3'],
                            'fish': 'cat',
                        },
                    ],
                },
                {
                    'name': '1.2.2',
                    'before': [{'name': '1.2.3'}],
                    'after': [{'name': '1.2.1'}],
                    'notes': [],
                },
                {
                    'name': '1.2.1',
                    'before': [{'name': '1.2.2'}],
                    'after': [],
                    'notes': [
                        {
                            'id': '789',
                            'releases': ['1.2.1'],
                            'bird': 'dog',
                        },
                    ],
                },
            ],
        }
        self.run_test(seano_config_data=config,
                      seano_notes_data={
                          '123': note123,
                          '456': note456,
                          '789': note789,
                          'gho': ghost_note, # should not impact anything
                      },
                      check_query=lambda found: self.assertEqual(expected, found))

    def testNoteSortOrder(self):
        config = '''---
current_version: 1.2.3
'''
        note123 = '''---
relative-sort-string: "345" # ties are broken using the note ID
foo: bar
'''
        note345 = '''---
relative-sort-string: "345" # ties are broken using the note ID
fish: cat
'''
        note567 = '''---
bird: dog
'''
        note789 = '''---
relative-sort-string: "456"
panda: turkey
'''
        expected = {
            'current_version': '1.2.3',
            'releases': [
                {
                    'name': '1.2.3',
                    'before': [],
                    'after': [],
                    'notes': [
                        {
                            'id': '123',
                            'releases': ['1.2.3'],
                            'relative-sort-string': '345',
                            'foo': 'bar',
                        },
                        {
                            'id': '345',
                            'releases': ['1.2.3'],
                            'relative-sort-string': '345',
                            'fish': 'cat',
                        },
                        {
                            'id': '789',
                            'releases': ['1.2.3'],
                            'relative-sort-string': '456',
                            'panda': 'turkey',
                        },
                        {
                            'id': '567',
                            'releases': ['1.2.3'],
                            'bird': 'dog',
                        },
                    ],
                },
            ],
        }
        self.run_test(seano_config_data=config,
                      seano_notes_data={
                          '123': note123,
                          '345': note345,
                          '567': note567,
                          '789': note789,
                      },
                      check_query=lambda found: self.assertEqual(expected, found))

    def testNonlinearReleaseAncestry(self):
        r'''
        In this test, we will manufacture a release ancestry that looks like the graph
        below, and then show that ``seano`` correctly sorts the releases during a query.

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
        config = '''---
current_version: "2.0"

releases:
- name: "2.0"
  after:
  - "1.0"
  - "1.3"
- name: "1.3"
  after:
  - "1.2"
  - "1.2b5"
- name: "1.2b5"
  after:
  - "1.2b1"
- name: "1.2"
  after:
  - "1.1"
  - "1.2b1"
- name: "1.2b1"
  after:
  - "1.1"
- name: "1.1"
  after:
  - "1.1b2"
- name: "1.1b2"
  after:
  - "1.0"
- name: "1.0"
'''
        expected = {
            'current_version': '2.0',
            'releases': [
                {
                    'name': '2.0',
                    'before': [],
                    'after': [{'name': '1.0'}, {'name': '1.3'}],
                    'notes': [],
                },
                {
                    'name': '1.3',
                    'before': [{'name': '2.0'}],
                    'after': [{'name': '1.2'}, {'name': '1.2b5'}],
                    'notes': [],
                },
                {
                    'name': '1.2b5',
                    'before': [{'name': '1.3'}],
                    'after': [{'name': '1.2b1'}],
                    'notes': [],
                },
                {
                    'name': '1.2',
                    'before': [{'name': '1.3'}],
                    'after': [{'name': '1.1'}, {'name': '1.2b1'}],
                    'notes': [],
                },
                {
                    'name': '1.2b1',
                    'before': [{'name': '1.2'}, {'name': '1.2b5'}],
                    'after': [{'name': '1.1'}],
                    'notes': [],
                },
                {
                    'name': '1.1',
                    'before': [{'name': '1.2'}, {'name': '1.2b1'}],
                    'after': [{'name': '1.1b2'}],
                    'notes': [],
                },
                {
                    'name': '1.1b2',
                    'before': [{'name': '1.1'}],
                    'after': [{'name': '1.0'}],
                    'notes': [],
                },
                {
                    'name': '1.0',
                    'before': [{'name': '1.1b2'}, {'name': '2.0'}],
                    'after': [],
                    'notes': [],
                },
            ],
        }
        self.run_test(seano_config_data=config, check_query=lambda found: self.assertEqual(expected, found))


if __name__ == '__main__':
    unittest.main()
