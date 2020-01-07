"""
pyseano/cmd/query_repo.py

Interactive command-line wrapper on top of the infrastructure that queries a seano database for release notes.
"""

from pyseano.db import *
from pyseano.utils import *
import json

log = logging.getLogger(__name__)


def query_release_notes(db, out, **db_kwargs):
    if not out:
        log.error("Invalid desitnation file: (empty string)")
        sys.exit(1)

    data = open_seano_database(db, **db_kwargs).query()
    data = json.dumps(data, sort_keys=True)

    if out in ['-']:
        print(data)
        return

    with open(out, "w") as f:
        f.write(data)
        f.write('\n')
