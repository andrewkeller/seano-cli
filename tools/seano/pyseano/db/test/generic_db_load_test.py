# generic_db_load_test.py
#
# Automated unit tests for the GenericSeanoDatabase class
#   - in particular, the behavior related to loading a database
from ..generic import GenericSeanoDatabase
from ...utils import SeanoFatalError
import os
import shutil
import tempfile
import unittest

rmrf = shutil.rmtree


class GenericDbLoadTest(unittest.TestCase):
    class TempDir(object):
        def __enter__(self):
            self.workdir = tempfile.mkdtemp(prefix='zarf_seano_generic_db_load_test_')
            return self.workdir

        def __exit__(self, exc_type, exc_val, exc_tb):
            rmrf(self.workdir)

    def run_test(self, seano_config_annex_data=None, seano_config_data=None, check_test=None):
        with self.TempDir() as workdir:
            config_path = os.path.join(workdir, 'seano-config.yaml')
            config_annex_path = os.path.join(workdir, 'seano-config-annex.yaml')

            if seano_config_data is not None:
                with open(config_path, 'w') as f:
                    f.write(seano_config_data)

            if seano_config_annex_data is not None:
                with open(config_annex_path, 'w') as f:
                    f.write(seano_config_annex_data)

            if isinstance(check_test, type) and issubclass(check_test, Exception):
                try:
                    db = GenericSeanoDatabase(path=workdir, config_annex_path=config_annex_path)
                except check_test as e:
                    return # Good (expected) exception
                self.fail('While opening a GenericSeanoDatabase: expected %s but found %s' % (
                          check_test.__name__, db))
            db = GenericSeanoDatabase(path=workdir, config_annex_path=config_annex_path)

            if check_test is not None:
                check_test(db=db)

    def testMissingConfigFile(self):
        self.run_test(check_test=SeanoFatalError)

    def testEmptyConfigFile(self):
        self.run_test(seano_config_data='')

    def testEmptyConfigAnnexFile(self):
        self.run_test(seano_config_annex_data='', seano_config_data='')

    def testConfigIsLoaded(self):
        self.run_test(seano_config_annex_data='{"example_string2":"foo"}',
                      seano_config_data='---\nexample_string: bar\n',
                      check_test=lambda db: self.assertEqual('bar', db.config['example_string']))

    def testConfigAnnexIsLoaded(self):
        self.run_test(seano_config_annex_data='{"example_string":"foo"}',
                      seano_config_data='---\nexample_string2: bar\n',
                      check_test=lambda db: self.assertEqual('foo', db.config['example_string']))

    def testConfigOverridesConfigAnnex(self):
        self.run_test(seano_config_annex_data='{"example_string":"foo"}',
                      seano_config_data='---\nexample_string: bar\n',
                      check_test=lambda db: self.assertEqual('bar', db.config['example_string']))

    def testLoadReleaseAncestry_official(self):
        sample_config = '''---
# This is the official, 100% correct way that release ancestry is defined in seano.
# Both before and after are lists of dictionaries of ancestry info.  Ancestry info
# requires just one key (name), but other optional keys exist.
parent_versions:
- name: 1.2.4
releases:
- name: 1.2.3
  before:
  - name: 1.2.4
  after:
  - name: 1.2.2
'''
        expected_config = {
            'current_version': 'HEAD',
            'parent_versions': [{'name': '1.2.4'}],
            'releases': [
                {'name': '1.2.3', 'before': [{'name': '1.2.4'}], 'after': [{'name': '1.2.2'}]},
            ],
        }
        self.run_test(seano_config_data=sample_config,
                      check_test=lambda db: self.assertEqual(expected_config, db.config))

    def testLoadReleaseAncestry_legacy_beforeAfterListsOfStrings(self):
        sample_config = '''---
# This is an old schema that seano used to use to define a release ancestry.  When this
# schema is used, seano will automatically translate it to the modern schema on-the-fly.
# The schema is fully converted by the time the seano database object's constructor has
# returned, resulting in any downstream operations only needing to understand the modern
# schema.
parent_versions:
- 1.2.4
releases:
- name: 1.2.3
  before:
  - 1.2.4
  after:
  - 1.2.2
'''
        expected_config = {
            'current_version': 'HEAD',
            'parent_versions': ['1.2.4'],
            'releases': [
                {'name': '1.2.3', 'before': ['1.2.4'], 'after': ['1.2.2']},
            ],
        }
        self.run_test(seano_config_data=sample_config,
                      check_test=lambda db: self.assertEqual(expected_config, db.config))

    def testLoadReleaseAncestry_legacy_beforeAfterStrings(self):
        sample_config = '''---
# This is an old schema that seano used to use to define a release ancestry.  When this
# schema is used, seano will automatically translate it to the modern schema on-the-fly.
# The schema is fully converted by the time the seano database object's constructor has
# returned, resulting in any downstream operations only needing to understand the modern
# schema.
parent_versions: 1.2.4
releases:
- name: 1.2.3
  before: 1.2.4
  after: 1.2.2
'''
        expected_config = {
            'current_version': 'HEAD',
            'parent_versions': '1.2.4',
            'releases': [
                {'name': '1.2.3', 'before': '1.2.4', 'after': '1.2.2'},
            ],
        }
        self.run_test(seano_config_data=sample_config,
                      check_test=lambda db: self.assertEqual(expected_config, db.config))

    def testLoadReleaseAncestry_legacy_beforeAfterMissing(self):
        sample_config = '''---
# There are some completely normal situations where you don't want to specify any ancestry
# on a release.  seano shouldn't crash in this case.
releases:
- name: 1.2.3
'''
        expected_config = {
            'current_version': 'HEAD',
            'releases': [
                {'name': '1.2.3'},
            ],
        }
        self.run_test(seano_config_data=sample_config,
                      check_test=lambda db: self.assertEqual(expected_config, db.config))


if __name__ == '__main__':
    unittest.main()
