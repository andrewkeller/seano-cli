"""
seano_cli/utils.py

Generic seano util functions
"""

from seano_cli.constants import *
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
FILE_ENCODING_KWARGS = {'encoding': 'utf-8'} if sys.hexversion >= 0x3000000 else {}


class SeanoFatalError(Exception):
    '''
    An exception type that is used to declare a fatal error -- an error where you might want to
    just kill the app.

    In fact, early versions of seano literally did kill the app.  However, as we've grown, it
    turns out that killing the app is not friendly to unit tests.  So, when some low-level code
    wants to kill the app, it raises this exception instead.  seano itself will then voluntarily
    die with non-zero exit status, and unit tests catch the exception and move on.
    '''
    pass


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


def get_unencrypted_shell_input(prompt_text):
    'Fetches a value from the user on the command-line.'
    # ABK: Manually writing the prompt because the stock implementation doesn't write to stderr.
    sys.stderr.write(prompt_text)
    sys.stderr.flush()
    return input() if sys.hexversion >= 0x3000000 else raw_input()


def write_file(filename, contents):
    if os.path.isfile(filename):
        raise SeanoFatalError("cannot write new file (already exists): %s" % (filename,))
    write_existing_file(filename, contents)


def write_existing_file(filename, contents):
    try:
        with open(filename, "w", **FILE_ENCODING_KWARGS) as f:
            f.write(contents)
        return
    except IOError as e:
        if e.errno != errno.ENOENT:
            raise SeanoFatalError("cannot write new file: %s" % (e,))
    os.makedirs(os.path.dirname(filename))
    with open(filename, "w", **FILE_ENCODING_KWARGS) as f:
        f.write(contents)


def edit_files(filenames):
    if not filenames:
        return
    editor = shlex.split(os.environ.get('SEANO_EDITOR', os.environ.get('EDITOR', SEANO_DEFAULT_EDITOR)))
    if len(filenames) > 9:
        if get_unencrypted_shell_input('Found %d notes; are you sure you want to run `%s` with all of them? [y,N]  '
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
            raise SeanoFatalError("Assertion failed: not a file: %s" % (f,))
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
