"""
seano_cli/constants.py

Shared constants used by seano
"""

SEANO_DOTFILE_FILE = '.seano'
SEANO_DOTFILE_DB_PATH_KEY = 'seano-db' # e.g.: "seano-db: ./foo/bar"

SEANO_DEFAULT_EDITOR = 'vim -O'

SEANO_CONFIG_FILE = 'seano-config.yaml'
SEANO_CONFIG_TEMPLATE = '''---
# ''' + SEANO_CONFIG_FILE + r'''
# seano configuration file
#
# This file is used both as a configuration for seano, and as a foundation for
# the big fat Json file you get after running a seano query.  Any keys you set
# here will show up in the root object of a query result, and may be consumed
# by any views you're using to make presentable release notes.

# Localized name of project:
project_name:
  en-US: Acme Piano Dropper

# seano needs to know the current version of the product.  You may:
# - specify it here
# - specify it at a command-line every time you perform a seano query
#   (in which case you may delete it here)
#
# Hint: If you use Zarf to run a seano query, Zarf passes its knowledge of the
# current project version to seano automatically, and you can delete this
# configuration here.
#current_version: 0.0.1d1

# seano needs to know the release ancestors of HEAD -- i.e., which releases
# the current working tree is a descendant of.  Normally, this is just one
# release, but in highly parallel work (in particular with back-porting
# patches to older releases) it's possible to have more than one ancestor
# release.  You may:
# * specify them here
# * track this project in Git so that seano can deduce them automatically
#   (in which case you may delete it here)
#
# Hint: You really should track this project in Git, and the delete this
# configuration here.
#parent_versions:
#- name: 0.0.0

# Even when Zarf and Git are used to automate release identification,
# inevitably, you will want to add per-release metadata so that the data can
# be used in documentation.  Here's the template releases list.  For each
# release, you may add any members you want to any release, and they will show
# up in the final releases list after a query.
releases:

# seano needs to know what releases exist, and the ancestry relationships
# between them.  You may:
# * declare all releases & ancestry relationships here (for all releases)
# * track this project in Git so that seano can auto-detect releases and auto-
#   deduce ancestry relationships
#   (in which case you won't have to declare most releases here)
#- name:  0.0.0

# Even if you track this project in Git, you may find that in some obscure
# cases you still need to whack seano with a stick because it got something
# wrong.  One of the common ways this happens is when Git detects a tag that
# you don't want to be a release.  Here's how to burn a tag that exists in
# your repository, without actually deleting the tag in Git:
#
#   releases:
#
#   - name: 1.2.3
#     delete: True # This tag does not represent a release we want
#
# Another thing that can go wrong is when you want to represent releases that
# predate the repository.  Here's how you can manually create a release
# ancestry graph beyond what Git can mine:
#
#   == seano config syntax ==        == analogous to this commit graph ==
#
#   releases:
#
#   - name:  1.2.0                  *  Implement birddog (tags: v1.2.0)
#     after:                        |
#     - name: 1.1.1                 |
#                                   |
#   - name:  1.1.1                  *  Merge v1.0.5 into master (tags: v1.1.1)
#     after:                        |\
#     - name: 1.1.0                 | |
#     - name: 1.0.5                 | |
#       is-backstory: true          | |
#                                   | |
#   - name:  1.0.5                  | *  Fix bug (tags: v1.0.5)
#     after:                        | |
#     - name: 1.0.4                 | |
#                                   | |
#   - name:  1.1.0                  * |  Implement fishcat (tags: v1.1.0)
#     after:                        | |
#     - name: 1.0.4                 | |
#                                   |/
#   - name: 1.0.4                   *  Implement foobar (tags: v1.0.4)
#     ... you get the picture       |
#
# Manual definitions of release ancestry are overlaid on top of ancestry
# auto-detected by the underlying repository.  This is normally handy, but can
# cause a little trouble when you need to manually insert a release that can't
# be tagged (we weren't as rigorous with our committing habits a decade ago).
# Here's how to manually insert a release in between two existing tags:
#
#   == seano config syntax ==        == example commit graph ==
#
#   releases:
#
#   - name: 2.1                     *  Final touches (tags: v2.1)
#     after:                        |
#     - name: 2.0                   |
#     - name: 1.5                   |
#       delete: True                |
#                                   |
#   - name: 2.0                     |  2.0 release, squashed into oblivion
#     after:                        |    (no commit to tag!)
#     - name: 1.5                   |
#                                   |
#   # (no need to declare 1.5)      *  Implement foobar (tags: v1.5)
#
# There's a lot to unpack in the above example.  Here's what's going on:
# * Even though 2.1 is auto-detected via Git, we're manually declaring it so
#   that we can edit its ancestry.
# * Declare that 2.1 is after 2.0.  Git wouldn't have auto-detected this, so
#   this is new knowledge.
# * Git auto-detects that 2.1 comes after 1.5 (because it's the next tag in
#   the repository), so it adds a corresponding ancestry link.  We don't want
#   that ancestry link at all, so mark it for deletion.
# * 2.0 is not auto-detected via Git because there is no tag.  Declare it, so
#   that it exists.
# * We already manually declared that 2.1 comes after 2.0.  Now, we must
#   declare that 2.0 comes after 1.5.
# * We don't need to declare that 1.5 is before 2.0, because we already
#   declared that 2.0 is after 1.5, and seano will automatically doubly-link
#   all ancestries at query time.
# * We don't need to delete the link from 1.5 to 2.1, because we already
#   marked the link for deletion on the other end of the link.
'''

SEANO_DB_SUBDIR = 'v1'
SEANO_EXTERN_NOTE_EXTENSION_PREFIX = '.extern-'
SEANO_NOTE_EXTENSION = '.yaml'
SEANO_NOTE_DEFAULT_TEMPLATE_CONTENTS = '''---
risk: One of low, medium, high; does not reflect deployment tricks to lower risk

tickets:
- URL to JIRA ticket

min-supported-os:        # Only include this section if you changed the minimum supported OS
  os1: "version number"  # You must re-specify all supported OSs every time you change a value
  os2: "version number"  # OS versions should be quoted to avoid yaml assuming numeric type

max-supported-os:        # Only include this section if you changed the maximum supported OS
  os1: "version number"  # You must re-specify all supported OSs every time you change a value
  os2: "version number"  # OS versions should be quoted to avoid yaml assuming numeric type

employee-milestones-list-loc-md:
- en-US: Short description of a big change
- en-US: Use sparingly, because these are printed prominently

customer-short-loc-hlist-md:
  en-US:
  - Short sentence explaining this change to customers
  - "This is an hlist, which means:":
    - you can express a hierarchy here
  - This text usually comes from the `#workroom-releasenotes` channel in Slack

employee-short-loc-hlist-md:
  en-US:
  - Short sentence explaining this change to CE employees
  - "This is an hlist, which means:":
    - you can express a hierarchy here
  - This text usually comes from the developer who made the change
  - "For consistency, use imperative tense, without a full stop, such as:":
    - Cook the bacon
    - Don't crash when bacon is not loaded
    - You usually only need one line; these are just examples

employee-upgrade-loc-md:
  en-US: |
    You are talking to your coworkers on other teams, and Ops.

    Explain what needs to be updated to adopt this change.  Although this
    usually refers to breaking changes, certain new features may also be worth
    mentioning, if the lack of using them causes headaches.

    This field is a single large Markdown blob.

    If no usages need updating, then delete this section.

employee-technical-loc-md:
  en-US: |
    You are talking to your future self and Ops.

    What was the problem?  What solutions did you reject?  Why did you choose
    this solution?  What might go wrong?  What can Ops do to resolve an outage
    over the weekend?

    This field is a single large Markdown blob.  Explaining details is
    good.

mc-technical-loc-md:
  en-US: |
    You are talking to a Tier-2 Member Care Representative.

    What changed?  How does this impact users?  How does this impact MC?

    Assume something *is going wrong*.  What caused it?  How can MC resolve it
    over the weekend?

    T2's have a dedicated block of time for catching up on release notes for
    all products at CE.  They oversee many products, so we try to keep this
    section as blunt and brief as is practical.  T2's are technically inclined,
    so feel free to use technical jargon to shorten explanations.

    Don't be afraid to be terse; if a T2 has questions, they'll often hop over
    to the `employee-technical-loc-md` section to look for more details.

    Sometimes a screenshot is a great way to shorten an explanation:

    <img width=100 alt="red heart with black outline" src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj4KICA8cGF0aCBkPSJNNTAsMzBjOS0yMiA0Mi0yNCA0OCwwYzUsNDAtNDAsNDAtNDgsNjVjLTgtMjUtNTQtMjUtNDgtNjVjIDYtMjQgMzktMjIgNDgsMCB6IiBmaWxsPSIjRjAwIiBzdHJva2U9IiMwMDAiLz4KPC9zdmc+" />

    If what you want to write here is identical to what you've already written
    in another section, you can use Yaml's reference syntax to copy another
    section.  You can copy any `*-loc-md` field, or any `*-loc-hlist-md` field.
    Example:

    ```yaml
    employee-short-loc-hlist-md: &empl-short
      en-US: #                   ^^^^^^^^^^^  Mark section to copy
      - Hello, this is an internal release note

    mc-technical-loc-md: *empl-short
    #                    ^^^^^^^^^^^  Copy contents of the marked section
    ```

    If this change doesn't impact customers or Member Care, or is too obscure
    to mention, then delete this section.

qa-technical-loc-md:
  en-US: |
    You are talking to QA.

    What new features need to be tested?  What old features need to be
    regression-tested?

    QA uses this section to perform QA, and also as a "diff" to update their
    own test plan archives.

    This field is a single large Markdown blob.  Explaining details is good.
    Assume that QA has zero knowledge of *what* to test, but that given that
    knowledge, they know *how* to test it.  Be specific in descriptions;
    avoid generalizations when practical.  Be as technical as you want.
    If QA has questions, they'll ask you.
'''

# Generally speaking, notes in seano contain keys that are designed
# to be consumed by humans, and by seano views.  When a key is
# intended to be consumed by seano itself for internal plumbing
# unrelated to release notes themselves, that's weird.  We like to
# prefix such keys with `x-seano-`, to help point out that the keys
# are very likely managed by seano itself and may be autonomously
# added or removed, and that views should be hesitant to rely on
# them.

SEANO_NOTE_KEY_RELPATH_TO_ORIGINAL_NOTE = 'x-seano-relpath-to-original'
SEANO_NOTE_KEY_SHA1_OF_ORIGINAL_NOTE = 'x-seano-sha1-of-original'
SEANO_NOTE_KEY_IS_GHOST = 'x-seano-is-ghost'
