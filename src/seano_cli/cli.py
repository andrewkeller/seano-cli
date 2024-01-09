#!/usr/bin/env python
"""
seano

CE (release) Notes

Interrogates and manipulates a CE Release Notes (seano) database.
"""

from seano_cli.cmd import *
from seano_cli.utils import SeanoFatalError
import argparse
import logging
import os
import re
import sys

log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action='count', default=0, help='Increase verbosity level')
    subparsers = parser.add_subparsers(help='verb')

    def add_db_args(subparser, needsExtendedInfo=False):
        subparser.add_argument('--db', metavar='PATH', action='store', dest='db_search_seed_path', default='',
                               help='The path at which searching for a .seano file should start.  ' +
                               'Defaults to the current working directory.')
        if not needsExtendedInfo: return
        subparser.add_argument('--config-annex', action='store', metavar='PATH', dest='config_annex_path',
                               help='After loading the main config file located inside the seano database, also load ' +
                                    'the file located at this path and import all of the values')

    subparser = subparsers.add_parser('init', help='Initialize a new release notes database')
    subparser.set_defaults(func=make_new_release_notes_db)
    subparser.add_argument('--dot-seano-dir', action='store', default=os.path.join('.', ''),
                           help='The path where the `.seano` file pointing to the database should be created.  ' +
                           'A relative path is assumed to be relative to the shell\'s CWD.  ' +
                           'Defaults to `%(default)s`.')
    subparser.add_argument('--db-path', action='store', default=os.path.join('.', 'docs', 'seano-db'),
                           help='The path where the seano database itself should be created.  ' +
                           'A relative path is assumed to be relative to the directory containing the `.seano` file.  ' +
                           'Defaults to `%(default)s`.')

    subparser = subparsers.add_parser('new', help='Create a new release note and edit it')
    subparser.set_defaults(func=make_new_release_notes)
    add_db_args(subparser)
    subparser.add_argument('-n', action='store', dest='count', default=1, help='Number of new notes to create')

    subparser = subparsers.add_parser('edit', help='Identifies and edits the latest created relase note')
    subparser.set_defaults(func=edit_latest_release_note)
    add_db_args(subparser)
    subparser.add_argument('--include-wip', '-w', action='store_true', default=False,
                           help='When no patterns are provided, the default behavior is to search for notes that ' +
                                'have not been committed in the repository yet.  When one or more patterns are ' +
                                'provided, that behavior is disabled.  This option turns that back on.')
    subparser.add_argument('--include-modified', '-m', action='store_true', default=False,
                           help='Modified files (files edited within a range, but added previously), are ' +
                                'universally ignored when selecting files to edit, whether you supplied a pattern ' +
                                'or not.  This option modifies the file selection process to include modified files.')
    subparser.add_argument('patterns', metavar='PATTERN', nargs='*', default=[],
                           help='Instead of selecting works-in-progress (uncommitted notes), search for notes based ' +
                                'on a pattern.  The pattern may be the beginning of a note ID, or it may be a ' +
                                'commit ID or range in the underlying repository, from which we auto-detect added ' +
                                'notes.')

    subparser = subparsers.add_parser('list', help='Identifies the latest created relase notes, and prints their note IDs')
    subparser.set_defaults(func=list_latest_release_notes)
    add_db_args(subparser)
    subparser.add_argument('--include-wip', '-w', action='store_true', default=False,
                           help='When no patterns are provided, the default behavior is to search for notes that ' +
                                'have not been committed in the repository yet.  When one or more patterns are ' +
                                'provided, that behavior is disabled.  This option turns that back on.')
    subparser.add_argument('--include-modified', '-m', action='store_true', default=False,
                           help='Modified files (files edited within a range, but added previously), are ' +
                                'universally ignored when selecting files to edit, whether you supplied a pattern ' +
                                'or not.  This option modifies the file selection process to include modified files.')
    subparser.add_argument('--exclude-ghosts', dest='include_ghosts', action='store_false', default=True,
                           help='By default, all matching notes are reported.  This option peeks inside each discovered '
                                'note, and if it\'s marked as a ghost, the note is excluded from the final list reported '
                                'to you.')
    subparser.add_argument('patterns', metavar='PATTERN', nargs='*', default=[],
                           help='Instead of selecting works-in-progress (uncommitted notes), search for notes based ' +
                                'on a pattern.  The pattern may be the beginning of a note ID, or it may be a ' +
                                'commit ID or range in the underlying repository, from which we auto-detect added ' +
                                'notes.')

    def repo_spec(value):
        key_pattern = '[a-zA-Z0-9_-]+'
        pattern = '^(?P<key>' + key_pattern + r'):(?P<path>.+)$'
        m = re.search(pattern, value)
        if not m:
            raise argparse.ArgumentTypeError('\n'.join([
                'invalid argument: "%s"' % (value,),
                '',
                'Hint: repo_spec values must be in the form "key:value", where:',
                '    key ~ /^' + key_pattern + '$/',
                '    value is a path to a directory whence we can search for another seano database',
            ]))
        return m.group('key'), m.group('path')

    subparser = subparsers.add_parser('import', help='Imports notes from an external seano database',
                                      description='Imports notes from an external seano database.  ' +
                                      'From an architecture point of view, seano does not support ' +
                                      'submodules directly, because we need to be able to access a ' +
                                      'unified commit graph of the history of all the notes, which ' +
                                      'is unnecessarily difficult when multiple repositories are ' +
                                      'involved.  As a compromise, seano can import notes from another ' +
                                      'seano database into the local seano database, enabling them to ' +
                                      'be tracked in the same SCM system as the local seano database ' +
                                      '(because everything is in the same SCM system).  When notes ' +
                                      'are imported, a path-safe, shell-safe, semi-permanent identifier ' +
                                      'is required for each external database.  This identifier is used ' +
                                      'to identify the origin of the note, and with that knowledge, ' +
                                      'identify when an external database has *deleted* a note.  Thus, ' +
                                      'this command can (a) import new notes, (b) update modified notes, ' +
                                      'and (c) delete deleted notes.')
    subparser.set_defaults(func=import_from_submodules)
    add_db_args(subparser)
    subparser.add_argument('--dry-run', action='store_true', dest='is_dry_run', default=False,
                           help='Describe modifications that would be made, and do not modify any files on disk')
    subparser.add_argument('--assert-no-change', action='store_true', default=False,
                           help='If the import made changes in the local database, or would have made ' +
                           'changes and --dry-run was specified, exit with a non-zero exit code.')
    subparser.add_argument(nargs='+', dest='db_defs', type=repo_spec, help='Accumulator')

    subparser = subparsers.add_parser('ghost', help='Mark certain notes as ghosts',
                                      description='Marks notes as ghosts.  Ghost notes are real notes, ' +
                                      'but do not show up in queries.  Ghost notes are useful when you ' +
                                      'initially hook up a new submodule, and you don\'t want the full ' +
                                      'database of all notes in the submodule (which likely represent ' +
                                      'multiple releases!) to show up on your product\'s current release ' +
                                      'as "changes".  Once you declare a note as a ghost, you don\'t have ' +
                                      'to repeatedly keep declaring a note as a ghost on subsequent imports ' +
                                      'from that submodule.')
    subparser.set_defaults(func=mark_as_ghost)
    add_db_args(subparser)
    subparser.add_argument('--dry-run', action='store_true', dest='is_dry_run', default=False,
                           help='Describe modifications that would be made, and do not modify any files on disk')
    subparser.add_argument('--extern-id', action='append', default=[], dest='extern_ids',
                           help='Matches all notes that are associated with the given extern identifier')
    subparser.add_argument('patterns', metavar='PATTERN', nargs='*', default=[],
                           help='Search for notes based on a pattern.  The pattern may be the beginning of a '
                           'note ID, or it may be a commit ID or range in the underlying repository, from '
                           'which we auto-detect added notes.')

    subparser = subparsers.add_parser('hash', help='Returns an arbitrary string that changes with all database '+
                                      'modifications; used by build systems to properly support incremental builds')
    subparser.set_defaults(func=hash_release_notes_db)
    subparser.add_argument('--config-annex', action='store', metavar='PATH', dest='config_annex_path',
                           help='After loading the main config file located inside the first provided seano database, ' +
                           'also load the file located at this path and import all of the values.  The config annex ' +
                           'is not loaded for any of the subsequently specified databases, which are assumed to be ' +
                           'associated extern databases, such as submodules, which don\'t normally load the config ' +
                           'annex.')
    subparser.add_argument(nargs='*', dest='db_search_seed_paths', metavar='PATH', action='store', default=[],
                           help='The path at which searching for a .seano file should start.  If no paths are ' +
                           'specified, the current working directory is used.  If one path is specified, it is ' +
                           'assumed to be the primary database, which may load a config annex, if provided.  ' +
                           'If additional paths are provided, they are assumed to be associated extern databases, ' +
                           'and are hashed in the order of the arguments.')

    subparser = subparsers.add_parser('query', help='Compiles release notes from the given database')
    subparser.set_defaults(func=query_release_notes)
    add_db_args(subparser, True)
    subparser.add_argument('--out', action='store', required=True, help='Output file; use a single hyphen for stdout')

    subparser = subparsers.add_parser('print-note-template', help='Print the default note template to stdout')
    add_db_args(subparser)
    subparser.set_defaults(func=print_note_template)

    subparser = subparsers.add_parser('format', help='Convert a seano query output file into something human-readable')
    subparser.set_defaults(func=format_query_output)
    subparser.add_argument('--list-formatters', action='store_true', help='List all of the Seano formatter plugins '
                           'currently installed on this computer')
    subparser.add_argument('format_name', metavar='FORMAT', nargs='?', help='The name of the format to use; this is '
                           'either the short name of a Seano formatter plugin, or it is the fully qualified Python '
                           'module name of a private Seano formatter')
    subparser.add_argument('args', nargs=argparse.REMAINDER, help='The argument stack to supply to the formatter')
    subparser.set_defaults(usage_str=subparser.format_usage())

    ns = parser.parse_args()

    logging.basicConfig(level=
        {
            0 : logging.WARNING,
            1 : logging.INFO,
            2 : logging.DEBUG,
        }.get(
            min(max(ns.verbose, 0), 2)
        ))

    log.debug('Arguments: %s', ns)

    kwargs = dict(vars(ns))
    try:
        del kwargs['func']
        del kwargs['verbose']
    except KeyError:
        parser.print_help()
        sys.exit(1)

    try:
        ns.func(**kwargs)
    except SeanoFatalError as e:
        # Expectation is that any supplimental errors/warnings are already logged, and that
        # this exception contains an error message to be printed, plus also indicates that
        # we should exit with a non-zero exit status.

        if ns.verbose > 1:
            # Show the stack trace of this error, followed by the error message, and then die:
            raise

        # Else, only print the error message, and then die:
        sys.stderr.write('fatal: ')
        sys.stderr.write(str(e))
        sys.stderr.write('\n')
        sys.exit(1)


if __name__ == '__main__':
    main()
