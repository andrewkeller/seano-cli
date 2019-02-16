"""
pyseano/cmd/edit_note.py
Interactive command-line wrapper on top of the infrastructure that edits the latest added release note.
"""

from pyseano.db import *
from pyseano.utils import *

log = logging.getLogger(__name__)


def edit_latest_release_note(db, include_wip, include_modified, patterns):
    db = open_seano_database(db)
    files = []
    if include_wip or not patterns:
        files.extend(db.most_recently_added_notes(include_modified=include_modified))
        log.debug("Most recent files are:\n    %s", "\n    ".join(files))
    if patterns:
        for pattern in patterns:
            new_files, errors = db.get_notes_matching_pattern(pattern, include_modified=include_modified)
            if not new_files:
                log.error('Unable to resolve pattern:\n    %s' % ('\n    '.join(errors)))
                sys.exit(1)
            log.debug("Pattern '%s' yielded:\n    %s", pattern, "\n    ".join(new_files))
            files.extend(new_files)
    if not files:
        log.warning("Release notes database is empty")
        sys.exit(1)
    files.sort()
    log.debug("About to edit:\n    %s", "\n    ".join(files))
    edit_files(files)
