"""
pyseano/cmd/format_query_output.py

Interactive command-line wrapper on top of the infrastructure that converts a seano query output file into
a human-readable format.
"""

# Gain access to Zarf's Python support module, which is where the stock seano views are located:
import os
import sys
sys.path.append(os.path.abspath(os.path.join(__file__, '..', '..', '..', '..', '..')))

import logging
from support.seano.views.ce_sphinx_1 import compile_seano_ce_sphinx_1
from support.seano.views.qa_notes import compile_qa_notes

log = logging.getLogger(__name__)

format_functions = {
    'ce-sphinx-1': compile_seano_ce_sphinx_1,
    'qa-notes': compile_qa_notes,
}

format_choices = list(format_functions.keys());


def format_query_output(src, format, out):

    if not src:
        log.error('Invalid seano query output file: (empty string)')
        sys.exit(1)

    if not out:
        log.error('Invalid destination file: (empty string)')
        sys.exit(1)

    if format not in format_functions:
        log.error('Invalid format "%s": not supported', format)
        sys.exit(1)

    if src in ['-']:
        srcdata = sys.stdin.read()
    else:
        with open(src, 'r') as f:
            srcdata = f.read()

    outdata = format_functions[format](srcdata)

    if out in ['-']:
        sys.stdout.write(outdata)
        return

    with open(out, 'w') as f:
        f.write(outdata)
