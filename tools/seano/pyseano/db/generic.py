"""
pyseano/db/generic.py

Base class for the different kinds of seano databases
"""

from pyseano.db.common import SeanoDataAggregator
from pyseano.db.schema_upgrade import upgrade_root_object_schema
from pyseano.utils import *
import errno
import glob
import logging
import os
import re
import uuid
import yaml

log = logging.getLogger(__name__)


class GenericSeanoDatabase(object):
    def __init__(self, path,
                 # ABK: Not using kwargs here so that we can block non-accepted args
                 config_annex_path=None):
        self.path = str(os.path.abspath(path))
        self.db_objs = os.path.join(self.path, SEANO_DB_SUBDIR)

        # Load all configurations from disk, beginning with the annex
        # (so that anything in the database configuration overrides the annex):

        self.config = dict()
        def load_file(cfg, is_required):
            try:
                with open(cfg, "r") as f:
                    for d in yaml.load_all(f, Loader=yaml.FullLoader):
                        # An empty section in yaml yields None here.
                        # Although it's weird (wrong?) to have an empty section
                        # in a yaml file in seano, let's not crash, either.
                        if not d:
                            continue
                        d = upgrade_root_object_schema(d)
                        self.config.update(d)
            except IOError as e:
                if is_required or e.errno != errno.ENOENT:
                    raise SeanoFatalError("unusual error while trying to read %s: %s" % (cfg, e))

        if config_annex_path:
            load_file(config_annex_path, False)
        load_file(os.path.join(path, SEANO_CONFIG_FILE), True)

        # Possibly overwrite some database configurations if they were provided to this constructor:

        if not self.config.get('current_version', None):
            self.config['current_version'] = 'HEAD'

    def is_valid(self):
        if not os.path.isfile(os.path.join(self.path, SEANO_CONFIG_FILE)):
            log.info('%s does not exist.  Is this a seano database?', SEANO_CONFIG_FILE)
            return False
        return True

    def incrementalHash(self):
        return h_data(h_folder(self.path), str(self.config))

    def make_new_note_filename(self):
        return self.make_note_filename_from_uid(uuid.uuid4().hex)

    def make_note_filename_from_uid(self, uid):
        fs_uid = uid[:2] + os.sep + uid[2:] + SEANO_NOTE_EXTENSION # be friendly to filesystems
        return os.path.join(self.db_objs, fs_uid)

    def extract_uid_from_filename(self, filename):
        '''
        The uid of any note file is:

        1. its relative path from inside ``self.db_objs``
        2. with the file extension hacked off the end
        3. and all slashes removed

        Invoking this function with any file that is not a "proper" note file for the
        seano database currently referenced by this database object results in undefined
        behavior.
        '''
        result = os.path.relpath(filename, self.db_objs) # [1]
        result = os.path.splitext(result)[0] # [2]
        result = result.replace('/', '') # [3]
        result = result.replace('\\', '') # [3]
        return result

    def get_seano_note_template_contents(self):
        # The entire note template file may be overwritten on a per-database basis:
        result = self.config.get('seano_note_template_contents', SEANO_NOTE_DEFAULT_TEMPLATE_CONTENTS)

        # Regardless of how we obtained the initial copy of the template, perform configured replacements:
        for txt_find, txt_replace in (self.config.get('seano_note_template_replacements', None) or {}).items():
            modified = result.replace(txt_find, txt_replace)
            if modified == result:
                log.warning('Warning: Unable to apply note template delta: pattern not found: "%s"', (txt_find,))
            result = modified

        # And we're done.  This is the official note template.
        return result

    def make_new_note(self):
        filename = self.make_new_note_filename()
        write_file(filename, self.get_seano_note_template_contents())
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
        raise SeanoFatalError("Database is not repository-backed; unable to intuit which release note is latest")

    def get_notes_matching_pattern(self, pattern, include_modified):
        # Even without a repository, we can still search the database for filenames that matches the given pattern.
        # ABK: Deliberately accept both Unix and Windows slashes here, because worst case scenario, you may be
        #      on Windows, running git from Git-Bash, but running seano from a Windows command prompt (or vice-versa!)
        #      Thus, just because we *think* we know which slashes to use doesn't mean we should ban the other
        #      kind.  Just accept both, on all platforms, all the time.
        m = re.match(r'^([0-9a-fA-F]{2})[/\\]?([0-9a-fA-F]*)$', pattern)
        if not m:
            return ([], ["refusing to glob '%s' on disk in the seano database" % (pattern,)])
        pat = m.group(1) + os.sep + m.group(2) + '*' + SEANO_NOTE_EXTENSION
        log.debug('Converted pattern to glob: %s', pat)
        files = glob.glob(os.path.join(self.db_objs, pat))
        if not files:
            return ([], ['No note in the database has a filename like ' + pat])
        return (files, [])

    def query(self):
        # ABK: The beginning and end of this function should be kept somewhat in sync with the copy in git.py

        # Even without a repository, we can still load everything and hope that all the information we need exists in
        # the band files and in the global config.  This is in fact what a freshly onboarded database looks like; we
        # can't trust the repository for those old versions anyways, so all the version numbers are hard-coded.
        #
        # Note, though, that this implementation doesn't scale well because we are unable to bail early, because there
        # is no sense of time without a repository.  This implementation is basically a glorified demo.
        s = SeanoDataAggregator(self.config)
        for root, directories, filenames in os.walk(self.db_objs):
            for f in filenames:
                if f.endswith(SEANO_NOTE_EXTENSION):
                    f = os.path.join(root, f)
                    s.import_note(path=f, uid=self.extract_uid_from_filename(f))

        # Use the main database config file (seano-config.yaml) as a foundation for the query result structure.
        # Overwrite the entire `releases` member; the SeanoDataAggregator object contains all the juicy metadata contained
        # in the existing `releases` member in seano-config.yaml, so we're not losing any data by overwriting.
        result = dict(self.config)
        result['releases'] = s.dump()
        return result
