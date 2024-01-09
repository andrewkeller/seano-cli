"""
seano_cli/db/generic.py

Base class for the different kinds of seano databases
"""

from seano_cli.db.common import SeanoDataAggregator
from seano_cli.db.schema_upgrade import upgrade_root_object_schema
from seano_cli.utils import *
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
        def load_file(cfg, is_failure_suggestive_of_repo_missing):
            try:
                with open(cfg, 'r', **FILE_ENCODING_KWARGS) as f:
                    for d in yaml.load_all(f, Loader=yaml.FullLoader):
                        # An empty section in yaml yields None here.
                        # Although it's weird (wrong?) to have an empty section
                        # in a yaml file in seano, let's not crash, either.
                        if not d:
                            continue
                        d = upgrade_root_object_schema(d)
                        self.config.update(d)
            except IOError as e:
                if e.errno != errno.ENOENT:
                    raise SeanoFatalError("unusual error while trying to read %s: %s" % (cfg, e))
                if is_failure_suggestive_of_repo_missing:
                    raise SeanoFatalError('%s does not exist.  Is this a seano database?' % (cfg,))
                raise SeanoFatalError('%s does not exist.' % (cfg,))

        if config_annex_path:
            load_file(config_annex_path, False)
        load_file(os.path.join(path, SEANO_CONFIG_FILE), True)

        # Possibly overwrite some database configurations if they were provided to this constructor:

        if not self.config.get('current_version', None):
            self.config['current_version'] = 'HEAD'

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

        1. its relative path from inside the SEANO_DB_SUBDIR folder
        2. with the file extension(s) hacked off the end
        3. and all slashes removed

        Invoking this function with any file that is not a "proper" note file for the
        seano database currently referenced by this database object results in undefined
        behavior.
        '''
        result = os.path.basename(filename)
        result = os.path.splitext(result)[0] # [2]  .yaml
        result = os.path.splitext(result)[0] # [2]  .extern-xxxx (if exists)

        while True:
            filename = os.path.dirname(filename) # [1]
            component = os.path.basename(filename) # [1]
            if component == SEANO_DB_SUBDIR: break # [3]
            if not component: raise SeanoFatalError('Attempt to operate on a note file not inside a seano database')
            result = component + result # [3]

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

    def import_extern_notes(self, is_dry_run, db_defs):
        if not db_defs:
            return [] # No local paths updated

        # Ensure that the list of extern IDs is unique:
        if len(set([id for id, _ in db_defs])) != len(db_defs):
            raise SeanoFatalError('List of extern IDs is not unique.')

        # Ensure that the list of extern databases is unique:
        if len(set([self.path] + [db_path for _, db_path in db_defs])) != len(db_defs) + 1:
            raise SeanoFatalError('List of extern database paths is not unique.')

        # Construct a list of all full note file extensions we're looking for.
        # These file extensions will be used to identify extraneous notes.
        # In particular, we are NOT assuming that the db_defs list is the full
        # list of all extern modules that exist, which means that NOT all
        # extern notes are candidates for deletion.  (For example, if a
        # submodule was deleted, we want to explicitly keep those notes.)
        extensions_by_id = {
            id: SEANO_EXTERN_NOTE_EXTENSION_PREFIX + id + SEANO_NOTE_EXTENSION
            for id, _ in db_defs
        }

        # Build up a list of note IDs that are candidates for deletion, and
        # also a list of all the extern identifiers that are currently active:
        extraneous = {}
        extern_id_used_previously = {}
        for root, directories, filenames in os.walk(self.db_objs):
            for f in filenames:
                for id, ext in extensions_by_id.items():
                    if f.endswith(ext):
                        note_path = os.path.join(root, f)
                        extraneous[self.extract_uid_from_filename(note_path)] = note_path
                        extern_id_used_previously[id] = True
                        break

        # Build up a list of remote paths that need to be copied.
        # And for each of these paths, remove them from `extraneous`.
        todo = []
        extern_id_now_used = {}
        for other_db_id, other_db_dir in db_defs:
            other_db_objs = os.path.join(other_db_dir, SEANO_DB_SUBDIR)
            for root, directories, filenames in os.walk(other_db_objs):
                for f in filenames:
                    if f.endswith(SEANO_NOTE_EXTENSION) and SEANO_EXTERN_NOTE_EXTENSION_PREFIX not in f:
                        full_path = os.path.join(root, f)
                        todo.append((full_path, other_db_id))
                        extern_id_now_used[other_db_id] = True

                        # Oh, and don't delete these files:
                        extraneous[self.extract_uid_from_filename(full_path)] = False

        # Flatten extraneous:
        extraneous = [v for _, v in extraneous.items() if v]

        # Mine used ids for newly used ids:
        new_extern_identifiers = [
            (id, db_path)
            for id, db_path in db_defs
            if id in extern_id_now_used and id not in extern_id_used_previously
        ]

        touched_files = []

        # Import each of the discovered files:
        for f, id in todo:
            touched_files.append(self.import_extern_note(f, id, is_dry_run))

        # Delete each extraneous note:
        for f in extraneous:
            touched_files.append(self.delete_note(f, is_dry_run=is_dry_run))

        if new_extern_identifiers:
            sys.stderr.write('''
NOTICE: It looks like you're importing notes from one or more
extern seano databases for the first time.

    - If you want all of these notes to show up as current changes
      in the current version of your project, then you have nothing
      to do.  Carry on.

    - If some of these notes are not relevant to the current version
      of your project, you may want to consider ghosting some or all
      of these notes so that they don't show up as changes in the
      current version of your project.
''')
            for id, db_path in new_extern_identifiers:
                sys.stderr.write('''
To ghost all currently imported notes from %s, run:

    seano ghost --extern-id %s
''' % (os.path.relpath(db_path), id))

            sys.stderr.write('''
Ghosting notes now does not impact any notes imported in the future.
''')

        # Return a list of all touched files:
        return [x for x in touched_files if x]

    def import_extern_note(self, extern_note_file, extern_identifier, is_dry_run):
        # Construct the file path where the imported note will live:
        id = self.extract_uid_from_filename(extern_note_file)
        local_path = self.make_note_filename_from_uid(id)
        local_path = os.path.splitext(local_path)
        local_path = (SEANO_EXTERN_NOTE_EXTENSION_PREFIX + extern_identifier).join(local_path)

        meta = {}
        status = 'A'

        if os.path.exists(local_path):
            # We already have a copy of the note on disk.
            # Load its extern metadata (the first hunk in the YAML):
            status = 'M'

            def load_extern_meta():
                with open(local_path, 'r', **FILE_ENCODING_KWARGS) as f:
                    for d in yaml.load_all(f, Loader=yaml.FullLoader):
                        # Skip over any empty sections
                        if not d: continue
                        # Return the first non-empty section:
                        return d
            meta = load_extern_meta()

            # If this is a ghost note, then do not overwrite it:
            if meta.get(SEANO_NOTE_KEY_IS_GHOST, False):
                log.debug('Importing %s: already imported as a ghost', extern_note_file)
                return None

        with open(extern_note_file, 'r', **FILE_ENCODING_KWARGS) as f:
            data = f.read()

        old_data_hash = meta.get(SEANO_NOTE_KEY_SHA1_OF_ORIGINAL_NOTE)
        if old_data_hash:
            if old_data_hash == h_data(data):
                log.debug('Importing %s: already imported and up-to-date', extern_note_file)
                return None

        if is_dry_run:
            log.info('Would import %s', extern_note_file)
            return status, local_path

        log.debug('Importing %s', extern_note_file)
        write_existing_file(local_path, '\n'.join([
            '---',
            '%s: %s' % (
                SEANO_NOTE_KEY_RELPATH_TO_ORIGINAL_NOTE,
                os.path.relpath(extern_note_file, self.path).replace('\\', '/'),
            ),
            '%s: %s' % (
                SEANO_NOTE_KEY_SHA1_OF_ORIGINAL_NOTE,
                h_data(data),
            ),
            '',
            '######## NOTICE ########',
            '# This note is a *copy* of a note from an external database.',
            '# You probably want to edit the original rather than this',
            '# copy, so that other projects inherit your change.',
            data,
        ]))

        return status, local_path

    def get_notes_with_extern_id(self, extern_id):
        # How do we identify notes with this extern ID?
        extension = SEANO_EXTERN_NOTE_EXTENSION_PREFIX + extern_id + SEANO_NOTE_EXTENSION
        # Go find them:
        results = []
        for root, directories, filenames in os.walk(self.db_objs):
            for f in filenames:
                if f.endswith(extension):
                    results.append(os.path.join(root, f))
        return results

    def delete_note(self, note_file, is_dry_run):
        if is_dry_run:
            log.info('Would delete %s', note_file)
            return 'D', note_file
        try:
            os.remove(note_file)
            return 'D', note_file
        except FileNotFoundError:
            pass
        return None

    def is_ghost(self, note_file):
        with open(note_file, 'r', **FILE_ENCODING_KWARGS) as f:
            for d in yaml.load_all(f, Loader=yaml.FullLoader):
                # Skip over any empty sections
                if not d: continue
                # Interrogate the first non-empty section:
                return d.get(SEANO_NOTE_KEY_IS_GHOST, False)

    def ghost_note(self, note_file, is_dry_run):

        def load_extern_meta(path):
            with open(path, 'r', **FILE_ENCODING_KWARGS) as f:
                for d in yaml.load_all(f, Loader=yaml.FullLoader):
                    # Skip over any empty sections
                    if not d: continue
                    # Return the first non-empty section:
                    return d
        meta = load_extern_meta(note_file)

        if meta.get(SEANO_NOTE_KEY_IS_GHOST, False):
            log.info('Is already a ghost: %s', note_file)
            return None

        if is_dry_run:
            log.info('Would ghost: %s', note_file)
            return 'M', note_file

        write_existing_file(note_file, '\n'.join([
            '---',
            ] + [x for x in ['%s: %s' % (
                SEANO_NOTE_KEY_RELPATH_TO_ORIGINAL_NOTE,
                meta.get(SEANO_NOTE_KEY_RELPATH_TO_ORIGINAL_NOTE),
            )] if SEANO_NOTE_KEY_RELPATH_TO_ORIGINAL_NOTE in meta] + [
            '%s: true' % (
                SEANO_NOTE_KEY_IS_GHOST,
            ),
            '',
        ]))

        return 'M', note_file

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
