"""
seano_cli/cmd/init_repo.py

Interactive command-line implementation of initializing a new seano database.
"""

from seano_cli.constants import *
from seano_cli.utils import SeanoFatalError, FILE_ENCODING_KWARGS
import errno
import logging
import os
import subprocess

log = logging.getLogger(__name__)


def make_new_release_notes_db(dot_seano_dir, db_path):
    dot_seano_path = os.path.abspath(os.path.join(dot_seano_dir, SEANO_DOTFILE_FILE))
    log.debug('Will create a `.seano` file at: %s', dot_seano_path)

    # ABK: os.path.join() automatically ignores former arguments when one of the paths is absolute
    db_path = os.path.abspath(os.path.join(dot_seano_dir, db_path))
    log.debug('Will create a seano database at: %s', db_path)

    db_redirect_path = os.path.relpath(db_path, dot_seano_dir)
    log.debug('Relative path from the `.seano` directory to the seano database is: %s', db_redirect_path)

    if db_redirect_path.startswith('..'):
        log.warn('\n'.join([
            'The seano database path:',
            '    %s' % (db_path,),
            '',
            'is not located inside a child directory of the `.seano` file:',
            '    %s' % (dot_seano_dir,),
            '',
            'This is probably not what you want.',
        ]))
        # Not an error, so don't explode.

    # Normalize the relative path:
    db_redirect_path = db_redirect_path.replace('\\', '/')

    # Write the `.seano` file to disk:
    with open(dot_seano_path, 'w', **FILE_ENCODING_KWARGS) as f:
        f.write(SEANO_DOTFILE_DB_PATH_KEY)
        f.write(': ')
        f.write(db_redirect_path)
        f.write('\n')

    # Initialize the database itself:

    try:
        os.makedirs(db_path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise SeanoFatalError("cannot initialize new release notes database: %s" % (e,))
    cfg = os.path.join(db_path, SEANO_CONFIG_FILE)
    if os.path.isfile(cfg):
        log.info('Hint: Not overwriting %s with the default config template because it already exists', cfg)
    else:
        with open(cfg, 'w', **FILE_ENCODING_KWARGS) as f:
            f.write(SEANO_CONFIG_TEMPLATE)
    log.info('Initialized new release notes repository in %s', db_path)
