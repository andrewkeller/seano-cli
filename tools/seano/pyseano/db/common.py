"""
pyseano/db/common.py

Organizes a set of release notes, does some sanity checking, and serializes as Json
"""

from pyseano.db.schema_upgrade import upgrade_note_schema, upgrade_release_schema
from pyseano.utils import SeanoFatalError, list_if_not_already, ascii_str_type, unicode_str_type
import itertools
import logging
import sys
import yaml

log = logging.getLogger(__name__)


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


    def dump(self):
        # Start by using the releases dictionary as a template:
        release_dicts = structure_deep_copy(self.releases)

        # Inject each note into each release:
        for note in self.notes.values():

            # Clone so we can make edits:
            note = structure_deep_copy(note)

            # Declare notes to be part of the HEAD release when no release is specified:
            # (this is important for non-Git-backed databases; when the release is not
            # specified, the default is HEAD)
            if not note.get('releases'):
                note['releases'] = [self.current_version]

            # Convert all sets into lists with predictable sort orders:
            for k, v in note.items():
                if isinstance(v, set):
                    note[k] = sorted(list(v))

            # Append to each applicable release:
            for r in note['releases']:
                release_dicts[r]['notes'] = (release_dicts[r].get('notes', None) or []) + [note]

        # Doubly-link the before and after lists on each release:
        # Remember that these are associative arrays (lists of dictionaries), not lists of strings.
        for name, info in release_dicts.items():
            for before in info.get('before', []):
                self.assocary_generic_setattr(release_dicts[before['name']],
                                              "release_dicts['%s']" % (before['name'],),
                                              'after', True, [{'name': name}], 'name')
            for after in info.get('after', []):
                self.assocary_generic_setattr(release_dicts[after['name']],
                                              "release_dicts['%s']" % (after['name'],),
                                              'before', True, [{'name': name}], 'name')

        # Sort special keys in each release we care about:
        for name, info in release_dicts.items():
            info['before'] = sorted(info.get('before', []), key=lambda x: x['name'])
            info['after'] = sorted(info.get('after', []), key=lambda x: x['name'])
            info['notes'] = sorted(info.get('notes', []), key=lambda x: x['id'])

        # Remove all of the 'accepts_auto_' keys:
        def my_key_filter(k):
            if k.startswith('accepts_auto_'):
                return False
            return True
        release_dicts = structure_deep_copy(release_dicts, key_filter=my_key_filter)

        # Define a sort order for the releases:
        # ABK: This sort algorithm behaves a lot like Git does, and should be good enough in most
        #      cases.  If you're developing a fancy 2D graph of the releases, then the sort order
        #      doesn't matter at all, because you're going to manually read the before and after
        #      lists on each release to establish your topology.  For a more primitive 1D view
        #      (where everything is a flat list), having the list of releases pre-sorted in some
        #      sort of sane manner is handy, because it lets you just go down the list and print
        #      everything in order, despite the concept of non-linear graph flattening being
        #      somewhat non-trivial.
        #
        #      Because this algorithm is not tail-recursive, it will eventually overflow the
        #      stack when we build up enough releases.  Iterate as necessary.

        release_order = []
        releases_togo = set(release_dicts.keys())

        def get_release_order(release):

            # If this releas has already been visited, then return an empty list:
            if release['name'] not in releases_togo:
                return []

            # Mark this release as visited:
            releases_togo.remove(release['name'])

            # Get a list of all of our unvisited parents:
            parents = [x['name'] for x in release['after']]

            # Get release order for each of the parents, from left to right, without
            # repeating any ancestors:
            order = [get_release_order(release_dicts[x]) for x in parents]

            # Return this release name, followed by each of the parent lists, right-to-left:
            return [release['name']] + list(itertools.chain(*reversed(order)))

        release_order.extend(get_release_order(release_dicts[self.current_version]))

        # As a final fallback, dump the remaining unselected releases at the end:

        for x in sorted(list(releases_togo)):
            log.info('Having trouble flattening ancestry history: %s might be in the wrong position.', x)
            release_order.append(x)
            releases_togo.remove(x)

        # Flatten into a list in the oder we decided on earlier, and return:

        return [release_dicts[x] for x in release_order]


    # internal plumbing:


    def get_note(self, filename, uid):
        if uid not in self.notes:
            log.debug('Loading note %s from disk (from %s)', uid, filename)
            # Start with a template note containing the given information:
            data = {}
            self.generic_setattr(data, 'notes[' + uid + ']', 'id', True, uid)

            self.notes[uid] = data

            # Overwrite all members of the template with what exists on disk:
            try:
                with open(filename, 'r') as f:
                    for d in yaml.load_all(f, Loader=yaml.FullLoader):
                        for k, v in d.items():
                            self.note_setattr(filename, uid, k, False, v)

            except:
                log.error('Something exploded while trying to load a note from disk.  '
                          'We were trying to load the note with id %s, located at %s', uid, filename)
                raise

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

        if type(obj[key]) in [ascii_str_type, unicode_str_type]:
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
