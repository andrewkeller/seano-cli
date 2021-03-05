"""
pyseano/db/schema_upgrade.py

As it turns out, updating schemas is complicated enough that it mucks up other files.
So to make other code readable, we've taken all of the horror and collected it here.
"""

from pyseano.utils import SeanoFatalError, ascii_str_type, unicode_str_type
import logging

log = logging.getLogger(__name__)


def validate_is_string_or_none(value):
    if value is None:
        return value
    if isinstance(value, (ascii_str_type, unicode_str_type)):
        return value
    raise SeanoFatalError('expected string or None but found %s' % (value,))


def convert_hlist_rst_to_rst(value):
    '''
    If the given value looks like rst, then the given value is returned as-is.

    Else, if the given value looks like hlist-rst, then the value is converted
    to flat rst, and the result is returned.

    Else, an exception is raised.

    ABK: Refer to the usage of this function for an architecture discussion.
    '''
    if isinstance(value, (ascii_str_type, unicode_str_type)):
        # This value is already a flat string (not an hlist).  Return as-is.
        return value
    if isinstance(value, list):
        # This value is an hlist of some kind.  Flatten it into a string, assuming
        # that the rich text markup being used is reStructuredText.

        # The top layer of hlist elements become paragraphs in reStructuredText,
        # and the next layer in becomes the new root of newer, smaller hierarchical
        # lists, formatted in reStructuredText.

        def flatten(v, level=0):
            if not v:
                yield level, None
                return
            if isinstance(v, (ascii_str_type, unicode_str_type)):
                yield level, v
                return
            if isinstance(v, list):
                for e in v:
                    for x in flatten(e, level):
                        yield x
                return
            if isinstance(v, dict):
                for head, inner in v.items():
                    yield level, head
                    for x in flatten(inner, level + 1):
                        yield x
                return
            raise SeanoFatalError('unsupported hlist value: %s' % (v,))

        def serialize():
            previousLevel = None
            for level, txt in flatten(value):
                if not txt:
                    continue
                if not level or level != previousLevel:
                    yield '\n'
                previousLevel = level
                if level:
                    yield '  ' * (level -1)
                    yield '* '
                yield txt
                yield '\n'

        return ''.join(serialize()).strip()

    raise SeanoFatalError('expected hlist or string but found %s' % (value,))


def upgrade_note_schema(key, value):
    if key in ['commits', 'releases', 'tickets']:
        if not value:
            # An empty list in Yaml shows up as None here.
            # Auto-correct anything False-ish to an empty set.
            return set()
        if isinstance(value, ascii_str_type) or isinstance(value, unicode_str_type):
            # For convenience, we let you type in a single string, avoiding
            # list syntax in Yaml.  Auto-upgrade the schema now:
            return set([value])
        if isinstance(value, list):
            # Yaml doesn't have a concept of sets, so we get this type often.
            # Auto-upgrade the schema now:
            return set([validate_is_string_or_none(x) for x in value])
        if isinstance(value, set):
            # This is the correct, modern type, but we still have to validate the contents.
            return set([validate_is_string_or_none(x) for x in value])
        raise SeanoFatalError('unsupported data type for %s list: %s' % (key, value))
    if key.endswith('-loc-rst') and isinstance(value, dict):
        # According to the name of this field, this field is supposed to have a loc-rst
        # value.  For developer convenience, we also permit loc-hlist-rst values here;
        # such values are auto-converted to loc-rst on-the-fly by the schema upgrader
        # (this infrastructure).  By the time this value gets to the seano query dump
        # file (the main output of the seano executable -- the data consumed by views),
        # the value has already been migrated, and nobody will have any clue that the
        # original data type was loc-hlist-rst.
        #
        # ABK: I have ethical qualms with teaching seano things about markup.  The way I
        # see it, there are 2 main options:
        #
        # - teach seano to auto-migrate loc-hlist-rst values to loc-rst when appropriate
        # - teach the views that loc-rst values might contain loc-hlist-rst data
        #
        # The former is bad because seano should not be responsible for markup in any
        # way.  The latter is bad because violating type patterns only leads to more
        # complexity, and the views are already complicated enough.
        #
        # For the time being, I believe the lesser of those evils is the former -- that
        # seano should auto-migrate the schema at query time -- and that the views should
        # be able to trust advertised data types, and be oblivious to this problem.
        #
        # Iterate as needed.
        return {loc: convert_hlist_rst_to_rst(val) for loc, val in value.items()}
    return value


def upgrade_notes_object_schema(value):
    if value is None:
        # Empty dictionaries in Yaml show up as None in python; auto-convert now:
        return {}
    if isinstance(value, dict):
        return {k: upgrade_note_schema(k, v) for k, v in value.items()}
    raise SeanoFatalError('a note object must be a dict, but found %s' % (value,))


def upgrade_notes_container_schema(value):
    if value is None:
        # Empty lists in Yaml show up as None in python; auto-convert now:
        return []
    if isinstance(value, list):
        return [upgrade_notes_object_schema(x) for x in value]
    raise SeanoFatalError('top-level notes containers must be a list, but found %s' % (value,))


def upgrade_ancestry_schema(key, value):
    # No schema updates yet
    if key in ['name']:
        if type(value) not in [ascii_str_type, unicode_str_type]:
            raise SeanoFatalError('Internal error: why is an ancestry name not a string? found %s' % (value,))
    return value


def upgrade_ancestry_object_schema(value):
    if value is None:
        # Empty dictionaries in Yaml show up as None in python; auto-convert now:
        return {}
    if isinstance(value, ascii_str_type) or isinstance(value, unicode_str_type):
        # In past versions of seano, release ancestry used to be just strings.  Upgrade the schema:
        return {'name': upgrade_ancestry_schema('name', value)}
    if isinstance(value, dict):
        return {k: upgrade_ancestry_schema(k, v) for k, v in value.items()}
    raise SeanoFatalError('each ancestry object must be a dict, but found %s' % (value,))


def upgrade_ancestry_container_schema(value):
    if value is None:
        # Empty lists in Yaml show up as None in python; auto-convert now:
        return []
    if isinstance(value, ascii_str_type) or isinstance(value, unicode_str_type):
        # In past versions of seano, release ancestry was allowed to be a single string.  Upgrade the schema:
        return [upgrade_ancestry_object_schema(value)]
    if isinstance(value, list):
        return [upgrade_ancestry_object_schema(x) for x in value]
    raise SeanoFatalError('top-level ancestry containers must be lists, but found %s' % (value,))


def upgrade_release_schema(key, value):
    if key in ['before', 'after']:
        return upgrade_ancestry_container_schema(value)
    if key in ['notes']:
        return upgrade_notes_container_schema(value)
    return value


def upgrade_release_object_schema(value):
    if value is None:
        # Empty dictionaries in Yaml show up as None in python; auto-convert now:
        return {}
    if isinstance(value, dict):
        return {k: upgrade_release_schema(k, v) for k, v in value.items()}
    raise SeanoFatalError('each release must be a dict, but found %s' % (value,))


def upgrade_release_container_schema(value):
    if value is None:
        # Empty lists in Yaml show up as None in python; auto-convert now:
        return []
    if isinstance(value, list):
        return [upgrade_release_object_schema(x) for x in value]
    raise SeanoFatalError('top-level releases list must be a list, but found %s' % (value,))


def upgrade_root_schema(key, value):
    if key in ['parent_versions']:
        return upgrade_ancestry_container_schema(value)
    if key in ['releases']:
        return upgrade_release_container_schema(value)
    return value


def upgrade_root_object_schema(value):
    if value is None:
        # Empty dictionaries in Yaml show up as None in python; auto-convert now:
        return {}
    if isinstance(value, dict):
        return {k: upgrade_root_schema(k, v) for k, v in value.items()}
    raise SeanoFatalError('the root seano object must be a dict, but found %s' % (value,))
