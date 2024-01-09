"""
seano_cli/cmd/import_from_submodules.py

Interactive command-line wrapper on top of the infrastructure that syncs
database changes in submodules with the the current database.
"""

from seano_cli.db import *
from seano_cli.db.auto_detect import find_seano_database
from seano_cli.utils import SeanoFatalError
import os
import sys


def import_from_submodules(db_search_seed_path, is_dry_run, assert_no_change, db_defs):
    db = find_and_open_seano_database(db_search_seed_path)

    # Check for overlapping databases:
    # ABK: Yes, db.import_extern_notes() does check this as well...  but
    #      we are in a better position to provide a good error message.

    db_defs = [(id, seed_path, find_seano_database(seed_path)) for id, seed_path in db_defs]

    if len(set([db.path] + [db_path for _, _, db_path in db_defs])) != len(db_defs) + 1:
        raise SeanoFatalError('\n'.join([
            'Unable to import notes from extern databases because some of the',
            'databases are the same database.',
            '',
            'Database paths:',
            '',
            '    %s  (Actual Destination)' % (db.path,),
        ] + ['    %s' % (db_path,) for _, _, db_path in db_defs] + [
            '',
            'Provided seed paths that found the above databases:',
            '',
            '    %s  (Requested Destination)' % (db_search_seed_path or '.',),
        ] + ['    %s' % (seed_path or '.',) for _, seed_path, _ in db_defs] + [
            '',
            'The common causes of this problem are:',
            '',
            '  - Missing or corrupt .seano file in a submodule',
            '  - Attempt to enable note importing from a submodule that does',
            '    not contain a seano database',
            '  - Incorrect path to an otherwise valid submodule with a seano',
            '    database',
        ]))

    # Okay, we're good.  Remove the search seed paths, and run the import:

    db_defs = [(id, db_path) for id, _, db_path in db_defs]

    path_info = db.import_extern_notes(is_dry_run=is_dry_run, db_defs=db_defs)

    if path_info:
        sys.stderr.write('\n'.join([
            '',
            'The following paths were updated:',
            '',
            ] + ['    %s  %s' % (s, os.path.relpath(p)) for s, p in path_info] + [
            '',
            'Please review the changes and commit them.',
            '',
        ]))

        if assert_no_change:
            sys.exit(1)
