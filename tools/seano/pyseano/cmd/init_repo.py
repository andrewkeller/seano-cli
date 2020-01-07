"""
pyseano/cmd/init_repo.py

Interactive command-line implementation of initializing a new seano database.
"""

from pyseano.constants import *
import errno
import logging
import os
import subprocess
import sys

log = logging.getLogger(__name__)


def make_new_release_notes_db(db):
    try:
        os.makedirs(db)
    except OSError as e:
        if e.errno != errno.EEXIST:
            log.error("cannot initialize new release notes database: %s", e)
            sys.exit(1)
    cfg = os.path.join(db, SEANO_CONFIG_FILE)
    if not os.path.isfile(cfg):
        with open(cfg, "w") as f:
            f.write(SEANO_CONFIG_TEMPLATE)
    log.info("Initialized new release notes repository in %s", db)
