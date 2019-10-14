"""
pyseano/db/git/git.py
Reads a git-backed seano database.
"""

from pyseano.db.note_set import NoteSet
from pyseano.utils import *
from pyseano.db.generic import GenericSeanoDatabase
import os
import re
import subprocess

log = logging.getLogger(__name__)


class GitSeanoDatabase(GenericSeanoDatabase):
    def __init__(self, path, **base_kwargs):
        super(GitSeanoDatabase, self).__init__(path, **base_kwargs)
        try:
            cdup = coerce_to_str(subprocess.check_output(['git', 'rev-parse', '--show-cdup'], cwd=self.path,
                                                         stderr=subprocess.PIPE)).strip()
        except subprocess.CalledProcessError:
            log.info('Unable to invoke git as expected')
            self.repo = None
        except FileNotFoundError:
            log.info('No database located at %s', self.path)
            self.repo = None
        else:
            self.repo = os.path.abspath(os.path.join(self.path, cdup))

            # Cache the list of deleted releases so that the ref parser can know to silenty swallow them:
            self.deleted_releases = [x['name'] for x in self.config.get('releases', []) if x.get('delete', False)]

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
        uncommitted_files_query = ['git', 'ls-files', '--modified', '--others', '--exclude-standard', '--', self.path]
        uncommitted_files = coerce_to_str(subprocess.check_output(uncommitted_files_query, cwd=self.repo)).splitlines()
        uncommitted_files = [os.path.join(self.repo, x) for x in uncommitted_files]
        h_inputs = []
        h_inputs.append(refs_list)
        h_inputs.extend([h_file(x) if os.path.exists(x) else 'deleted' for x in uncommitted_files])
        h_inputs.append(self.config)
        return h_data(*h_inputs)

    def make_new_note(self):
        filename = super(GitSeanoDatabase, self).make_new_note()
        subprocess.check_call(['git', 'add', '-N', filename])
        return filename

    def move_note(self, from_filename, to_filename):
        subprocess.check_call(['git', 'mv', from_filename, to_filename])

    def most_recently_added_notes(self, include_modified):
        for thing in self.scan_git_seano_db(include_modified):
            notes = thing.get('notes', None)
            if notes:
                return [os.path.join(self.repo, x) for x in notes.keys()]
        return []

    def get_notes_matching_pattern(self, pattern, include_modified):
        # Leverage our friendly neighbourhood base class to perform fuzzy matching on-disk:

        prior_files, prior_errors = super(GitSeanoDatabase, self) \
            .get_notes_matching_pattern(pattern=pattern, include_modified=include_modified)

        # In addition, also see if the pattern is a Git commit or Git commit range:

        p = subprocess.Popen(['git', 'rev-parse', pattern], cwd=self.repo,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        stdout = coerce_to_str(stdout)
        stderr = coerce_to_str(stderr)
        if p.returncode != 0:
            err = 'git rejected the pattern: ' + (stderr.splitlines() or ['unspecified error'])[0]
            return (prior_files, prior_errors + [err])
        commits_remaining = set(stdout.splitlines())

        is_a_commit = re.compile('^[a-f0-9]+$').match
        if not all(map(is_a_commit, commits_remaining)):

            # Something in the returned data is not a simple Git commit.  It's probably a range, like this:
            #
            #       123abc
            #       ^456def
            #
            # Convert that into a list of commits.

            p = subprocess.Popen(['git', 'rev-list'] + list(commits_remaining), cwd=self.repo,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()
            stdout = coerce_to_str(stdout)
            stderr = coerce_to_str(stderr)
            if p.returncode != 0:
                err = 'git rejected the pattern: ' + (stderr.splitlines() or ['unspecified error'])[0]
                return (prior_files, prior_errors + [err])
            commits_remaining = set(stdout.splitlines())
        if not commits_remaining:
            err = "git did not provide any commits for the pattern '%s'" % (pattern,)
            return (prior_files, prior_errors + [err])
        log.debug('Searching for notes added%s in %s', '/modified' if include_modified else '', commits_remaining)
        files = []
        for thing in self.scan_git_seano_db(include_modified):
            notes = thing.get('notes', None)
            if notes:
                # filter the paths by the commit that created/modified the note.  Note that notes can override the
                # commit, but that the Git scanner doesn't read notes, so it doesn't have access to that information.
                matches = [path for path, info in notes.items() if info['commit'] in commits_remaining]
                if matches:
                    log.debug('Notes from commits: %s', matches)
                    files.extend([os.path.join(self.repo, x) for x in matches])
                    # On our checklist of commits togo, check off the commit of the first note (because without
                    # reading note files and potentially overriding an automatically deduced commit ID, all of the
                    # notes in the same hunk will have the same automatically deduced commit ID)
                    commits_remaining.remove(notes[matches[0]]['commit'])
                # If our checklist is empty, stop scanning.
                if not commits_remaining: break;
        if not files:
            err = 'No commit in the range %s added%s any notes' % (pattern, '/modified' if include_modified else '')
            return (prior_files, prior_errors + [err])
        return (prior_files + files, prior_errors)


    def query(self):
        # ABK: The beginning and end of this function should be kept somewhat in sync with the copy in generic.py
        s = NoteSet(self.config)
        for thing in self.scan_git_seano_db(False):

            # Forward discovered notes into the note set:
            for filename, info in thing.get('notes', {}).items():
                f = os.path.join(self.repo, filename)
                s.import_automatic_note(path=f, uid=self.extract_uid_from_filename(f), **info)

            # Forward discovered releases into the note set:
            for name, info in thing.get('releases', {}).items():
                s.import_automatic_release_info(name, **info)

        # Use the main database config file (seano-config.yaml) as a foundation for the query result structure.
        # Overwrite the entire `releases` member; the NoteSet object contains all the juicy metadata contained
        # in the existing `releases` member in seano-config.yaml, so we're not losing any data by overwriting.
        result = dict(self.config)
        result['releases'] = s.dump()
        return result


    def parse_ref(self, ref):
        '''
        Scans the given ref for the possibility that it indicates a release.

        If we think this ref indicates a release, we return the release name.  Else, we return None.
        '''
        m = re.match(r'^refs/tags/v(?P<name>[0-9]+(\.[0-9]+)+([a-z]{1,2}[0-9]+)?)$', ref)
        if m:
            name = m.group('name')
            if name not in self.deleted_releases:
                return name
        return None


    def scan_git_seano_db(self, include_modified):
        '''
        Uses Git to read the local seano database (as opposed to reading the filesystem).  In a nutshell, this means
        that we report note files in reverse order of creation date, and we can parse tags to deduce releases.

        Args:
            include_modified (bool-ish): change sort order of note files from A (added) to AM (added || modified)

        Yields:
            Dictionaries of juicy info

        A yielded dictionary is one that contains a single top-level key saying what it is.  It may be any one of the
        following::

            # A set of discovered note files:
            {
                'notes' : {
                    <path> : {                          # path to note file in working directory
                        commits = [<commit-id>, ...],   # commit in which note was created
                        releases = [<name>, ...],       # list of releases note release in
                        ...                             # (optional) more juicy info?
                    },
                    ...
                }
            }

            # Info about a single release:
            {
                'releases' : {
                    <name> : {                      # name of the release
                        'after' : [<name>, ...],    # (optional) list of releases after
                        'before' : [<name>, ...],   # (optional) list of releases before
                        'commit' : <commit-id>,     # commit of this release
                        ...                         # (optional) more juicy info?
                    }
                }
            }

        This function does NOT read note files from disk.  This is important to understand, namely because a note file
        may explicitly override its list of releases.  If a note file is to be read from disk (such as what happens
        during a query), it is expected that the caller will take the partial note created by this function, which
        contains ONLY fully automatic data, and flash-update it with the values read from the note file on disk.  The
        net effect is that the contents of the note will be automatic when possible, but manual if overridden in the
        notes file on disk.

        This function yields all knowledge -- notes and release ancestry data -- in the reverse order that the data
        was committed in the repository.

        In the case of yielding notes, because multiple notes can be created in the same commit, this function returns
        entire lists of partial notes at a time, indicating that the notes are indistinguishable in age (at least
        according to the commit graph).

        The topological sort order of yielded knowledge in a non-linear commit graph is undefined, but consistent.

        By default, notes are considered "added in a commit" if they are, according to Git, created.  Exact renames
        are followed, and are not considered to be when a note was created.

        If include_modified is Trueish, notes are yielded in either in the reverse order that they were added, or in
        the order of most recently modified, whichever is first.  Same as before, exact renames are followed, and are
        not considered to be a date when a note was created or modified.

        Any uncommitted notes are yielded as a dedicated group prior to any notes discovered as added in any commit.

        If include_modified is Trueish, notes with uncommitted changes are also included in the aforementioned special
        first group.
        '''
        # ABK: We are not going to traverse the filesystem at self.db_objs.  For performance reasons, all knowledge of
        #      what files exist is going to come straight from Git itself.  In theory, this should let us bail early
        #      if the generator is deallocated early.

        def yield_commits():

            class Commit(object):
                def __init__(self, commit_id, parents, refs, releases, raw_name_statuses):
                    self.commit_id = commit_id
                    self.parents = parents
                    self.refs = refs
                    self.releases = releases
                    self.raw_name_statuses = raw_name_statuses

            diff_opts = [
                '-M100%',
                '--name-status',
            ]

            staged_changes = coerce_to_str(subprocess.check_output(
                ['git', 'diff', '--cached'] + diff_opts,
                cwd=self.repo,
            )).splitlines()
            log.debug('Staged changes: %s', staged_changes)

            unstaged_changes = coerce_to_str(subprocess.check_output(
                ['git', 'diff'] + diff_opts,
                cwd=self.repo,
            )).splitlines()
            log.debug('Unstaged changes: %s', unstaged_changes)

            untracked_unignored_files = coerce_to_str(subprocess.check_output(
                ['git', 'ls-files', '--others', '--exclude-standard'],
                cwd=self.repo,
            )).splitlines()
            log.debug('Untracked unignored files: %s', untracked_unignored_files)

            # ABK: The order of this addition is designed so that algorithms later
            #      will process changes in an order expected by humans.
            uncommitted_changes = \
                ['A\t' + x for x in untracked_unignored_files] + \
                unstaged_changes + \
                staged_changes

            # Manufacture a fake commit containing the data we've gathered, and yield it.
            # (by pretending that this is a commit, we simplify the algorithm later)

            if uncommitted_changes:
                yield Commit(
                    commit_id = None,
                    parents = [coerce_to_str(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.repo)).strip()],
                    refs = [],
                    releases = [],
                    raw_name_statuses = uncommitted_changes,
                )

            def yield_commit_info_hunks():

                # Fire up the massive commit graph dump.  Example output:
                #
                # 1     a8dc74cb0fca0405ce4f9ecc8f2718b2accb6dc6 7b936ed3b4116e2615c6fdf1c119823f6c2a8e9c (tag: refs/tags/v1.2.3, refs/remotes/origin/master, refs/remotes/origin/HEAD)
                # 2     A       doc/seano-db/v1/60/8bb47a848f6e8949c5f2545b0d0056.yaml
                # 3     R100    mac/doc/seano-db/v1/ae/55628fcf4f49975d7c949c52be8bc7.yaml       doc/seano-db/v1/42/713c898b24a0220133cc9696f990ab.yaml
                # 4     D       mac/doc/seano-db/v1/ef/9a7df3ab58c8583a42f258ac8cf0b1.yaml
                # 5     M       some/other/file.txt
                #
                #   1. Commit hash; parent hashes (missing if none); refs (missing if none)
                #   2. Added files (ding ding ding!  report this note)
                #   3. Renamed files (track rename in `heap`)
                #   4. Deleted files (ban this file from ever being reported)
                #   5. Modified files (report this note iff `include_modified`)

                # ABK: For performance reasons, slurp stdout instead of loading the entire Git history all at once.
                #      Because we're yielding results instead of returning a final list, the caller can deallocate
                #      our generator before we finish reading the entire Git history.  (Assuming this syntax is
                #      correct, of course)
                p = subprocess.Popen(
                    ['git', 'log', '--decorate=full', '--name-status', '-M100%', '--pretty=format:%H %P%d'],
                    cwd=self.repo, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    bufsize=4096, # hopefully large enough to capture any possible stderr without blocking
                    close_fds=True,
                )
                p.stdin.close()

                def possibly_dump_stderr():
                    if p.poll() is not None and p.returncode != 0:
                        log.error('unable to read commit graph: %s', p.stderr.read().strip())
                        sys.exit(1)

                accumulator = []
                commit_begin_regex = re.compile('^[0-9a-f]{6,}')

                possibly_dump_stderr()
                for line in iter(p.stdout.readline, ""):
                    possibly_dump_stderr()
                    if not line:
                        # Normally, all read lines include the EOL.
                        # If we read literally nothing, then the pipe has been closed,
                        # which may mean the app has exited.  Well?  Has the app exited?
                        if p.poll() is not None:
                            break # app has exited; bail on the read loop
                    line = coerce_to_str(line.strip())
                    if accumulator and commit_begin_regex.match(line):
                        yield accumulator
                        accumulator = []
                    if line: # ignore empty lines
                        accumulator.append(line)

            ws_split = re.compile(r'(\s+)').split
            ref_split = re.compile(r'(?:HEAD \->|tags?:|\(|\)|,|\s)+').split

            for hunk in yield_commit_info_hunks():
                header, changes = hunk[0], hunk[1:]

                hashes, _, refs = header.partition('(')

                hashes = ws_split(hashes)
                commit_id, parents = hashes[0], hashes[1:]

                refs = ref_split(refs)

                parents = [x for x in parents if x]
                refs = [x for x in refs if x]

                releases = list(filter(None, map(self.parse_ref, refs)))

                yield Commit(
                    commit_id = commit_id,
                    parents = parents,
                    refs = refs,
                    releases = releases,
                    raw_name_statuses = changes,
                )

        # Declare self.config['current_version'] as a release, to help downstream systems more
        # easily get release sort order correct:
        yield {'releases' : {
            self.config['current_version'] : {}, # no info; just declare that it exists
        }}

        # Prepare to traverse the commit graph

        # Because HEAD is an implicit release (above), we want its commit ID,
        # even if it's not a tag (tags get their commit IDs reported automatically).
        has_reported_head_commit_id = False

        current_releases = {}   # set() per-commit
        distant_releases = {}   # set() per-commit

        # A structure for storing notes, such that we can still access notes even if they get renamed.
        # You should assume that notes in this structure are multi-linked!
        notes = {}  # filename -> { note dict }

        primary_note_prefix = os.path.relpath(self.db_objs, self.repo) + os.sep
        primary_note_suffix = SEANO_NOTE_EXTENSION

        for commit in yield_commits():
            log.debug('Investigating commit %s', commit.commit_id)

            if not current_releases:
                # This is the first iteration of this loop.  Seed the release tracking structures:

                # This code is a bit clever.  Here's what's happening:
                #   - regardless, distant_releases only needs commit.commit_id defined to an empty set.
                #   - for current_releases, commit.commit_id gets set to:
                #       - if releases were automatically identified, then that means HEAD is tagged and
                #         we have no uncommitted work.  We do *not* want the implicit HEAD release defined
                #         out ahead of any automatic releases.  Use auto-detected releases right now.
                #       - if releases were not automatically identified, then that means either HEAD is
                #         not tagged or we have uncommitted changes.  This means that we *must* have an
                #         implicit HEAD release defined out in front of any tag we detect automatically.
                local_current_releases = commit.releases or [self.config['current_version']]

                # Initialize current & future releases caches:
                current_releases = {    # set() per-commit
                    commit.commit_id : set(local_current_releases),
                }
                distant_releases = {    # set() per-commit
                    commit.commit_id : set(),
                }

                # No point in removing previously defined releases (no previous releases exist)

                # No point in notifying the caller of discovered release ancestry (no previous release exists)

            elif commit.releases:
                # This means:
                #   - this is not the first commit we are investigating
                #   - but yet, we found a new release tag
                #       - every release in commit.releases is automatically an ancestor
                #         of every release in current_releases[commit.commit_id]
                #       - every release in current_releases[commit.commit_id]
                #         should get moved to distant_releases[commit.commit_id]

                # We found release tag(s).  Parse them.
                local_current_releases = set(commit.releases)
                immediate_descendants  = current_releases[commit.commit_id] - distant_releases[commit.commit_id]
                local_distant_releases = current_releases[commit.commit_id] | distant_releases[commit.commit_id]

                log.debug('Investigating release %s'
                          '\n\tcurrent_releases[commit.commit_id]: %s'
                          '\n\tdistant_releases[commit.commit_id]: %s'
                          '\n\tlocal_current_releases: %s'
                          '\n\timmediate_descendants:  %s'
                          '\n\tlocal_distant_releases: %s',
                          commit.releases, current_releases[commit.commit_id], distant_releases[commit.commit_id],
                          local_current_releases, immediate_descendants, local_distant_releases)

                # Sanity check; avoid problems where the same release is defined multiple times:
                for error_overlap in [local_current_releases & current_releases[commit.commit_id],
                                      local_current_releases & distant_releases[commit.commit_id]]:
                    if error_overlap:
                        log.warn('WARNING: Releases %s redefined in commit %s; will ignore redefinition',
                                 error_overlap, commit.commit_id)
                        local_current_releases = local_current_releases - error_overlap

                # Notify the caller of the commit ID of this release:
                yield {'releases' : {
                    x : { 'commit' : commit.commit_id } for x in local_current_releases
                }}

                # Notify the caller of the discovered release ancestry:
                for newer in immediate_descendants:
                    for older in local_current_releases:
                        yield {'releases' : {
                            older : {
                                'before' : [newer],
                            },
                            newer : {
                                'after' : [older],
                            },
                        }}

                # Update current & future releases caches:
                current_releases[commit.commit_id] = local_current_releases
                distant_releases[commit.commit_id] = local_distant_releases

            # Report the commit of the HEAD release (applicable when HEAD is not tagged or has uncommitted changes):
            if not has_reported_head_commit_id and commit.commit_id:
                yield {'releases' : {
                    x : { 'commit' : commit.commit_id } for x in local_current_releases
                }}
                has_reported_head_commit_id = True

            # Propagate release ancestry knowledge to the parent commits:
            for p in commit.parents:
                distant_releases[p] = distant_releases.get(p, set()) | distant_releases[commit.commit_id]
                current_releases[p] = (current_releases.get(p, set()) | current_releases[commit.commit_id]) \
                                      - distant_releases[p]

            # Identify any reportable note files:
            notes_to_report = []
            for change in commit.raw_name_statuses:
                change = change.split('\t')
                code = change[0]
                if code == 'A' or code == 'C' or (include_modified and code == 'M'):
                    fname = change[1]
                    if fname in notes or (fname.startswith(primary_note_prefix) and fname.endswith(primary_note_suffix)):
                        # Report this note!
                        n = notes.get(fname, dict(path=fname))
                        notes_to_report.append(n)
                    continue
                if code == 'R100':
                    fsrc = change[1]
                    fdst = change[2]
                    if fdst in notes or (fdst.startswith(primary_note_prefix) and fdst.endswith(primary_note_suffix)):
                        # Alias the note to both filenames
                        n = notes.get(fdst, notes.get(fsrc, dict(path=fdst)))
                        notes[fsrc] = n
                        notes[fdst] = n
                    continue
                if code == 'D':
                    fname = change[1]
                    if fname in notes or (fname.startswith(primary_note_prefix) and fname.endswith(primary_note_suffix)):
                        # Mark the note as "never report"
                        n = notes.get(fname, dict(path=fname))
                        n['delete'] = True
                    continue

            # Do not ever report deleted notes:
            notes_to_report = [x for x in notes_to_report if not x.get('delete', False)]

            if notes_to_report:
                # Report notes:
                yield dict(notes={
                    n['path'] : dict(
                        commits=[commit.commit_id],
                        releases=current_releases[commit.commit_id],
                    )
                    for n in notes_to_report
                })