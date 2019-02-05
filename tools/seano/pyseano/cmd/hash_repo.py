"""
pyseano/cmd/hash_repo.py
Interactive command-line wrapper on top of the infrastructure that hashes a release notes database.
"""

from pyseano.db import *


def hash_release_notes_db(db):
    print open_seano_database(db).incrementalHash()
