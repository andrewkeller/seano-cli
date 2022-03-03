"""
pyseano/cmd/mark_as_ghost.py

Interactive command-line wrapper on top of the infrastructure that marks
currently existing extern notes as ghosts.
"""

from pyseano.db import *

import os
import sys


def mark_as_ghost(db_search_seed_path, is_dry_run, extern_id):
    db = find_and_open_seano_database(db_search_seed_path)
    path_info = db.mark_all_notes_as_ghosts(is_dry_run=is_dry_run, extern_id=extern_id)

    if path_info:
        sys.stderr.write('\n'.join([
            'The following paths were updated:',
            '',
            ] + ['    %s  %s' % (s, os.path.relpath(p)) for s, p in path_info] + [
            '',
            'Please review the changes and commit them.',
            '',
        ]))
