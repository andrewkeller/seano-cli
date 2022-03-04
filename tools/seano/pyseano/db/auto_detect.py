"""
pyseano/db/auto_detect.py

Automatically deduces the type of the database at the given path, and returns an appropriate database reader.
"""

from pyseano.constants import *
from pyseano.db.dumb import DumbSeanoDatabase
from pyseano.db.git import GitSeanoDatabase
from pyseano.utils import SeanoFatalError
import logging
import os
import sys

log = logging.getLogger(__name__)


def locate_dot_seano_file(seed_path):
    seed_path = os.path.abspath(seed_path)
    while seed_path:
        attempt = os.path.join(seed_path, SEANO_DOTFILE_FILE)
        if os.path.exists(attempt):
            return attempt
        next = os.path.dirname(seed_path)
        if next == seed_path:
            break
        seed_path = next
    return None


def follow_dot_seano_file(dot_seano_file):
    with open(dot_seano_file, 'r') as f:
        key, _, path = f.read().splitlines()[0].partition(':')

    if key != SEANO_DOTFILE_DB_PATH_KEY:
        raise SeanoFatalError('Unable to read %s: data does not start with `%s`.' % (dot_seano_file, SEANO_DOTFILE_DB_PATH_KEY))

    # `.seano` files are always written with Unix path separators;
    # convert back to native before we try to use the path.
    path = path.strip().replace('/', os.sep)

    return os.path.join(os.path.dirname(dot_seano_file), path)


def find_seano_database(db_search_seed_path):
    dot_seano_file = locate_dot_seano_file(seed_path=db_search_seed_path or '')
    if not dot_seano_file:
        raise SeanoFatalError('Unable to find a seano database starting from `%s`.  Do you need to run `seano init`?' % (db_search_seed_path or '',))
    db_path = follow_dot_seano_file(dot_seano_file)
    if not db_path:
        raise SeanoFatalError('Unable to read %s (unknown problem)' % (dot_seano_file,))

    return db_path


def open_seano_database(path, **db_kwargs):
    db = GitSeanoDatabase(path, **db_kwargs)
    if db.is_valid():
        log.debug('Using GitSeanoDatabase at %s', path)
        return db
    db = DumbSeanoDatabase(path, **db_kwargs)
    if db.is_valid():
        log.debug('Using DumbSeanoDatabase at %s', path)
        return db
    raise SeanoFatalError('None of the seano database implementations accepted the path `%s`...  What is wrong?' % (path,))


def find_and_open_seano_database(db_search_seed_path, **db_kwargs):
    path = find_seano_database(db_search_seed_path=db_search_seed_path)
    return open_seano_database(path=path, **db_kwargs)
