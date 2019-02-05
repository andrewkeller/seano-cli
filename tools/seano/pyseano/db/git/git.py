"""
pyseano/db/git/git.py
Reads a git-backed seano database.
"""

from pyseano.utils import *
from pyseano.db.generic import GenericSeanoDatabase
import os
import subprocess


class GitSeanoDatabase(GenericSeanoDatabase):
    def __init__(self, path):
        super(GitSeanoDatabase, self).__init__(path)
        try:
            cdup = subprocess.check_output(['git', 'rev-parse', '--show-cdup'], cwd=self.path,
                                           stderr=subprocess.PIPE).strip()
            self.repo = os.path.abspath(os.path.join(self.path, cdup))
        except subprocess.CalledProcessError:
            self.repo = None

    def is_valid(self):
        # If super doesn't think this is valid, then none of our core required files exist; bail.
        if not super(GitSeanoDatabase, self).is_valid(): return False
        # If there is no Git repository at all, then this cannot possibly be GitSeanoDatabase; bail.
        if not self.repo: return False
        # If any files inside the database are committed, then we consider this to be a valid GitSeanoDatabase:
        if subprocess.check_output(['git', 'log', '-1', '--', self.path], cwd=self.repo): return True
        # If any files inside the database are staged, then we consider this to be a valid GitSeanoDatabase:
        if 0 != subprocess.call(['git', 'diff', '--cached', '--quiet', '--', self.path], cwd=self.repo): return True
        # This may very well be a valid Seano database of some kind, but it cannot be a GitSeanoDatabase.
        return False

    def incrementalHash(self):
        # Same as dumb implementation, but faster.  Hash all files, but using HEAD as a base
        refs_list = subprocess.check_output(['git', 'for-each-ref'], cwd=self.repo).strip()
        uncommitted_files_query = ['git', 'ls-files', '--modified', '--others', '--exclude-standard']
        uncommitted_files = subprocess.check_output(uncommitted_files_query, cwd=self.path).splitlines()
        uncommitted_files = [os.path.join(self.path, x) for x in uncommitted_files]
        uncommitted_files = [x for x in uncommitted_files if os.path.exists(x)]
        return h_data(refs_list, *[h_file(x) for x in uncommitted_files])

    def make_new_note(self):
        filename = super(GitSeanoDatabase, self).make_new_note()
        subprocess.check_call(['git', 'add', '-N', filename])
        return filename

    def _fixup_release_notes_list(self, files):
        files = [f for f in files if f.endswith(SEANO_TEMPLATE_EXTENSION)]
        files = [os.path.join(self.repo, f) for f in files]
        return files

    def list_newly_staged_release_notes(self):
        return self._fixup_release_notes_list(subprocess.check_output(
            ['git', 'diff', '--cached', '--no-renames', '--diff-filter=A', '--name-only', '--', self.db_objs],
            cwd=self.repo,
        ).splitlines())

    def list_untracked_unignored_release_notes(self):
        return self._fixup_release_notes_list(subprocess.check_output(
            ['git', 'ls-files', '--others', '--exclude-standard', '--', self.db_objs],
            cwd=self.repo,
        ).splitlines())

    def move_note(self, from_filename, to_filename):
        subprocess.check_call(['git', 'mv', from_filename, to_filename])

    def most_recently_added_notes(self):
        def list_most_recently_committed_added_release_notes():
            # ABK: This command outputs the commit ID of the found commit, but it's conveniently pruned later due to
            #      the lack of a file extension.
            return self._fixup_release_notes_list(subprocess.check_output(
                [
                    'git', 'log', '--no-renames', '--diff-filter=A', '--name-only', '--pretty=format:%H', '-1', '--',
                    self.db_objs,
                 ],
                cwd=self.repo,
            ).splitlines())

        for attempt in [self.list_newly_staged_release_notes,
                        self.list_untracked_unignored_release_notes,
                        list_most_recently_committed_added_release_notes]:
            files = attempt()
            if files:
                return files
        return []
