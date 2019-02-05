"""
pyseano/cmd/edit_note.py
Interactive command-line wrapper on top of the infrastructure that edits the latest added release note.
"""

from pyseano.db import *
from pyseano.utils import *

log = logging.getLogger(__name__)


def edit_latest_release_note(db):
    files = open_seano_database(db).most_recently_added_notes()
    if not files:
        log.warning("Release notes database is empty")
        sys.exit(1)
    log.debug("Most recent files are:\n\t%s", "\n\t".join(files))
    edit_files(files)
