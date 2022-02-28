"""
pyseano/cmd/hash_repo.py

Interactive command-line wrapper on top of the infrastructure that hashes a release notes database.
"""

from pyseano.db import *


def hash_release_notes_db(db_search_seed_path, **db_kwargs):
    db = find_and_open_seano_database(db_search_seed_path, **db_kwargs)
    # Following the same style as `shasum()`, print the hash, two spaces,
    # and the thing we hashed (specifically, the full path to the database)
    print(db.incrementalHash() + '  ' + db.path)
