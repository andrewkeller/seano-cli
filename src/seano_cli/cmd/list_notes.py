"""
seano_cli/cmd/list_notes.py

Interactive command-line wrapper on top of the infrastructure that lists the latest added release notes.
"""

from seano_cli.db import *
from seano_cli.utils import *

log = logging.getLogger(__name__)


# IMPROVE: This shares a lot with `edit_latest_release_note()`; should they be unified?
def list_latest_release_notes(db_search_seed_path, include_wip, include_modified, include_ghosts, patterns):
    db = find_and_open_seano_database(db_search_seed_path)
    files = []
    # IMPROVE: In a Git-backed project, `most_recently_added_notes()` and `get_notes_matching_pattern()` are both
    #          implemented using the Git scanner.  And, the use of `get_notes_matching_pattern()` is inside a for
    #          loop.  There's some room for improvement here with regard to performance; although the Git scanner
    #          is designed to be as fast as possible, it is also not terribly cheap; it would be nice to invoke it
    #          less often.
    if include_wip or not patterns:
        files.extend(db.most_recently_added_notes(include_modified=include_modified))
        log.debug("Most recent files are:\n    %s", "\n    ".join(files))
    if patterns:
        for pattern in patterns:
            new_files, errors = db.get_notes_matching_pattern(pattern, include_modified=include_modified)
            if not new_files:
                raise SeanoFatalError('Unable to resolve pattern:\n    %s' % ('\n    '.join(errors),))
            log.debug("Pattern '%s' yielded:\n    %s", pattern, "\n    ".join(new_files))
            files.extend(new_files)
    if not files:
        raise SeanoFatalError("Release notes database is empty")
    files = sorted(set(files))
    for f in files:
        if include_ghosts or not db.is_ghost(f):
            print(db.extract_uid_from_filename(f))
