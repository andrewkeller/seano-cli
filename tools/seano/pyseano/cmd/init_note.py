"""
pyseano/cmd/init_note.py
Interactive command-line wrapper on top of the infrastructure that creates a new release note.
"""

from pyseano.db import *
from pyseano.utils import *


def make_new_release_note(db):
    edit_files([open_seano_database(db).make_new_note()])
