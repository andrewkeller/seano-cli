"""
seano_cli/db/schema_upgrade.py

As it turns out, updating schemas is complicated enough that it mucks up other files.
So to make other code readable, we've taken all of the horror and collected it here.
"""

from seano_cli.utils import SeanoFatalError, ascii_str_type, unicode_str_type
import logging

log = logging.getLogger(__name__)


def validate_is_string_or_none(value):
    if value is None:
        return value
    if isinstance(value, (ascii_str_type, unicode_str_type)):
        return value
    raise SeanoFatalError('expected string or None but found %s' % (value,))


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
