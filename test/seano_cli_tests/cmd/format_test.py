# format_test.py
#
# Automated unit tests for the seano CLI
#   - in particular, the ability to execute a formatter
import unittest

from seano_cli.cmd import format_query_output
from seano_cli.utils import SeanoFatalError


def format_format_test(bucket, value):
    bucket.extend([2, value])


def format_other_test(bucket, value):
    bucket.extend([3, value])


class SeanoFormatTest(unittest.TestCase):
    def testCorrectlyFailsForUnknownModule(self):
        self.assertRaises(SeanoFatalError, lambda: format_query_output(format_name='example_format_that_doesnt_exist', args=[]))

    def testCanLookupPublicFormatter(self):
        bucket = []
        format_query_output(format_name='utest_example_public', args=[bucket, 'hello'])
        self.assertEqual([1, "hello"], bucket)

    def testCanLookupPrivateFormatter(self):
        bucket = []
        format_query_output(format_name='seano_cli_tests.cmd.format_test', args=[bucket, 'hello'])
        self.assertEqual([2, "hello"], bucket)

    def testCanLookupPrivateFormatterWithCustomName(self):
        bucket = []
        format_query_output(format_name='seano_cli_tests.cmd.format_test:format_other_test', args=[bucket, 'hello'])
        self.assertEqual([3, "hello"], bucket)


if __name__ == '__main__':
    unittest.main()
