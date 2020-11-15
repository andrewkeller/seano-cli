"""
pyseano/db/common.py

Organizes a set of release notes, does some sanity checking, and serializes as Json
"""

from pyseano.utils import list_if_not_already, ascii_str_type, unicode_str_type
import logging
import sys
import yaml

log = logging.getLogger(__name__)


class SeanoDataAggregator(object):
    def __init__(self, config):
        self.releases = {}  # Releases *do not* contain notes (unless hard-coded in seano-config.yaml)
        self.notes = {}     # Notes mention releases *by name*

        # Use the given config to import (pre-populate) anything hard-coded.

        # Declare the current version:
        self.current_version = config['current_version'] # must exist or else explode
        self.get_release(self.current_version)

        # Possibly add manually-configured release ancestors on the current version:
        # (This is usually only applicable in non-SCM-backed seano databases)
        if 'parent_versions' in config:
            self.release_setattr(self.current_version, 'after', False, set(config['parent_versions']))
            for p in config['parent_versions']:
                self.release_setattr(p, 'before', False, set([self.current_version]))

        # Import all manually declared releases:
        self.load_manual_releases(config.get('releases', None) or [])


    def import_automatic_release_info(self, name, **automatic_attributes):
        for k, v in automatic_attributes.items():
            self.release_setattr(name, k, True, v)

    def import_automatic_note(self, path, uid, **automatic_attributes):
        for k, v in automatic_attributes.items():
            self.note_setattr(path, uid, k, True, v)


    def dump(self):
        # Assemble each release for returning, pruning private data out as we go:
        release_dicts = {}
        for name, info in self.releases.items():

            # Clone so we can make edits:
            info = dict(info)

            # Remove all accepts_auto_* keys:
            for k in [x for x in info.keys() if x.startswith('accepts_auto_')]:
                del info[k]

            # Also clone each individual note so we can make edits:
            info['notes'] = [dict(x) for x in info.get('notes', None) or []]

            # Remove all accepts_auto_* keys from each note:
            for note in info['notes']:
                for k in [x for x in note.keys() if x.starts('accepts_auto_')]:
                    del note[k]

            release_dicts[name] = info

        # Inject each note into each release:
        for note in self.notes.values():

            # Clone so we can make edits:
            note = dict(note)

            # Remove all accepts_auto_* keys:
            for k in [x for x in note.keys() if x.startswith('accepts_auto_')]:
                del note[k]

            # Sort/sanitize special keys in each note we care about:
            if 'commits' in note:
                note['commits'] = sorted(list(note['commits']))
            note['releases'] = sorted(list(note.get('releases', None) or [self.current_version]), reverse=True) # [1]

            #  [1]  Note that the `or` clause here is important for non-Git-backed databases; when releases are not
            #       specified, the default is HEAD.  Also, if a change doesn't have a release, then the world explodes.

            # Append to each applicable release:
            for r in note['releases']:
                release_dicts[r]['notes'] = (release_dicts[r].get('notes', None) or []) + [note]

        # Doubly-link the before and after lists on each release:
        for name, info in release_dicts.items():
            for before in info.get('before', set()):
                release_dicts[before]['after'] = release_dicts[before].get('after', set()) | set([name])
            for after in info.get('after', set()):
                release_dicts[after]['before'] = release_dicts[after].get('before', set()) | set([name])

        # Sort special keys in each release we care about:
        for name, info in release_dicts.items():
            info['before'] = sorted(list(info.get('before', set())), reverse=True)
            info['after'] = sorted(list(info.get('after', set())), reverse=True)
            info['notes'] = sorted(info.get('notes', []), key=lambda x: x.get('id', None))

        # Define a sort order for the releases:
        # ABK: This isn't a terribly great sort algorithm, but it should be fine in most cases.
        #      If you're developing a 2D graph of the releases, then the sort order doesn't matter
        #      at all, because you're going to use the before and after lists to reorder everything
        #      anyways.  For a more common view, where everything is a flat list, having the list
        #      of releases be sorted correctly by default is handy, because it lets you just go down
        #      the list and print everything in order.  However, because the graph is 2D in reality,
        #      "making a list" is setting yourself up for failure.  Sooner or later, someone is going
        #      to come up with a commit graph that doesn't play well with this algorithm.  When that
        #      happens, iterate as necessary.

        release_order = []
        releases_togo = set(release_dicts.keys())

        release_order.append(self.current_version)
        releases_togo.remove(self.current_version)

        while releases_togo:
            found_something = False
            for possibility in release_dicts[release_order[-1]].get('after', set()):
                if possibility in releases_togo:
                    log.debug('Identified next oldest release: %s', possibility)
                    release_order.append(possibility)
                    releases_togo.remove(possibility)
                    found_something = True
            if found_something: continue
            possibility = sorted(list(releases_togo), reverse=True)[0]
            log.info('Having trouble flattening ancestry history: %s might be in the wrong position.', possibility)
            release_order.append(possibility)
            releases_togo.remove(possibility)

        # Flatten into a list in the oder we decided on earlier, and return:

        return [release_dicts[x] for x in release_order]


    # internal plumbing:


    def load_manual_releases(self, releases):
        index = -1
        for r in releases:
            index = index +1

            if r.get('delete', False):
                # This release has been deleted; pretend it does not exist.
                continue

            name = r.get('name', None)
            if not name:
                log.error("fatal: no name set on releases[%d]", index)
                sys.exit(1)

            for key, value in r.items():
                self.release_setattr(name, key, False, value)


    def get_note(self, filename, uid):
        if uid not in self.notes:
            log.debug('Loading note %s from disk (from %s)', uid, filename)
            # Start with a template note containing the given information:
            data = {
                'id': uid,
            }

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
        if key in ['commits', 'releases']:
            if not value:
                # An empty list in Yaml shows up as None here.
                # This auto-corrects anything False-ish into an empty set.
                value = set()
            else:
                # For convenience, we let you enter single strings instead
                # of forcing you to use the list syntax in Yaml all the time.
                # For algorithm similicity here, standardize on a formal set.
                value = set(list_if_not_already(value))
        self.generic_setattr(self.get_note(filename, uid), "notes['%s']" % (uid,), key, is_auto, value)


    def release_setattr(self, name, key, is_auto, value):
        if key in ['notes']:
            log.error('''releases should never directly set notes (that's done during the dump stage)''')
            explode
        if key in ['before', 'after']:
            if not value:
                # An empty list in Yaml shows up as None here.
                # This auto-corrects anything False-ish into an empty set.
                value = set()
            else:
                # For convenience, we let you enter single strings instead
                # of forcing you to use the list syntax in Yaml all the time.
                # For algorithm similicity here, standardize on a formal set.
                value = set(list_if_not_already(value))
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
            # "overriding" them in seano-config.yaml.

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
            log.error("fatal: cannot merge different types %s (%s) and %s (%s) on %s['%s']",
                      type(obj[key]), obj[key], type(value), value, obj_desc, key)
            sys.exit(1)

        if type(obj[key]) in [list]:
            obj[key] = obj[key] + value
            return

        if type(obj[key]) in [set]:
            obj[key] = obj[key] | value
            return

        if type(obj[key]) in [ascii_str_type, unicode_str_type]:
            obj[key] = value
            return

        log.error("fatal: cannot merge unknown type %s (%s + %s) on %s['%s']",
                  type(obj[key]), obj[key], value, obj_desc, key)
        sys.exit(1)
