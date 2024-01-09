# schema_upgrade_test.py
#
# Automated unit tests for the schema upgrading logic in seano
from ..schema_upgrade import upgrade_note_schema
import unittest


class SchemaUpgradeTest(unittest.TestCase):
    def testNotesHaveHlistsMigrated(self):
        # Unknown keys pass through:
        self.assertEqual(42, upgrade_note_schema('trouble', 42))
        # Data already formatted as loc-md:
        self.assertEqual({'en-US': 'foo'}, upgrade_note_schema('sample-loc-md', {'en-US': 'foo'}))


if __name__ == '__main__':
    unittest.main()
