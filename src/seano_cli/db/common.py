"""
seano_cli/db/common.py

Organizes a set of release notes, does some sanity checking, and serializes as Json
"""

from seano_cli.constants import SEANO_NOTE_KEY_IS_GHOST
from seano_cli.db.release_sorting import sorted_release_names_from_releases
from seano_cli.db.schema_upgrade import upgrade_note_schema, upgrade_release_schema
from seano_cli.utils import FILE_ENCODING_KWARGS, SeanoFatalError, list_if_not_already, ascii_str_type, unicode_str_type
import logging
import os
import re
import sys
import yaml

log = logging.getLogger(__name__)


class AttemptToLoadGhostNote(Exception):
    pass


def structure_deep_copy(src, key_filter=lambda _: True):
    if isinstance(src, list):
        return [structure_deep_copy(x, key_filter=key_filter) for x in src]
    if isinstance(src, set):
        return set([structure_deep_copy(x, key_filter=key_filter) for x in src])
    if isinstance(src, dict):
        return {k: structure_deep_copy(v, key_filter=key_filter) for k, v in src.items() if key_filter(k)}
    if isinstance(src, ascii_str_type):
        return ascii_str_type(src)
    if isinstance(src, unicode_str_type):
        return unicode_str_type(src)
    if src is None or isinstance(src, bool):
        return src
    raise SeanoFatalError('structure_deep_copy: unsupported value of type %s: %s' % (type(src).__name__, src))


class SeanoDataAggregator(object):
    def __init__(self, config):
        # Define structures to store data as we assemble things.
        # Releases and notes are stored separately because they are associated N:N, and they each receive
        # incremental updates throughout the load process.  When an information fragment comes in, we want
        # to be able to apply it quickly and easily, without needing to search.  Notes are injected into
        # releases at the last minute, right before dump() returns.
        self.releases = {}
        self.notes = {}

        # Use the given config to import (pre-populate) anything hard-coded.

        # Declare the current version:
        self.current_version = config['current_version'] # must exist or else explode
        self.get_release(self.current_version)

        # Import all manually configured release ancestors of HEAD:
        # (This is usually only applicable in non-SCM-backed seano databases)
        if 'parent_versions' in config:
            self.release_setattr(self.current_version, 'after', False, config['parent_versions'])

        # Import all manually declared releases:
        index = -1
        for r in config.get('releases') or []:
            index = index +1

            if r.get('delete', False):
                # This release has been deleted; pretend it does not exist.
                continue

            name = r.get('name', None)
            if not name:
                raise SeanoFatalError("no name set on releases[%d]" % (index,))

            for k, v in r.items():
                self.release_setattr(name, k, False, v)


    def import_release_info(self, name, **automatic_attributes):
        for k, v in automatic_attributes.items():
            self.release_setattr(name, k, True, v)

    def import_note(self, path, uid, **automatic_attributes):
        try:
            if not automatic_attributes:
                # note_setattr() (below) invokes get_note() under-the-hood, which means that
                # simply setting an automatic attribute will load the note from disk first.
                # When no automatic attributes exist, the loop doesn't run.  In this case,
                # manually invoke get_note(), discarding the result, to ensure that the note
                # file was loaded, which is the whole point of this function.
                self.get_note(path, uid)
                return

            for k, v in automatic_attributes.items():
                self.note_setattr(path, uid, k, True, v)

        except AttemptToLoadGhostNote:
            pass


    def dump(self):
        # Clone the notes structure, so we can make changes without making this method non-re-entrant-safe:
        note_dicts = structure_deep_copy(self.notes)

        # Also clone the releases structure, for the same reason:
        release_dicts = structure_deep_copy(self.releases)

        # In the course of the dump() method, we patch the output in ways that both (a) require the release
        # ancestry graph to be properly doubly-linked, and (b) introduces new data that forces us to
        # re-doubly-link the ancestry graph.  Thus, this process has to be reusable.
        def doubly_link():

            # Doubly-link the before and after lists on each release:
            # Remember that these are associative arrays (lists of dictionaries), not lists of strings.
            def ancestry_mirroring_key_filter(key):
                # When doubly-linking release ancestries, only mirror these keys across either side of the link:
                return key in ['delete']

            for name, info in release_dicts.items():
                for before in info.get('before', []):
                    ancestry_data = structure_deep_copy(before, key_filter=ancestry_mirroring_key_filter)
                    ancestry_data['name'] = name
                    self.assocary_generic_setattr(release_dicts[before['name']],
                                                  "release_dicts['%s']" % (before['name'],),
                                                  'after', True, [ancestry_data], 'name')
                for after in info.get('after', []):
                    ancestry_data = structure_deep_copy(after, key_filter=ancestry_mirroring_key_filter)
                    ancestry_data['name'] = name
                    self.assocary_generic_setattr(release_dicts[after['name']],
                                                  "release_dicts['%s']" % (after['name'],),
                                                  'before', True, [ancestry_data], 'name')
        doubly_link()

        # Auto-create backstories when `auto-wrap-in-backstory` is set on a release:
        def auto_create_backstories_for_auto_wrapped_release(release, seen):
            # Bail if we've already been here:
            if release in seen: return
            # Declare that we've been here:
            seen.add(release)
            # Process all parents first:  **(we haven't pruned deleted releases yet!)**
            for after in [x for x in release_dicts[release].get('after', []) if not x.get('delete')]:
                auto_create_backstories_for_auto_wrapped_release(after['name'], seen)
            # Bail if this release does not have `auto-wrap-in-backstory` set:
            if not release_dicts[release].get('auto-wrap-in-backstory'): return
            # Okay!  This is an auto-wrapped release.  Set up new ancestries to declare
            # this release as a backstory of this release's descendants:
            #  **(we haven't pruned deleted releases yet!)**
            ancestors = [x['name'] for x in release_dicts[release].get('after', []) if
                not x.get('delete') and not x.get('is-backstory')]
            for before in [x for x in release_dicts[release].get('before', []) if not x.get('delete')]:

                rbefore = release_dicts[before['name']]

                # If the link from `before` to `release` already has `is-backstory` set, then bail:
                if any([x.get('is-backstory') for x in rbefore.get('after', []) if x['name'] == release]):
                    log.debug('Warning: Refusing to auto-wrap %s in a backstory merging into %s because '
                              'the ancestry link from %s to %s is already a backstory',
                              release, before['name'], before['name'], release)
                    continue

                self.assocary_generic_setattr(rbefore,
                                              "release_dicts['%s']" % (before['name'],),
                                              'after', True, [{'name': release, 'is-backstory': True}], 'name')
                # ABK: This line in particular is what forces us to need to re-doubly-link everything.
                self.assocary_generic_setattr(rbefore,
                                              "release_dicts['%s']" % (before['name'],),
                                              'after', True, [{'name': x} for x in ancestors], 'name')
        seen = set()
        for release in release_dicts.keys():
            auto_create_backstories_for_auto_wrapped_release(release, seen)

        # The auto-created backstories require us to re-doubly-link everything:
        doubly_link()

        # Now that all release ancestry links marked for deletion have been marked for deletion on both ends,
        # do another sweep through the entire ancestry graph, deleting ancestry links marked for deletion:
        for info in release_dicts.values():
            info['before'] = [x for x in info.get('before', []) if not x.get('delete', False)]
            info['after'] = [x for x in info.get('after', []) if not x.get('delete', False)]

        # Calculate backstory forwarding for each release:
        backstory_forwards = {}

        def list_lineage(release_name):
            '''Lists all parents of the given release, without risk of an infinite loop'''
            todo = [release_name]
            result = []
            while todo:
                todo, x = todo[1:], todo[0]
                for y in release_dicts[x].get('after') or []:
                    y = y['name']
                    if y not in result and y not in todo:
                        todo.append(y)
                result.append(x)
            return result

        for release in release_dicts.values():
            all_after = release.get('after') or []
            # Order is important here.  We want to paint all ancestors reachable only by a backstory
            # ancestry link, and then un-paint all ancestors reachable by any non-backstory ancestry
            # link -- in that order.  When painting and un-painting has completed, we will then have
            # a literal map of when we need to forward notes.  (search for usages of backstory_forwards
            # to see when this knowledge is used)
            bs_after = [x for x in all_after if x.get('is-backstory', False)]
            gm_after = [x for x in all_after if not x.get('is-backstory', False)]
            for after in bs_after:
                for x in list_lineage(after['name']):
                    backstory_forwards[x] = backstory_forwards.get(x, set()) | set([release['name']])
            for after in gm_after:
                for x in list_lineage(after['name']):
                    backstory_forwards[x] = backstory_forwards.get(x, set()) - set([release['name']])

        log.debug('Backstory forwards: %s', backstory_forwards)

        # Inject each note into each release:
        for note in note_dicts.values():

            # Declare notes to be part of the HEAD release when no release is specified:
            # (this is important for non-Git-backed databases; when the release is not
            # specified, the default is HEAD)
            if not note.get('releases'):
                note['releases'] = [self.current_version]

            # Convert all sets into lists with predictable sort orders:
            for k, v in note.items():
                if isinstance(v, set):
                    note[k] = sorted(list(v))

            # Append this note to each release when this change was first released:
            for r in note['releases']:
                # Add to releases where this note was created:
                release_dicts[r]['notes'] = (release_dicts[r].get('notes') or []) + [note]

            # Append this note to each release that is a termination of a relevant backstory:
            note = dict(note) # Copy so that we can make changes
            note['is-copied-from-backstory'] = True
            backstory_targets = set()
            for r in note['releases']:
                backstory_targets = backstory_targets | backstory_forwards.get(r, set())
            for p in backstory_targets:
                release_dicts[p]['notes'] = (release_dicts[p].get('notes') or []) + [note]

        # Sort special keys in each release we care about:
        def ancestry_sort_key(x):
            return (
                x.get('is-backstory', False),
                x['name'],
            )
        def note_sort_key(x):
            return (
                x.get('relative-sort-string') or x['id'], # Missing, empty, or None-ish falls back to the note ID
                x['id'], # Break ties using the note ID (for when sort strings are identical)
            )
        for name, info in release_dicts.items():
            info['before'] = sorted(info.get('before', []), key=ancestry_sort_key)
            info['after'] = sorted(info.get('after', []), key=ancestry_sort_key)
            info['notes'] = sorted(info.get('notes', []), key=note_sort_key)

        # Remove all of the 'accepts_auto_' keys:
        def my_key_filter(k):
            if k.startswith('accepts_auto_'):
                return False
            return True
        release_dicts = structure_deep_copy(release_dicts, key_filter=my_key_filter)

        # Return the list of releases, in an idealized sort order:
        return [release_dicts[x] for x in sorted_release_names_from_releases(release_dicts)]

    # internal plumbing:


    _extern_id_path_regex = re.compile(r'\.extern\-(?P<name>.+)\.yaml$')
    def get_note(self, filename, uid):
        if uid not in self.notes:
            log.debug('Loading note %s from disk (from %s)', uid, filename)
            # Start with a template note containing the given information:
            data = {}
            self.generic_setattr(data, 'notes[' + uid + ']', 'id', True, uid)
            m = self._extern_id_path_regex.search(os.path.basename(filename))
            if m:
                self.generic_setattr(data, 'notes[' + uid + ']', 'x-seano-extern-identifier', True, m.group('name'))

            self.notes[uid] = data

            # Overwrite all members of the template with what exists on disk:
            try:
                with open(filename, 'r', **FILE_ENCODING_KWARGS) as f:
                    for d in yaml.load_all(f, Loader=yaml.FullLoader):
                        for k, v in d.items():
                            self.note_setattr(filename, uid, k, False, v)

            except:
                log.error('Something exploded while trying to load a note from disk.  '
                          'We were trying to load the note with id %s, located at %s', uid, filename)
                raise

            # If this is a ghost note, then torch the note we just created, and
            # notify the caller to stop whatever it was doing before we got here:
            if data.get(SEANO_NOTE_KEY_IS_GHOST, False):
                del self.notes[uid]
                raise AttemptToLoadGhostNote()

        return self.notes[uid]


    def get_release(self, name):
        if name not in self.releases:
            self.releases[name] = dict(name=name)
        return self.releases[name]


    def note_setattr(self, filename, uid, key, is_auto, value):
        value = upgrade_note_schema(key, value)
        # ABK: At this time, all keys are flat; we can use generic_setattr() for everything.
        self.generic_setattr(self.get_note(filename, uid), "notes['%s']" % (uid,), key, is_auto, value)


    def release_setattr(self, name, key, is_auto, value):
        value = upgrade_release_schema(key, value)
        if key in ['notes']:
            log.error('''this API does not yet support setting notes.  feature request?''')
            explode
        if key in ['before', 'after']:
            # These keys are associative arrays.
            self.assocary_generic_setattr(self.get_release(name), "release['%s']" % (name,),
                                          key, is_auto, value, 'name')
            return
        self.generic_setattr(self.get_release(name), "release['%s']" % (name,), key, is_auto, value)


    def generic_setattr(self, obj, obj_desc, key, is_auto, value):
        '''
        Conceptually, setattr(), except with the ability to distinguish/discriminate between automatic/manual values.

        This new fancy version supports rejecting automatic changes if a manual value already exists.

        However, if a manual value already exists and you try to set a manual value again, or if an
        automatic value already exists and you try to set an automatic value again, the value will
        be merged if possible.

        If you try to set a manual value and an automatic value already exists, the automatic value is
        erased and the manual value is set.
        '''

        if key not in obj:
            # New attribute to set doesn't exist at all.  Import it blindly.
            obj[key] = value
            obj['accepts_auto_' + key] = is_auto
            return

        if key not in ['notes']:
            # ^^ some keys bypass the "accepts auto" concept, in favor of guaranteeing data is never lost.
            # The penalty, though, is that you can't *remove* values automatically gathered by simply
            # "overriding" the parent object in seano-config.yaml.

            if is_auto and not obj.get('accepts_auto_' + key, True):
                # New attribute to set is auto, and existing attribute already set is manual.
                # No matter what, this update is silently rejected.  We disallow updating a
                # manually set value with an automatically set one.
                return

            if not is_auto and obj.get('accepts_auto_' + key, True):
                # New attribute to set is manual, and existing attribute already set is
                # automatic.  Just this once, wipe out the automatic value, and replace
                # it with the manual value.
                obj[key] = value
                obj['accepts_auto_' + key] = is_auto
                return

        # is_auto matches, and the attribute is already set.
        # Ugh.  We have to do a merge.

        if type(obj[key]) != type(value):
            raise SeanoFatalError("cannot merge different types %s (%s) and %s (%s) on %s['%s']"
                                 % (type(obj[key]), obj[key], type(value), value, obj_desc, key))

        if type(obj[key]) in [list]:
            obj[key] = obj[key] + value
            return

        if type(obj[key]) in [set]:
            obj[key] = obj[key] | value
            return

        if type(obj[key]) in [ascii_str_type, unicode_str_type, bool]:
            obj[key] = value
            return

        raise SeanoFatalError("cannot merge unknown type %s (%s + %s) on %s['%s']"
                             % (type(obj[key]), obj[key], value, obj_desc, key))


    def assocary_generic_setattr(self, obj, obj_desc, key, is_auto, value, inner_key):
        '''
        Merges the given value into the given object, assuming that the value is an associative array.
        Associative arrays are, in this context, lists of dictionaries.  The given inner key is used to
        match dictionaries in obj and value.

        Once matching dictionaries are identified, generic_setattr() is used to merge all of the keys.
        '''
        if key not in obj:
            # The associative array doesn't exist yet.  Create a new one, and let the merging logic
            # (below) fill in the elements:
            obj[key] = []

        dest_assocary = obj[key]
        src_assocary = value

        if not isinstance(value, list):
            raise SeanoFatalError('value provided is not an associative array: %s' % (value,))

        for src_element in src_assocary:

            # Fetch the destination element corresponding with this source element:

            dest_element = list(filter(lambda x: x.get(inner_key) == src_element.get(inner_key), dest_assocary))

            if len(dest_element) > 1:
                raise SeanoFatalError("cannot merge associative array element %s['%s'][%s='%s'] because it is ambiguous"
                                     % (obj_desc, key, inner_key, src_element.get(inner_key)))

            if len(dest_element) < 1:
                # No match; create the element so that we can perform a merge:
                dest_element = [{}]
                dest_assocary.append(dest_element[0])

            dest_element = dest_element[0]

            for x in src_element.keys():
                self.generic_setattr(dest_element,
                                     "%s['%s'][%s='%s']" % (obj_desc, key, inner_key, src_element.get(inner_key)),
                                     x, is_auto, src_element[x])
