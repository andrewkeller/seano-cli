"""
pyseano/utils.py
Generic seano util functions
"""

from pyseano.constants import *
import errno
import hashlib
import logging
import os
import shlex
import subprocess
import sys

log = logging.getLogger(__name__)


def write_file(filename, contents):
    if os.path.isfile(filename):
        log.error("cannot write new file (already exists): %s", filename)
        sys.exit(1)
    try:
        with open(filename, "w") as f:
            f.write(contents)
        return
    except IOError as e:
        if e.errno != errno.ENOENT:
            log.error("cannot write new file: %s", e)
            sys.exit(1)
    os.makedirs(os.path.dirname(filename))
    with open(filename, "w") as f:
        f.write(contents)


def edit_files(filenames):
    if not filenames:
        return
    editor = shlex.split(os.environ.get('SEANO_EDITOR', os.environ.get('EDITOR', SEANO_DEFAULT_EDITOR)))
    subprocess.call(editor + filenames)


def h_data(*data):
    m = hashlib.sha1()
    for d in data:
        m.update(d)
    return m.hexdigest()


def h_file(*files):
    m = hashlib.sha1()
    for f in files:
        if os.path.isdir(f):
            log.error("Assertion failed: not a file: %s", f)
            sys.exit(1)
        m.update(str(os.path.getmtime(f)))
    return m.hexdigest()


def h_folder(*folders):
    def h(f):
        if os.path.isdir(f):
            return h_folder(*[os.path.join(f, x) for x in os.listdir(f)])
        return h_file(f)
    return h_data(*[h(f) for f in folders])


def list_if_not_already(item):
    if isinstance(item, list):
        return item
    return [item]
