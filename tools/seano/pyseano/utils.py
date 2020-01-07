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

ascii_str_type = bytes if sys.hexversion >= 0x3000000 else str
unicode_str_type = str if sys.hexversion >= 0x3000000 else unicode

log = logging.getLogger(__name__)


def coerce_to_str(s):
    'Coerces the given value to whatever the `str` type is on this Python.'
    if sys.hexversion >= 0x3000000:
        if isinstance(s, bytes):
            return s.decode('utf-8')
    else:
        if isinstance(s, unicode):
            return s.encode('utf-8')
    return s


def coerce_to_ascii_str(s):
    'Coerces the given value to a byte string.'
    if isinstance(s, ascii_str_type):
        return s
    if isinstance(s, unicode_str_type):
        return s.encode('utf-8')
    # The bytes class in Python 3 is less flexible/powerful than the str class in Python 2, and explodes more easily.
    # As a workaround, use the str class to serialize untrusted types, and then convert to ASCII when on Python 3.
    return coerce_to_ascii_str(str(s))


def coerce_to_unicode_str(s):
    'Coerces the given value to a unicode string.'
    if isinstance(s, unicode_str_type):
        return s
    if isinstance(s, ascii_str_type):
        return s.decode('utf-8')
    return unicode_str_type(s)


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
    if len(filenames) > 9:
        if raw_input('Found %d notes; are you sure you want to run `%s` with all of them? [y,N]  '
                     % (len(filenames), ' '.join(editor))).lower() not in ['y', 'ye', 'yes']:
            return
    subprocess.call(editor + filenames)


def h_data(*data):
    m = hashlib.sha1()
    for d in data:
        m.update(coerce_to_ascii_str(d))
    return m.hexdigest()


def h_file(*files):
    m = hashlib.sha1()
    for f in files:
        if os.path.isdir(f):
            log.error("Assertion failed: not a file: %s", f)
            sys.exit(1)
        m.update(coerce_to_ascii_str(str(os.path.getmtime(f))))
    return m.hexdigest()


def h_folder(*folders):
    def h(f):
        if os.path.isdir(f):
            return h_folder(*[os.path.join(f, x) for x in os.listdir(f)])
        return h_file(f)
    return h_data(*[h(f) for f in folders])


def list_if_not_already(item):
    if isinstance(item, set):
        return list(item)
    if isinstance(item, list):
        return item
    return [item]
