``seano``
========

``seano`` is a tool that lets you write a Json object per-change, and then later get a list of all the Json objects
you wrote per-release, all without making rebasing harder in Git.

In practice, what this means is that developers can write arbitrarily complex release notes and other metadata at the
time of development without sacrificing rebase usability in Git.

How we got here
---------------

When maintaining a single file of release notes, you are eventually presented with a choice:

1. For each change, edit the text file (this makes rebasing hard)
2. Update the text file only at release time (this makes it hard to write good notes)

When a project is young, the latter is easy, and reasonable.  As the project grows, both of the options become more
painful at different rates, depending on the project's needs:

1. Release notes get more detailed (this can manifest as new sections in your text file)
2. The same release notes get consumed by more than one entity, but as different formats (this can force you to
   maintain the same information multiple times in different formats)
3. Automation is desired

Depending on your needs, a glob-import in Sphinx may be good enough for you.  And if you use a new file for each
change, rebases won't suffer.

``seano`` may help if any of the following are true for your project:

1. A glob-import in Sphinx is not customizable enough
2. You need an output format that is difficult for Sphinx to support
3. You're tracking a lot of metadata for each change and you'd like the information centrally organized


Requirements
------------

In the event that you decide that a system better than a glob-import in Sphinx is needed, here are the basic
requirements of such a system:

1. Can store notes
2. Notes are mutable
3. Notes are deletable
4. Notes storage should not optimize for merge conflicts
5. Cherry-picking a commit should also pull over associated notes without requiring fixups
6. Supports submodules
7. Supports output types we know we need: reStructuredText, HTML, Confluence-flavored HTML, and RTF

Takeaways:

* #2 and #3 mean we can't use commit messages in Git
* #4 means we can't use a single file of any kind
* #5 means Git is involved in some way

Upon initial investigation, `Reno <https://docs.openstack.org/reno/latest/>`_ and
`towncrier <https://pypi.org/project/towncrier/>`_ both fit the core requirements nicely, but fall short with
submodule and output file type support.  Since neither system is really that complex, it seemed easiest to start a new
system from scratch that does exactly what we need.

This version of ``seano`` doesn't support submodules yet, but the correct groundwork is already in place to move in
that direction when it gets prioritized.


Concept
-------

Although ``seano`` is used for release notes, ``seano`` itself is only an object storage system; other infrastructure is
used to convert a ``seano`` query result file into a presentable view.

The objects you store in a ``seano`` database must be non-null objects.  To help enforce this, and to improve
readability by humans, the individual band files you save in a ``seano`` database are Yaml files.

When you query a ``seano`` database for its objects, ``seano`` auto-groups all notes into releases based on the commit
graph in Git, and you get a big fat Json file containing::

    {                         # top-level dictionary
      ...,                     # the contents of seano-config.yaml, as-is
      "releases" : [           # sorted list of releases
        {                       # a single release
          "name" : "1.2.3",      # tag name
          "after" : [            # list of immediate ancestors
            {"name": "1.2.2"},    # an ancestry link
          ],
          "before" : [           # list of immediate descendants
            {"name": "1.2.4"},    # an ancestry link
          ],
          "notes" : [            # sorted list of notes
            {                     # a single note
              "id" : "123abc",     # the id of this note in seano
              ...                  # the contents of the note, as-is
            },
            ...
          ]
        },
        ...
      ]
    }

The top-level dictionary is a copy of ``seano-config.yaml``; this is intended to provide shared (cross-project)
views project-specific knowledge.  Examples of such knowledge include the project name, URL, etc.

The schema of data you store in ``seano`` is demanded/enforced by the views you choose to use, not by ``seano`` itself.
For documentation on what schema you need to use, refer to the documentation for the :doc:`seanoViews`.


Usage
-----

``seano`` is perfectly happy to be ran on its own without Zarf, however Zarf does smooth over some of the rough edges
in ``seano`` by automatically providing certain arguments behind your back.  To help keep this documentation short,
we'll cover how ``seano`` is used in the typical case: as part of a Zarf project.

``seano`` launches a text editor in most cases.  The default editor is ``vim -O`` (``vim`` in column mode).  To
customize the editor, define either the ``SEANO_EDITOR`` or ``EDITOR`` environment variables.


Inserting data
--------------

``seano new`` and ``seano edit`` have fairly good runtime documentation as-is, so here is a brief
overview:

To create a single new note::

    $ seano new

To edit the note most recently created::

    $ seano edit

To edit the note most recently modified::

    $ seano edit -m

Say, 4 commits ago, in commit ``5c6ff85ffc76022e8c525f23e7cff1726bb3aaee``, you created a note stored at
``docs/seano-db/v1/46/543fbda3bedd85c50385ffc19fe576.yaml``.  All of the following will find it::

    $ seano edit HEAD~~~~    # 4 commits ago
    $ seano edit 5c6ff85     # Git commit ID
    $ seano edit 46/543      # partial path with seano note ID
    $ seano edit 46\543      # partial path with seano note ID (see note)
    $ seano edit 46543       # seano note ID

To edit all notes created between ``v1.2.4`` and ``v1.2.5``::

    $ seano edit v1.2.4..v1.2.5

.. note::

    When you give ``seano edit`` a partial path, it will accept either Unix slashes or Windows slashes on all
    platforms.  This is because, in particular on Windows, it's not hard to have paths formatted either way on
    the same physical machine (i.e., Windows command-line vs. Linux subsystem).  Factoring in SSH and other
    forms of remote control, the reality is that on lots of OSs, it's not hard to have the "wrong" slashes at
    any given time.  To make copy/paste easier in the face of directory slash differences, ``seano edit`` accepts
    either kind all the time.


Reserved keys
-------------

Generally speaking, ``seano`` only stores objects, and you put whatever data you want into it.  However, ``seano`` does
own some keys; avoid setting them unless you intend to override them.

.. note::

    This documentation describes only the keys specific to ``seano``; either ``seano`` itself uses these keys, or
    ``seano`` guarantees to all views that these keys will exist.  Some of the :doc:`seanoViews` reserve additional keys
    for their own uses; such additional keys are not mentioned here.

Notes have these keys automatically set on them:

* ``commits``: list of commit IDs that supply this note *(supported SCMs)*
* ``id``: the ``seano`` note ID
* ``is-copied-from-backstory``: whether or not the note was copied from a backstory (see :ref:`seano-backstory`)
* ``releases``: list of release names in which this note was released *(supported SCMs)*

  * In unsupported SCMs, if you don't set this key, the note will appear in the ``HEAD`` release

* ``refs``: unused; reserved for future use

Releases have these keys automatically set on them:

* ``after``: list of dictionaries describing immediate ancestor releases *(supported SCMs)*

  * In unsupported SCMs, if you do not set either ``before`` or ``after`` on a release, ``seano`` may get the release
    order incorrect

* ``before``: list of dictionaries describing immediate descendant releases *(supported SCMs)*

  * In unsupported SCMs, if you do not set either ``before`` or ``after`` on a release, ``seano`` may get the release
    order incorrect

* ``commit``: the commit ID of this release *(supported SCMs)*
* ``name``: name of this release (not localized)
* ``notes``: list of note dictionaries
* ``refs``: unused; reserved for future use

The following keys are functional in ``seano-config.yaml``:

.. note::

    Zarf automatically supplies some keys via the config annex, allowing humans to never need to supply them manually.
    Such keys should be noted below.

    For more information on the ``seano`` config annex concept, search the code base for ``--config-annex``

* ``current_version``: the current version of the project

  * Always required (``seano`` does not want to be responsible for deriving this)
  * In Zarf projects, this is automatically supplied via the config annex

* ``parent_versions``: list of dictionaries describing immediate ancestors of HEAD *(supported SCMs)*

  * In unsupported SCMs, you must set this

* ``releases``: list of release dictionaries

  * In unsupported SCMs, this is where you manually set keys on releases

* ``seano_note_template_contents``: big fat string value to use as the template when creating a new note

  * When not set, a default value is used that contains all keys used by the :doc:`seanoViews`

* ``seano_note_template_replacements``: dictionary of search-and-replace pairs to run on the note template before a
  human sees it for editing

  * The intended purpose is to let projects augment the template without fully replacing the whole thing

Feel free to save any other key in ``seano``.


Querying data
-------------

Getting data out of a ``seano`` database is done using ``seano query``.  We hope to make this process more
automated/integrated with Zarf/Sphinx in the future.  In the meantime, feel free to browse the runtime documentation::

    $ seano query -h


.. _seano-backstory:

Backstories
-----------

In modern development, release ancestries are often conceptually non-linear.  We do a pretty good job denying it, with
comments like *"long-lived betas are an anti-pattern"*, and *"why is it so hard to establish confidence of the
stability of a release"*, and *"if you'd use feature flags, you wouldn't have this problem"*, but the reality is, even
in a perfect world with unicorns, rainbows, and feature flags, some development still take more than one release to
finish.  And when you finally do finish, you now have a trail of "extra" releases behind you that, ideally, you'd like
to prune, because they don't tell the story you want to tell — but you don't want to delete them, because they were
actually real releases, and for Member Care to support them, we need to have at least some memory of what they
contained.

Enter *backstories*.  In ``seano``, a backstory is a subgraph of the release ancestry graph that is deemed unhelpful to
be displayed by default to public customers.  By convention, our internal tools, such as our internal Release Notes
archives, typically display all releases, whereas our public-facing tools, such as published Release Notes, typically
hide backstories.

When a backstory is defined, all notes for all releases within the backstory are automatically copied into the notes
list of the release that merges the backstory.  The copies each automatically have a new member named
``is-copied-from-backstory`` set on them, with a value of ``true``.  The originals of the notes do not have
``is-copied-from-backstory`` set on them at all.

When iterating over the Json in a ``seano`` query dump file, you'll find that the releases list includes all releases
*(including backstory releases)*, and the notes lists on every release include all notes *(including backstory notes)*.
Sure, you could display everything — but that can be confusingly repetitive to most readers.  Usually, you want to
filter one or the other out:

* If you are displaying backstories, then you usually want to display all releases, but *filter out backstory notes*

  * The easiest way to identify whether or not a note is a backstory note is to see if ``is-copied-from-backstory``
    both exists *and* is set to ``true``

* If you are hiding backstories, then you usually want to display all notes, but *filter out backstory releases*

  * The easiest way to identify whether or not a release is a backstory release is to invoke
    :py:func:`zarf.support.seano.views.shared.schema_painting.seano_paint_backstory_releases` on your releases list, and
    then on a release, see if ``is-backstory`` is set to ``true``

Presently, backstories can only be configured manually; they are never auto-deduced from Git.  Long term, we hope to
add some automation here.  For now, you can manually define backstories in your project's ``seano-config.yaml`` file.
Say, for example, in the scenario below, you want the granular history of the ``1.4`` and ``1.6`` releases to be
backstories.  Here's how to do it:

.. code-block:: text

                   Auto-deduced by
                   mining the commit    Must be manually typed
                   graph (no need       into seano-config.yaml
   Commit graph    to type in)          to configure backstories

                   releases:            releases:
   *  v1.6         - name: 1.6          - name: 1.6
   |\                after:               after:
   | |               - name: 1.0
   | |               - name: 1.5          - name: 1.5
   | |                                      is-backstory: true
   | |
   | * v1.5        - name: 1.5
   | |               after:
   | |               - name: 1.4
   | |
   | *  v1.4       - name: 1.4          - name: 1.4
   | |\              after:               after:
   | | |             - name: 1.1
   | | |             - name: 1.3          - name: 1.3
   | | |                                    is-backstory: true
   | | |
   | | * v1.3      - name: 1.3
   | | |             after:
   | | |             - name: 1.2
   | | |
   | | * v1.2      - name: 1.2
   | | |             after:
   | | |             - name: 1.1
   | |/
   | *  v1.1       - name: 1.1
   | |               after: 1.0
   |/
   *  v1.0         - name: 1.0

In the above scenario, the entire release ancestry is auto-deduced from tags in Git, which means we don't have to
declare any releases or any release ancestries.  However, in order to set ``is-backstory`` to ``true`` on any
particular release ancestry link, we must define the release, and then define the ancestry link.

``is-backstory`` can only be set on the *descendant side* of an ancestry link (i.e., the ``after`` list).  Setting
``is-backstory`` on the ancestor side of an ancestry link has no effect.

The graph theory explanation of what the above configuration says is the following:

* The backstory of ``1.6`` is ``1.5`` and all ancestors thereof, *not including* ``1.0`` and all ancestors thereof
* The backstory of ``1.4`` is ``1.3`` and all ancestors thereof, *not including* ``1.1`` and all ancestors thereof

In practice, what ends up happening is:

* ``1.0`` contains notes for ``1.0``
* ``1.1`` contains notes for ``1.1``
* ``1.2`` contains notes for ``1.2``
* ``1.3`` contains notes for ``1.3``
* ``1.4`` contains notes for ``1.2``, ``1.3``, and ``1.4``
* ``1.5`` contains notes for ``1.5``
* ``1.6`` contains notes for ``1.1``, ``1.2``, ``1.3``, ``1.4``, ``1.5``, and ``1.6``


Onboarding old data
-------------------

If the project has never used ``seano`` before, you must first create the ``seano`` database::

    $ seano init

To import old notes into an existing ``seano`` database:

1. If the release for which you are importing does not exist as a tag in Git (or if you are not using Git), you must
   inform ``seano`` of the existence of the release.  To do that, open ``docs/seano-db/seano-config.yaml`` in your
   favorite text editor, and in the ``releases`` list, make sure a release is defined with the name of the release
   you're importing.  The list looks something like this:

   .. code-block:: yaml

      releases:
      - name:  1.2.3
        after: 1.2.2    # `after` can optionally be a single string, or a list of single strings
      - name:  1.2.2
        after:          # `after` is only needed if tags are missing
        - name: 1.2.0
        - name: 1.2.1   # example of full schema here
          is-backstory: true
      # ... etc

2. Run ``seano new -n <N>``, where ``<N>`` is the number of release notes you're adding for this release.  By
   creating ``N`` new notes all at once and editing them in ascending order of filename, you preserve the original
   sort order of the release notes, so that when you render old release notes using your new tools, the output has a
   chance at actually looking remarkably the same as it used to.
3. For each note you added, explicitly set a value for the ``releases`` key.  This value is the name of the release
   from when you defined the release in the ``releases`` list in ``seano-config.yaml``.  By explicitly setting a
   release name, you are instructing ``seano`` to not try to automatically deduce the release name from the
   commit graph.

.. note::

    It is highly recommended to commit regularly when importing old release notes.  ``seano`` does not have any "undo"
    concept at all; the power to undo mistakes is granted only by the underlying repository.  If you do not commit
    regularly, it can be difficult to undo an erroneous or mistaken ``seano new`` invocation without also
    destroying desired but uncommitted work.


Displaying data
---------------

``seano`` is not designed to display any data on its own.  ``seano`` is an object storage/query system; nothing more.
To display data, take a peek at the :doc:`seanoViews`.


Known bugs and other sharp edges
--------------------------------

Git scanner does not auto-detect backstories
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It would be nice if support for :ref:`seano-backstory` included automatically identifying backstories from commit graph
topology, or even tag names.


``seano edit`` does not respect overridden commit IDs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is more of a sharp edge than a bug.

So, ``seano`` lets you override the automatically deduced commit ID of a note by setting the ``commit`` attribute in
the note to the commit of your choice.  This is useful in particular with onboarded notes, where you have N notes
onboarded into ``seano`` all in one commit, but they represent the past X releases.  If you have a view that displays
or uses commit IDs, it's useful to be able to tell ``seano`` the correct commit ID of an onboarded note.

However, the vast majority of the functionality that powers being able to override automatically deduced properties of
a note is implemented inside the query layer (used by ``seano query``), which is an entire layer of its own on
top of the Git scanner.

For performance, ``seano edit <commit>``, is built directly on top of the Git scanner.  It doesn't actually
read note files from disk at all; it only returns filenames yielded by the Git scanner.  This means that if a note
overrides its commit ID, ``seano edit <commit>`` will never know.

Algorithmically, this can be fixed, but it comes with the performance penalty of being forced to load every note from
disk, because every note has the possibility of having the commit overridden to the commit you asked for.

For now, when you use ``seano edit <commit>``, understand that the ``<commit>`` parameter is referring strictly
to Git's knowledge, and doesn't account for any overrides inside the note.  Iterate as necessary.


Deleted releases cannot be referenced in release ancestries
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is more of a sharp edge than a bug.

For context, in a Git-backed ``seano`` database, if you want to tell ``seano`` to skip (ignore) a tag in Git, you can
open up ``seano-config.yaml``, and add a section like this:

.. code-block:: yaml

    releases:
    - name: 1.2.3
      delete: True

In a fully automatic situation, where all releases and all release ancestry is mined from Git, this works well.  When
the Git scanner runs, it ignores 1.2.3 outright (it pretends it doesn't exist).  The automatically set before/after
links properly hook up the releases on either side of 1.2.3, and 1.2.3 never shows up in any query.  It's like 1.2.3
doesn't even exist.

This sharp edge actually has nothing to do with Git -- it's related to the logic that automatically validates and
doubly-links the ancestry graph at query time.  Suppose you have some manually defined releases, and you suddenly
decide to delete a release.  What you *cannot do* is simply set ``delete`` to ``true`` on that release, and expect
``seano`` to hook up the dangling ancestry links like it does for a deleted Git tag.

The practical fallout here is that if you want to delete a release that is involved in some manual ancestry
declarations, you must also reroute those ancestries around the deleted release.  Here's an example:

.. code-block:: diff

    releases:
    - name: 1.2.4
      after: 1.2.3

    - name: 1.2.3
   -  after: 1.2.2    # this causes seano to explode at query time
   +  after: 1.2.1    # you must reroute any manually defined
   +                  # ancestries around the deleted release

    - name: 1.2.2
   -  after: 1.2.1    # this data is useless on a deleted release
   +  delete: True    # primary goal: delete this release

    - name: 1.2.1


Git scanner has trouble with conflicting reversed cherry-picks
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Git scanner uses a simple dictionary object to track vanquished notes, but the order in which the Git scanner
investigates parent commits is undefined.  Here's a visual example of the problem that can happen::

    *   abc  Merge topic, preserving new feature
    |\
    | * 789  Cherry-pick commit 123
    * | 456  Revert commit 123
    * | 123  Develop feature
    |/
    *

If the Git scanner chooses to investigate the left side first, it will follow these decisions:

1. Commit ``456`` shows a deletion of note A.  Will mark as vanquished.
2. Commit ``123`` shows a creation of note A.  Note A is vanquished, so it will not be reported.
3. Commit ``789`` shows a creation of note A.  Note A is vanquished, so it will not be reported.

In the above logic, step 3 is wrong.  The logic should read like this:

1. Commit ``456`` shows a deletion of note A.  Will mark as vanquished.
2. Commit ``123`` shows a creation of note A.  Note A is vanquished, so it will not be reported.
3. Commit ``789`` shows a creation of note A.  Will report note.

Presently, the commit graph described in this scenario is not expected to be common, if it ever happens at all.
Iterate as necessary.


Git scanner is blind to changes inside merge commits
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you create a note, modify a note, or rename a note in a merge commit, the Git scanner (used to identify the commit
when a note was added) *will not see that change*.

Algorithmically, this can be fixed, but because the current convention is that merge commits should not change the
tree (beyond resolving merge conflicts), it's difficult to prioritize fixing this right now.


Git scanner has trouble with note rename tracking
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In a Git-backed ``seano`` database, ``seano`` will follow exact renames of note files.  This is useful in particular,
when you have a scenario where the database was moved at some point in history, and you want to run
``seano edit <commit-id>`` on one of the older commits.  ``seano`` has been told the location of the database
today, but in that old commit, it's in the old folder, so an ordinary
``git show <commit-id> --name-only --diff-filter=AC -- <db-path>`` won't find any notes, because it's looking at the
wrong directory.

Oh, and also, renaming/moving your database shouldn't cause all of your release notes in all of history to suddenly
look like they were created in ``HEAD``.  Yea, that too.  That's important.

So how does it work?  Any time we need to read the Git history of a database, we always start at ``HEAD`` and work our
way back through history, tracking renames as we go.  This allows us to find the correct original commit that
introduces a specific note file, even if the database has been renamed N times throughout history.

More amazingly, in the ``seano edit <commit-id>`` scenario, we use the same algorithm, but with the opposite
goal: to find a *current note file* which was, following renames, introduced in a given commit.  Again, we start at
``HEAD``, and trace our way back through the commit graph; because we're tracking renames per-file, when we find the
files added in our desired commit, we also know the equivalent filename in ``HEAD``, and that's how we know which note
to open, even though it's been renamed N times throughout history.

Here's the problem.  That algorithm is *really simple*.  Like, so simple that it can be easily fooled by certain
commit graphs::

    *   789  Merge
    |\
    | * 456  Move entire seano database
    * | 123  Fix spelling error in old note
    |/
    *

In the above scenario, if the Git scanner happens to investigate the left side first, it will not detect the edited
note in commit ``123``, because the filename in which the edit took place is not a file where the Git scanner is
looking.  When the Git scanner gets to commit ``456``, it will see the rename and begin looking in the new location,
but it's too late.  The consequence here is that ``seano edit -m 123`` may not work as intended.

A word of advice: if you choose to rename/move a ``seano`` database (or even a single note file), do so such that:

1. All rename operations are 100% exact renames (no modifications)
2. If you make modifications to note files, do so in a different commit so that all renames are exact renames
3. Avoid merging any branch which edits the ``seano`` database, forked from a commit before the rename, into any commit
   after the rename.  (i.e., avoid editing the database in parallel with the rename)

If you follow that advise, you should successfully avoid getting bit by shortcomings in ``seano``'s note rename
detection logic.
