"""
seano_cli/cmd/init_note.py

Interactive command-line wrapper on top of the infrastructure that creates a new release note.
"""

from seano_cli.db import *
from seano_cli.utils import *
import sys


def make_new_release_notes(db_search_seed_path, count):
    edit_files(find_and_open_seano_database(db_search_seed_path).make_new_notes(count))


def print_note_template(db_search_seed_path):
    sys.stdout.write(find_and_open_seano_database(db_search_seed_path).get_seano_note_template_contents())
