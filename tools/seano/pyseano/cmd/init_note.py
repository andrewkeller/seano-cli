"""
pyseano/cmd/init_note.py

Interactive command-line wrapper on top of the infrastructure that creates a new release note.
"""

from pyseano.db import *
from pyseano.utils import *
import sys


def make_new_release_notes(db, count):
    edit_files(open_seano_database(db).make_new_notes(count))


def print_note_template(db):
    sys.stdout.write(open_seano_database(db).get_seano_note_template_contents())
