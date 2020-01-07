"""
pyseano/cmd/rekey_note.py

Interactive command-line wrapper on top of the infrastructure that re-keys a release note
"""

from pyseano.db import *


def rekey_release_note(db, uid):
    open_seano_database(db).rekey_note(uid)
