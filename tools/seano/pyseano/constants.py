"""
pyseano/constants.py

Shared constants used by seano
"""

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
#- 0.0.0

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
# wrong.  The most common example of such a scenario is when you wish to have
# a full and accurate release history of the entire life of the project, but
# some of the ancient releases use weird tag names that seano doesn't auto-
# detect, or maybe they pre-date the repository itself.  Whatever the reason,
# here's how you manually define ancestry relationships between releases:
#
#   == seano config syntax ==        == example commit graph ==
#
#   releases:
#
#   - name:  1.2.0                  *  Implement birddog (tags: v1.2.0)
#     after: 1.1.1                  |
#                                   |
#   - name:  1.1.1                  *  Merge v1.0.5 into master (tags: v1.1.1)
#     after:                        |\
#     - 1.1.0                       | |
#     - 1.0.5                       | |
#                                   | |
#   - name:  1.0.5                  | *  Fix bug (tags: v1.0.5)
#     after: 1.0.4                  | |
#                                   | |
#   - name:  1.1.0                  * |  Implement fishcat (tags: v1.1.0)
#     after: 1.0.4                  | |
#                                   |/
#   - name: 1.0.4                   *  Implement foobar (tags: v1.0.4)
#     ... you get the picture       |
#
# Note that any use of before/after overrides seano's automatic logic when a
# Git repository exists.  If you're using a Git repository but want to
# manually insert a release that doesn't otherwise exist, here's how you can
# do it:
#
#   == seano config syntax ==        == example commit graph ==
#
#   releases:
#
#   - name:  1.1.0                  *  Final touches (tags: v1.1.0)
#     after: 1.1.0b1                |
#                                   |
#   - name:  1.1.0b1                *  Public beta (no tag!)
#                                   |
#   - name:   1.0.0                 *  Implement foobar (tags: v1.0.0)
#     before: 1.1.0b1               |
#
# There's a lot to unpack in the above example.  Here's what's going on:
# * Even though 1.1.0 is auto-detected via Git, we're manually declaring it so
#   that we can override a member.
# * By setting `after` on 1.1.0, we're switching ONLY the `after` list on
#   1.1.0 to full manual, and providing the full list (in this case, a single
#   value).  The `before` list on 1.1.0 remains automatically deduced via Git.
# * 1.1.0b1 is not auto-detected via Git, because there is no tag.  Declare it
#   so that it exists.
# * Even though 1.0.0 is auto-detected via Git, we're manually declaring it so
#   that we can override a member.
# * By setting `before` on 1.0.0, we're switching ONLY the `before` list on
#   1.0.0 to full manual, and providing the full list (in this case, a single
#   value).  The `after` list on 1.0.0 remains automatically deduced via Git.
# * Even though 1.1.0b1 is a manually declared release, its `before` and
#   `after` lists are automatic.  In this case, `before` is automatically
#   1.1.0, and `after` is automatically 1.0.0.
'''

SEANO_DB_SUBDIR = 'v1'
SEANO_NOTE_EXTENSION = '.yaml'
SEANO_NOTE_DEFAULT_TEMPLATE_CONTENTS = '''---
tickets:
- URL to JIRA/Redmine ticket

customer-short-loc-hlist-rst:
  en-US:
  - Short sentence explaining this change to CE customers
  - "This is an hlist, which means:":
    - you can express a hierarchy here
  - This text usually comes from the ``#workroom-releasenotes`` channel in Slack

employee-short-loc-hlist-rst:
  en-US:
  - Short sentence explaining this change to CE employees
  - "This is an hlist, which means:":
    - you can express a hierarchy here
  - This text usually comes from the developer who made the change
  - "For consistency, use imperative tense, without a full stop, such as:":
    - Cook the bacon
    - Don't crash when bacon is not loaded
    - You usually only need one line; these are just examples

employee-technical-loc-rst:
  en-US: |
    You are talking to your future self and Ops.

    What changed?

    What might go wrong?

    What can Ops do to resolve an outage over the weekend?

    This field is a single large reStructuredText blob.  Go wild.  Explaining
    details is good.

cs-technical-loc-rst:
  en-US: |
    You are talking to a Tier-2 Customer Service Representative.

    What changed?

    How does this change interact with the environment?

    How does this change interact with the user?

    Assume something *is going wrong*.  What caused it?  How can a Customer
    Service Representative resolve it over the weekend?

    This field is a single large reStructuredText blob.  Explaining details is
    good, but tend toward environmental and human information over API
    architecture explanations.

    If this change is not worth mentioning to Customer Service at all, then
    delete this section.

employee-testing-loc-rst:
  en-US: |
    Explain what needs to be tested (new things to test) and/or re-tested
    (impact requiring regression testing).  Target audience is QA.

    In addition to informing QA of what to test/re-test, this field also is
    used by QA as a "diff" to be applied to their official test plans.

    This field is a single large reStructuredText blob.  Go wild.  Explaining
    details is good.
'''
