"""
pyseano/db/git/git.py
Reads a git-backed seano database.
"""

from pyseano.utils import *
from pyseano.db.generic import GenericSeanoDatabase
import os
import subprocess

log = logging.getLogger(__name__)


class GitSeanoDatabase(GenericSeanoDatabase):
    def __init__(self, path, **base_kwargs):
        super(GitSeanoDatabase, self).__init__(path, **base_kwargs)
        try:
            cdup = subprocess.check_output(['git', 'rev-parse', '--show-cdup'], cwd=self.path,
                                           stderr=subprocess.PIPE).strip()

            self.repo = os.path.abspath(os.path.join(self.path, cdup.decode('utf-8')))
        except subprocess.CalledProcessError:
            log.info('Unable to invoke git as expected')
            self.repo = None
        except FileNotFoundError:
            log.info('No database located at %s', self.path)
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
        log.info('It looks like no files exist where the database is supposed to be')
        return False

    def incrementalHash(self):
        # Same as dumb implementation, but faster.  Hash all files, but using HEAD as a base
        refs_list = subprocess.check_output(['git', 'for-each-ref'], cwd=self.repo).strip()
        uncommitted_files_query = ['git', 'ls-files', '--modified', '--others', '--exclude-standard']
        uncommitted_files = subprocess.check_output(uncommitted_files_query, cwd=self.path).splitlines()
        uncommitted_files = [os.path.join(self.path, x) for x in uncommitted_files]
        uncommitted_files = [x for x in uncommitted_files if os.path.exists(x)]
        h_inputs = []
        h_inputs.append(refs_list)
        h_inputs.extend([h_file(x) for x in uncommitted_files])
        h_inputs.append(self.config['current_version'])
        h_inputs.extend(self.config['parent_versions'])
        return h_data(*h_inputs)

    def make_new_note(self):
        filename = super(GitSeanoDatabase, self).make_new_note()
        subprocess.check_call(['git', 'add', '-N', filename])
        return filename

    def git_diff_opts(self, include_modified):
        return [
                '--no-renames',
                '--diff-filter=AM' if include_modified else '--diff-filter=A',
                '--name-only',
                ]

    def _fixup_release_notes_list(self, files):
        files = [f for f in files if f.endswith(SEANO_NOTE_EXTENSION)]
        files = [os.path.join(self.repo, f) for f in files]
        return files

    def list_just_staged_release_notes(self, include_modified):
        result = self._fixup_release_notes_list(subprocess.check_output(
            ['git', 'diff'] + self.git_diff_opts(include_modified) + ['--', self.db_objs],
            cwd=self.repo,
        ).splitlines())
        log.debug('Staged release notes (no content): %s', result)
        return result

    def list_recently_staged_release_notes(self, include_modified):
        result = self._fixup_release_notes_list(subprocess.check_output(
            ['git', 'diff', '--cached'] + self.git_diff_opts(include_modified) + ['--', self.db_objs],
            cwd=self.repo,
        ).splitlines())
        log.debug('Staged release notes (some content): %s', result)
        return result

    def list_untracked_unignored_release_notes(self):
        result = self._fixup_release_notes_list(subprocess.check_output(
            ['git', 'ls-files', '--others', '--exclude-standard', '--', self.db_objs],
            cwd=self.repo,
        ).splitlines())
        log.debug('Untracked unignored release notes: %s', result)
        return result

    def move_note(self, from_filename, to_filename):
        subprocess.check_call(['git', 'mv', from_filename, to_filename])

    def most_recently_added_notes(self, include_modified):
        def list_most_recently_committed_added_release_notes():
            # ABK: This command outputs the commit ID of the found commit, but it's conveniently pruned later due to
            #      the lack of a file extension.
            result = self._fixup_release_notes_list(subprocess.check_output(
                [
                    'git', 'log'] + self.git_diff_opts(include_modified) + ['--pretty=format:%H', '-1', '--',
                    self.db_objs,
                 ],
                cwd=self.repo,
            ).splitlines())
            log.debug('Most recently committed release notes: %s', result)
            return result

        for attempt in [lambda: self.list_just_staged_release_notes(include_modified) +
                                self.list_recently_staged_release_notes(include_modified) +
                                self.list_untracked_unignored_release_notes(),
                        lambda: list_most_recently_committed_added_release_notes()]:
            files = attempt()
            if files:
                return files
        return []

    def get_notes_matching_pattern(self, pattern, include_modified):
        prior_files, prior_errors = super(GitSeanoDatabase, self) \
            .get_notes_matching_pattern(pattern=pattern, include_modified=include_modified)
        p = subprocess.Popen(['git', 'rev-parse', pattern], cwd=self.repo,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        if p.returncode != 0:
            err = 'git rejected the pattern: ' + (stderr.splitlines() or ['unspecified error'])[0]
            return (prior_files, prior_errors + [err])
        range = stdout.splitlines()
        if len(range) < 1:
            err = "git did not provide a commit range for the pattern '%s'" % (pattern,)
            return (prior_files, prior_errors + [err])
        if len(range) > 1:
            argv = ['git', 'diff'] + self.git_diff_opts(include_modified) + range
        else:
            argv = ['git', 'show'] + self.git_diff_opts(include_modified) + ['--pretty=format:%H'] + range
        files = self._fixup_release_notes_list(subprocess.check_output(argv, cwd=self.repo).splitlines())
        if not files:
            err = 'No commit in the range %s added%s any notes' % (pattern, '/modified' if include_modified else '')
            return (prior_files, prior_errors + [err])
        return (prior_files + files, prior_errors)
