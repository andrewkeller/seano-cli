"""
seano_cli/cmd/hash_repo.py

Interactive command-line wrapper on top of the infrastructure that hashes a release notes database.
"""

from seano_cli.db import *
from seano_cli.utils import SeanoFatalError
import os
import sys


def hash_release_notes_db(db_search_seed_paths, **db_kwargs):

    did_all_hashes_succeed = True

    for db_search_seed_path in db_search_seed_paths or ['.']:

        try:
            db = find_and_open_seano_database(db_search_seed_path, **db_kwargs)
        except SeanoFatalError as e:
            sys.stderr.write(str(e))
            sys.stderr.write('\n')
            # Always print some kind of line on stdout, so that
            # stdout lines up with the arguments to this command:
            print('%040d  %s' % (0, os.path.abspath(db_search_seed_path)))
            did_all_hashes_succeed = False
            continue
        finally:
            # Only the first database is allowed to use db_kwargs
            db_kwargs = {}

        # Following the same style as `shasum()`, print the hash, two spaces,
        # and the thing we hashed (specifically, the full path to the database)
        print(db.incrementalHash() + '  ' + db.path)

    if not did_all_hashes_succeed:
        sys.exit(1)
