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
from pyseano.utils import SeanoFatalError, FILE_ENCODING_KWARGS
from support.seano.views.ce_sphinx_1 import compile_seano_ce_sphinx_1
from support.seano.views.qa_notes import compile_qa_notes
from support.seano.views.wiki_latest_releases import compile_confluence_latest_releases
from support.seano.views.wiki_mc_notes import compile_confluence_mc_notes
from support.seano.views.wiki_release_notes import compile_confluence_release_notes
from support.seano.views.wiki_tech_notes import compile_confluence_tech_notes

log = logging.getLogger(__name__)

format_functions = {
    'ce-sphinx-1': compile_seano_ce_sphinx_1,
    'qa-notes': compile_qa_notes,
    'confluence_latest_releases': compile_confluence_latest_releases,
    'confluence_mc_notes': compile_confluence_mc_notes,
    'confluence_release_notes': compile_confluence_release_notes,
    'confluence_tech_notes': compile_confluence_tech_notes,
}

format_choices = list(format_functions.keys());


def format_query_output(src, format, out):

    if not src:
        raise SeanoFatalError('Invalid seano query output file: (empty string)')

    if not out:
        raise SeanoFatalError('Invalid destination file: (empty string)')

    if format not in format_functions:
        raise SeanoFatalError('Invalid format "%s": not supported' % (format,))

    if src in ['-']:
        srcdata = sys.stdin.read()
    else:
        with open(src, 'r') as f:
            srcdata = f.read()

    outdata = format_functions[format](srcdata)

    if sys.hexversion < 0x3000000:
        outdata = outdata.encode('utf-8')

    if out in ['-']:
        sys.stdout.write(outdata)
        return

    with open(out, 'w', **FILE_ENCODING_KWARGS) as f:
        f.write(outdata)
