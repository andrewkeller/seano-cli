"""
pyseano/db/generic.py
Base class for the different kinds of seano databases
"""

from pyseano.db.note_set import NoteSet
from pyseano.utils import *
import errno
import glob
import logging
import os
import re
import sys
import uuid
import yaml

log = logging.getLogger(__name__)


class GenericSeanoDatabase(object):
    def __init__(self, path,
                 # ABK: Not using kwargs here so that we can block non-accepted args
                 current_version=None, parent_versions=None):
        self.path = os.path.abspath(path)
        self.db_objs = os.path.join(self.path, SEANO_DB_SUBDIR)

        # Load database's current configurations from disk:
        cfg = os.path.join(path, SEANO_CONFIG_FILE)
        try:
            with open(cfg, "r") as f:
                for d in yaml.load_all(f):
                    for k, v in d.items():
                        setattr(self, k, v)
        except IOError as e:
            if e.errno != errno.ENOENT:
                log.warning("unusual error while trying to read %s: %s", cfg, e)
                sys.exit(1)

        # Possibly overwrite some database configurations if they were provided to this constructor:

        if current_version:
            self.current_version = current_version
        if not getattr(self, 'current_version', None):
            self.current_version = 'HEAD'

        if parent_versions:
            self.parent_versions = parent_versions
        if not getattr(self, 'parent_versions', None):
            self.parent_versions = []

    def is_valid(self):
        if not os.path.isfile(os.path.join(self.path, SEANO_CONFIG_FILE)): return False
        return True

    def incrementalHash(self):
        return h_data(h_folder(self.path), self.current_version, *self.parent_versions)

    def make_new_note_filename(self):
        return self.make_note_filename_from_uid(uuid.uuid4().hex)

    def make_note_filename_from_uid(self, uid):
        fs_uid = uid[:2] + os.sep + uid[2:] + SEANO_TEMPLATE_EXTENSION # be friendly to filesystems
        return os.path.join(self.db_objs, fs_uid)

    def extract_uid_from_filename(self, filename):
        # IMPROVE: This algorithm could use some santity checking to make sure it's returning a sane result
        return filename[-38:-36] + filename[-35:-5]

    def make_new_note(self):
        filename = self.make_new_note_filename()
        write_file(filename, SEANO_TEMPLATE_CONTENTS)
        return filename

    def make_new_notes(self, count):
        count = int(count) # Buck stops here for garbage data
        filenames = []
        while len(filenames) < count:
            filenames.append(self.make_new_note())
        filenames.sort()
        return filenames

    def rekey_note(self, from_id):
        from_filename = self.make_note_filename_from_uid(from_id)
        with open(from_filename, 'r') as f:
            data = f.read()
        to_filename = self.make_new_note_filename()
        try:
            os.makedirs(os.path.dirname(to_filename))
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        self.move_note(from_filename, to_filename)

    def move_note(self, from_filename, to_filename):
        os.rename(from_filename, to_filename)

    def most_recently_added_notes(self, include_modified):
        log.error("Database is not repository-backed; unable to intuit which release note is latest")
        sys.exit(1)

    def get_notes_matching_pattern(self, pattern, include_modified):
        # Even without a repository, we can still search the database for filenames that matches the given pattern.
        m = re.match(r'^([0-9a-fA-F]{2})/?([0-9a-fA-F]*)$', pattern)
        if not m:
            return ([], ["refusing to glob '%s' on disk in the seano database" % (pattern,)])
        pat = m.group(1) + os.sep + m.group(2) + '*' + SEANO_TEMPLATE_EXTENSION
        log.debug('Converted pattern to glob: %s', pat)
        files = glob.glob(os.path.join(self.db_objs, pat))
        if not files:
            return ([], ['No note in the database has a filename like ' + pat])
        return (files, [])

    def query(self):
        # Even without a repository, we can still load everything and hope that all the information we need exists in
        # the band files and in the global config.  This is in fact what a freshly onboarded database looks like; we
        # can't trust the repository for those old versions anyways, so all the version numbers are hard-coded.
        #
        # Note, though, that this implementation doesn't scale well because we don't know when to bail, because there
        # is no sense of time without a repository.  This implementation is basically a glorified demo.
        s = NoteSet(self.current_version)
        s.load_version_info(getattr(self, 'version_defs', []))
        s.load_version_info([{
            'name' : self.current_version,
            'after' : self.parent_versions,
        }])
        for root, directories, filenames in os.walk(self.db_objs):
            for f in filenames:
                if f.endswith(SEANO_TEMPLATE_EXTENSION):
                    f = os.path.join(root, f)
                    s.load_note(f, self.extract_uid_from_filename(f))
        return s.dump()
