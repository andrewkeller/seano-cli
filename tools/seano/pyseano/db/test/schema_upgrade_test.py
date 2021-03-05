# schema_upgrade_test.py
#
# Automated unit tests for the schema upgrading logic in seano
from ..schema_upgrade import *
from ...utils import SeanoFatalError
import os
import unittest
import yaml


class HlistRst2RstConverterTest(unittest.TestCase):
    def testNull(self):
        with self.assertRaises(SeanoFatalError):
            convert_hlist_rst_to_rst(None)

    def testStr(self):
        self.assertEqual('', convert_hlist_rst_to_rst(''))
        self.assertEqual('foo', convert_hlist_rst_to_rst('foo'))

    def testHList(self):
        self.assertEqual('', convert_hlist_rst_to_rst([]))
        self.assertEqual('', convert_hlist_rst_to_rst([{}]))
        self.assertEqual('foo', convert_hlist_rst_to_rst(['foo']))
        self.assertEqual('foo', convert_hlist_rst_to_rst([{'foo': None}]))
        self.assertEqual('bar\n\nfoo', convert_hlist_rst_to_rst(['bar', {'foo': None}]))
        self.assertEqual('foo\n\n* bar', convert_hlist_rst_to_rst([{'foo': 'bar'}]))

        hlist = yaml.safe_load('''---
- one
- two:
  - three
  - four:
    - five
    - six:
      - seven:
        - eight
  - nine
  - ten
- eleven:
  - twelve: # deliberate syntax error
- thirteen
- fourteen
''')

        expected = '''
one

two

* three
* four

  * five
  * six

    * seven

      * eight

* nine
* ten

eleven

* twelve

thirteen

fourteen
'''

        self.assertEqual(expected.strip().splitlines(), convert_hlist_rst_to_rst(hlist).splitlines())


class SchemaUpgradeTest(unittest.TestCase):
    def testNotesHaveHlistsMigrated(self):
        # Unknown keys pass through:
        self.assertEqual(42, upgrade_note_schema('trouble', 42))
        # Data already formatted as loc-rst:
        self.assertEqual({'en-US': 'foo'}, upgrade_note_schema('sample-loc-rst', {'en-US': 'foo'}))
        # Data in loc-hlist-rst is auto-migrated to loc-rst when the key suggests the type is loc-rst:
        self.assertEqual({'en-US': 'foo'}, upgrade_note_schema('sample-loc-rst', {'en-US': [{'foo': None}]}))


if __name__ == '__main__':
    unittest.main()
