"""
seano_cli/db/dumb.py

Reads a dumb seano database (one without a repository).
"""

from seano_cli.db.generic import GenericSeanoDatabase


class DumbSeanoDatabase(GenericSeanoDatabase):
    pass
