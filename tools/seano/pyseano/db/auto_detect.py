"""
pyseano/db/auto_detect.py

Automatically deduces the type of the database at the given path, and returns an appropriate database reader.
"""

from pyseano.constants import *
from pyseano.db.dumb import DumbSeanoDatabase
from pyseano.db.git import GitSeanoDatabase
import logging
import os
import sys

log = logging.getLogger(__name__)


def open_seano_database(path, **db_kwargs):
    db = GitSeanoDatabase(path, **db_kwargs)
    if db.is_valid():
        log.debug("Using GitSeanoDatabase")
        return db
    db = DumbSeanoDatabase(path, **db_kwargs)
    if db.is_valid():
        log.debug("Using DumbSeanoDatabase")
        return db
    log.error("seano db doesn't look valid.  Do you need to run `seano init`?")
    sys.exit(1)
