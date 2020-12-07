# generic_db_backstory_test.py
#
# Automated unit tests for the GenericSeanoDatabase class
#   - in particular, the behavior related to processing backstories
from ..generic import GenericSeanoDatabase
import os
import shutil
import tempfile
import unittest

mkdir = os.mkdir
rmrf = shutil.rmtree


class GenericDbBackstoryTest(unittest.TestCase):
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


    # ABK: No "test empty", because other tests already do that.


    def testAutoWrapSingleRelease(self):
        config = '''---
current_version: 1.2.3

releases:
- name:  1.2.3
  after: 1.2.2
- name:  1.2.2
  auto-wrap-in-backstory: true
  after: 1.2.1
- name:  1.2.1
'''
        notes = {
            '123': '---\nreleases: 1.2.3\n',
            '456': '---\nreleases: 1.2.2\n',
            '789': '---\nreleases: 1.2.1\n',
        }
        expected = {
            'current_version': '1.2.3',
            'releases': [
                {
                    'name': '1.2.3',
                    'before': [],
                    'after': [{'name': '1.2.1'}, {'name': '1.2.2', 'is-backstory': True}],
                    'notes': [
                        {
                            'id': '123',
                            'releases': ['1.2.3'],
                        },
                        {
                            'id': '456',
                            'releases': ['1.2.2'],
                            'is-copied-from-backstory': True,
                        },
                    ],
                },
                {
                    'name': '1.2.2',
                    'auto-wrap-in-backstory': True,
                    'before': [{'name': '1.2.3'}],
                    'after': [{'name': '1.2.1'}],
                    'notes': [
                        {
                            'id': '456',
                            'releases': ['1.2.2'],
                        },
                    ],
                },
                {
                    'name': '1.2.1',
                    'before': [{'name': '1.2.2'}, {'name': '1.2.3'}],
                    'after': [],
                    'notes': [
                        {
                            'id': '789',
                            'releases': ['1.2.1'],
                        },
                    ],
                },
            ],
        }
        self.run_test(seano_config_data=config, seano_notes_data=notes,
                      check_query=lambda found: self.assertEqual(expected, found))

    def testAutoWrapMultipleReleases(self):
        config = '''---
current_version: "five"

releases:
- name: five
  after: four
- name: four
  auto-wrap-in-backstory: true
  after: three
- name: three
  auto-wrap-in-backstory: true
  after: two
- name: two
  auto-wrap-in-backstory: true
  after: one
- name: one
'''
        notes = {
            'five_note': '---\nreleases: five\n',
            'four_note': '---\nreleases: four\n',
            'three_note': '---\nreleases: three\n',
            'two_note': '---\nreleases: two\n',
            'one_note': '---\nreleases: one\n',
        }
        expected = {
            'current_version': 'five',
            'releases': [
                {
                    'name': 'five',
                    'before': [],
                    'after': [{'name': 'four', 'is-backstory': True}, {'name': 'one'}],
                    'notes': [
                        {
                            'id': 'five_note',
                            'releases': ['five'],
                        },
                        {
                            'id': 'four_note',
                            'is-copied-from-backstory': True,
                            'releases': ['four'],
                        },
                        {
                            'id': 'three_note',
                            'is-copied-from-backstory': True,
                            'releases': ['three'],
                        },
                        {
                            'id': 'two_note',
                            'is-copied-from-backstory': True,
                            'releases': ['two'],
                        },
                    ],
                },
                {
                    'name': 'four',
                    'auto-wrap-in-backstory': True,
                    'before': [{'name': 'five'}],
                    'after': [{'name': 'one'}, {'name': 'three', 'is-backstory': True}],
                    'notes': [
                        {
                            'id': 'four_note',
                            'releases': ['four'],
                        },
                        {
                            'id': 'three_note',
                            'is-copied-from-backstory': True,
                            'releases': ['three'],
                        },
                        {
                            'id': 'two_note',
                            'is-copied-from-backstory': True,
                            'releases': ['two'],
                        },
                    ],
                },
                {
                    'name': 'three',
                    'auto-wrap-in-backstory': True,
                    'before': [{'name': 'four'}],
                    'after': [{'name': 'one'}, {'name': 'two', 'is-backstory': True}],
                    'notes': [
                        {
                            'id': 'three_note',
                            'releases': ['three'],
                        },
                        {
                            'id': 'two_note',
                            'is-copied-from-backstory': True,
                            'releases': ['two'],
                        },
                    ],
                },
                {
                    'name': 'two',
                    'auto-wrap-in-backstory': True,
                    'before': [{'name': 'three'}],
                    'after': [{'name': 'one'}],
                    'notes': [
                        {
                            'id': 'two_note',
                            'releases': ['two'],
                        },
                    ],
                },
                {
                    'name': 'one',
                    'before': [{'name': 'five'}, {'name': 'four'}, {'name': 'three'}, {'name': 'two'}],
                    'after': [],
                    'notes': [
                        {
                            'id': 'one_note',
                            'releases': ['one'],
                        },
                    ],
                },
            ],
        }
        self.run_test(seano_config_data=config, seano_notes_data=notes,
                      check_query=lambda found: self.assertEqual(expected, found))

    def testAutoWrapExistingBackstoryHead(self):
        config = r'''---
current_version: "five"
                                #   Manually typed graph        What seano should generate
releases:
- name: five                    #   *  five                     *  five
  after:                        #   |\                          |\
  - name: four                  #   | |                         | |
    is-backstory: true          #   | |- is-backstory: true     | |- is-backstory: true
  - name: one                   #   | |                         | |
- name: four                    #   | *  four (auto-wrap)       | *  four
  auto-wrap-in-backstory: true  #   | |                         | |\
  after: three                  #   | |                         | | |- is-backstory: true
- name: three                   #   | *  three (auto-wrap)      | | *  three
  auto-wrap-in-backstory: true  #   | |                         | | |
  after: two                    #   | |                         | |/
- name: two                     #   | *  two                    | *  two
  after: one                    #   |/                          |/
- name: one                     #   *  one                      *  one
                                #
                                #   Notice how release "four" is NOT wrapped in a backstory,
                                #   despite explicitly asking for it; this is because five's
                                #   link to four is already a backstory, and wrapping four in
                                #   a new backstory would cause graph corruption.  This outcome
                                #   is definitely not what the user asked for, but it's the
                                #   lesser of multiple evils.
'''
        notes = {
            'five_note': '---\nreleases: five\n',
            'four_note': '---\nreleases: four\n',
            'three_note': '---\nreleases: three\n',
            'two_note': '---\nreleases: two\n',
            'one_note': '---\nreleases: one\n',
        }
        expected = {
            'current_version': 'five',
            'releases': [
                {
                    'name': 'five',
                    'before': [],
                    'after': [{'name': 'four', 'is-backstory': True}, {'name': 'one'}],
                    'notes': [
                        {
                            'id': 'five_note',
                            'releases': ['five'],
                        },
                        {
                            'id': 'four_note',
                            'is-copied-from-backstory': True,
                            'releases': ['four'],
                        },
                        {
                            'id': 'three_note',
                            'is-copied-from-backstory': True,
                            'releases': ['three'],
                        },
                        {
                            'id': 'two_note',
                            'is-copied-from-backstory': True,
                            'releases': ['two'],
                        },
                    ],
                },
                {
                    'name': 'four',
                    'auto-wrap-in-backstory': True,
                    'before': [{'name': 'five'}],
                    'after': [{'name': 'three', 'is-backstory': True}, {'name': 'two'}],
                    'notes': [
                        {
                            'id': 'four_note',
                            'releases': ['four'],
                        },
                        {
                            'id': 'three_note',
                            'is-copied-from-backstory': True,
                            'releases': ['three'],
                        },
                    ],
                },
                {
                    'name': 'three',
                    'auto-wrap-in-backstory': True,
                    'before': [{'name': 'four'}],
                    'after': [{'name': 'two'}],
                    'notes': [
                        {
                            'id': 'three_note',
                            'releases': ['three'],
                        },
                    ],
                },
                {
                    'name': 'two',
                    'before': [{'name': 'four'}, {'name': 'three'}],
                    'after': [{'name': 'one'}],
                    'notes': [
                        {
                            'id': 'two_note',
                            'releases': ['two'],
                        },
                    ],
                },
                {
                    'name': 'one',
                    'before': [{'name': 'five'}, {'name': 'two'}],
                    'after': [],
                    'notes': [
                        {
                            'id': 'one_note',
                            'releases': ['one'],
                        },
                    ],
                },
            ],
        }
        self.run_test(seano_config_data=config, seano_notes_data=notes,
                      check_query=lambda found: self.assertEqual(expected, found))


if __name__ == '__main__':
    unittest.main()
