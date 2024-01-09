"""
seano_cli/cmd/mark_as_ghost.py

Interactive command-line wrapper on top of the infrastructure that marks
currently existing extern notes as ghosts.
"""

from seano_cli.db import *
from seano_cli.utils import *

log = logging.getLogger(__name__)


def mark_as_ghost(db_search_seed_path, is_dry_run, extern_ids, patterns):
    db = find_and_open_seano_database(db_search_seed_path)
    files = []
    # IMPROVE: In a Git-backed project, `most_recently_added_notes()` and
    #          `get_notes_matching_pattern()` are both implemented using the
    #          Git scanner.  And here, our use of `get_notes_matching_pattern()`
    #          is inside a for loop.  There's some room for improvement here
    #          with regard to performance; although the Git scanner is designed
    #          to be as fast as possible, it is also not terribly cheap; it
    #          would be nice to invoke it less often.
    for extern_id in extern_ids:
        files.extend(db.get_notes_with_extern_id(extern_id))
        log.debug("Found notes with extern ID '%s':\n    %s", extern_id, "\n    ".join(files))

    for pattern in patterns:
        new_files, errors = db.get_notes_matching_pattern(pattern, include_modified=True)
        if not new_files:
            raise SeanoFatalError('Unable to resolve pattern:\n    %s' % ('\n    '.join(errors),))
        log.debug("Pattern '%s' yielded:\n    %s", pattern, "\n    ".join(new_files))
        files.extend(new_files)

    if not files:
        raise SeanoFatalError('Unable to identify any notes that match your query (add -v to troubleshoot)')

    files = sorted(set(files))
    log.debug("About to ghost:\n    %s", "\n    ".join(files))

    path_info = [db.ghost_note(note_file=file, is_dry_run=is_dry_run) for file in files]
    path_info = [x for x in path_info if x]

    if path_info:
        sys.stderr.write('\n'.join([
            'The following paths were updated:',
            '',
            ] + ['    %s  %s' % (s, os.path.relpath(p)) for s, p in path_info] + [
            '',
            'Please review the changes and commit them.',
            '',
        ]))
    else:
        sys.stderr.write('No changes were made to any selected notes\n')
