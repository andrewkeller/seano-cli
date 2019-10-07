"""
pyseano/db/note_set.py
Organizes a set of release notes, does some sanity checking, and serializes as Json
"""
from pyseano.utils import list_if_not_already

import logging
import sys
import yaml

log = logging.getLogger(__name__)


class NoteSet(object):
    def __init__(self, current_version):
        self.current_version = current_version
        self.releases = {}
        self.release_order = []

    def with_release(self, name):
        if name not in self.releases:
            self.releases[name] = {
                'before': [],
                'after': [],
                'notes': [],
            }
            self.release_order.append(name)
        return self.releases[name]

    def load_version_info(self, releases):
        index = -1
        for r in releases:
            index = index +1
            name = r.get('name', None)
            if not name:
                log.error("fatal: no name set on releases[%d]", index)
                sys.exit(1)

            # update() doesn't merge lists; pull out the obvious keys and do them manually

            before = []
            if 'before' in r:
                before = list_if_not_already(r.get('before', []))
                del r['before']

            after = []
            if 'after' in r:
                after = list_if_not_already(r.get('after', []))
                del r['after']

            notes = []
            if 'notes' in r:
                notes = list_if_not_already(r.get('notes', []))
                del r['notes']

            # Bulk-update the release info:
            self.with_release(name).update(r)

            # Manually update complex info that update() doesn't do for us nicely:

            for x in before:
                self.set_version_ordering(name, before=x)
            for x in after:
                self.set_version_ordering(name, after=x)
            for x in notes:
                self.attach_note(name, x)

    def set_version_ordering(self, base, before=None, after=None):
        # For sanity/QA, do not have two implementations; rather, swap inputs if needed
        if before:
            after = base
            base = before
        # Save the base/after relationship (bi-directional)
        self.with_release(base)['after'].append(after)
        self.with_release(after)['before'].append(base)
        # Adjust release ordering to match:
        bx = self.release_order.index(base)
        ax = self.release_order.index(after)
        if ax < bx:
            del self.release_order[bx]
            self.release_order.insert(ax, base)

    def attach_note(self, name, note):
        self.with_release(name)['notes'].append(note)

    def load_note(self, path, uid):
        data = {'id': uid}
        with open(path, 'r') as f:
            for d in yaml.load_all(f, Loader=yaml.FullLoader):
                data.update(d)
        releases = list_if_not_already(data.get('releases', [])) or [self.current_version]
        if 'releases' in data: del data['releases']
        for r in releases:
            self.attach_note(r, data)

    def sort_notes(self):
        # ABK: This algorithm is dependent on accessing the releases data by reference.
        for r in self.releases.values():
            r['notes'].sort(key=lambda x: x.get('id', None))

    def dump(self):
        self.sort_notes()
        return [self.releases[x] for x in self.release_order]
