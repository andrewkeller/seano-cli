"""
pyseano/cmd/hash_repo.py

Interactive command-line wrapper on top of the infrastructure that hashes a release notes database.
"""

from pyseano.db import *


def hash_release_notes_db(db, **db_kwargs):
    print(open_seano_database(db, **db_kwargs).incrementalHash())
