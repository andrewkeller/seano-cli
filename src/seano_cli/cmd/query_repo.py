"""
seano_cli/cmd/query_repo.py

Interactive command-line wrapper on top of the infrastructure that queries a seano database for release notes.
"""

from seano_cli.db import *
from seano_cli.utils import *
import json

log = logging.getLogger(__name__)


def query_release_notes(db_search_seed_path, out, **db_kwargs):
    if not out:
        raise SeanoFatalError("Invalid desitnation file: (empty string)")

    data = find_and_open_seano_database(db_search_seed_path, **db_kwargs).query()
    data = json.dumps(data, sort_keys=True)

    if sys.hexversion < 0x3000000:
        data = data.encode('utf-8')

    if out in ['-']:
        print(data)
        return

    with open(out, 'w', **FILE_ENCODING_KWARGS) as f:
        f.write(data)
        f.write('\n')
