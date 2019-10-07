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
5. Cherry-picking a commit should also pull over associated notes witout requiring fixups
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
          "after" : ["1.2.2"],   # list of immediate ancestor tags
          "before" : ["1.2.4"],  # list of immediate descendant tags
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
renderers project-specific knowledge.  Examples of such knowledge include the project name, URL, etc.

We do not yet have a recommended schema of data to store in ``seano``; bear with us while we figure this out.  To see
some of the experiments in this area, take a peek at most of the ``seano``-based `documentation modules in the Mac
Client`__.

.. _MacClientSeanoDocs: https://github.com/redacted/redacted/tree/master/mac/doc

__ MacClientSeanoDocs_

.. warning::

    ``seano`` does not yet support automatically deducing tags from Git.  It's on the todo list.  In the meantime, you
    need to do three things to tell ``seano`` what it needs to know to organize information as intended:

    1. ``seano_config.yaml`` must contain a ``parent_versions`` key that contains a list of all parent tags of
       ``HEAD``, like this:

        .. code-block:: yaml

            parent_versions:
            - 1.2.3

    2. ``seano_config.yaml`` must contain a ``releases`` key that defines all past releases.  Refer to the Onboarding
       section for how that looks.
    3. The note files that are no longer applicable to ``HEAD`` must have a ``releases`` key added defining which
       release those notes were released in.  Refer to the Onboarding section for how that looks.

    Essentially, all ``HEAD`` notes will work as expected, but all non-``HEAD`` notes must be treated like they were
    onboarded.

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
``doc/seano-db/v1/46/543fbda3bedd85c50385ffc19fe576.yaml``.  All of the following will find it::

    $ seano edit HEAD~~~~    # 4 commits ago
    $ seano edit 5c6ff85     # Git commit ID
    $ seano edit 46/543      # partial path with seano note ID
    $ seano edit 46543       # seano note ID

To edit all notes created between ``v1.2.4`` and ``v1.2.5``::

    $ seano edit v1.2.4..v1.2.5

Reserved keys
-------------

Generally speaking, ``seano`` only stores objects, and you put whatever data you want into it.  However, ``seano`` does
own some keys; avoid setting them unless you intend to override them.

Notes have these keys automatically set on them:

* ``commits``: list of commit IDs that supply this note *(supported SCMs)*
* ``id``: the ``seano`` note ID
* ``releases``: list of release names in which this note was released *(supported SCMs)*
    * In unsupported SCMs, if you don't set this key, the note will appear in the ``HEAD`` release
* ``refs``: unused; reserved for future use

Releases have these keys automatically set on them:

* ``after``: list of names of releases that are immediate ancestors of this release *(supported SCMs)*
    * In unsupported SCMs, if you do not set either ``before`` or ``after`` on a release, ``seano`` may get the release
      order incorrect
* ``before``: list of names of releases that are immediate descendants of this release *(supported SCMs)*
    * In unsupported SCMs, if you do not set either ``before`` or ``after`` on a release, ``seano`` may get the release
      order incorrect
* ``commit``: the commit ID of this release *(supported SCMs)*
* ``name``: name of this release (not localized)
* ``notes``: list of note dictionaries
* ``refs``: unused; reserved for future use

The following keys are functional in ``seano-config.yaml``:

* ``current_version``: the current version of the project
    * Always required (``seano`` does not want to be responsible for deriving this)
    * Can be set here, or with ``--current-version`` when invoking ``seano``
* ``parent_versions``: list of names of releases that are immediate ancestors of HEAD *(supported SCMs)*
    * In unsupported SCMs, you must set this
* ``releases``: list of release dictionaries
    * In unsupported SCMs, this is where you manually set keys on releases

Feel free to save any other key in ``seano``.

Querying data
-------------

Getting data out of a ``seano`` database is done using ``seano query``.  We hope to make this process more
automated/integrated with Zarf/Sphinx in the future.  In the meantime, feel free to browse the runtime documentation::

    $ seano query -h

Onboarding old data
-------------------

If the project has never used ``seano`` before, you must first create the ``seano`` database::

    $ seano init

To import old notes into an existing ``seano`` database:

1. Open ``doc/seano-db/seano-config.yaml`` in your favorite text editor.
2. In the ``releases`` list, make sure a release is defined with the name of the release you're importing.  The list
   looks something like this:

    .. code-block:: yaml

        releases:
        - name:  1.2.3
          after: 1.2.2
        - name:  1.2.2
          after:
          - 1.2.1   # `after` can optionally be a list
          - 1.2.0
        # ... etc

3. Run ``seano new -n <N>``, where ``<N>`` is the number of release notes you're adding for this release.  By
   creating ``N`` new notes all at once and editing them in ascending order of filename, you preserve the original
   sort order of the release notes, so that when you render old release notes using your new tools, the output has a
   chance at actually looking remarkably the same as it used to.
4. For each note you added, explicitly set a value for the ``releases`` key.  This value is the name of the release
   from when you defined the release in the ``releases`` list in ``seano-config.yaml``.  By explicitly setting a
   release name, you are instructing ``seano`` to not try to automatically deduce the release name from the
   commit graph.

.. note::

    It is highly recommended to commit regularly when importing old release notes.  ``seano`` does not have any "undo"
    concept at all; the power to undo mistakes is granted only by the underlying repository.  If you do not commit
    regularly, it can be difficult to undo an erroneous or mistaken ``seano new`` invocation without also
    destroying desired but uncommitted work.
