"""
seano_cli/db/release_sorting.py

As it turns out, sorting a list of releases is hard.
To improve readability and testability, the algorithm is isolated to here.
"""

import itertools
import logging
import re
import sys

log = logging.getLogger(__name__)

if sys.hexversion < 0x3000000:
    range = xrange


alpha_or_numeric_regex = re.compile(r'(\d+|[a-zA-Z]+)')
numeric_regex = re.compile(r'(\d+)')

def semverish_sort_key(version_string):
    """
    Returns an opaque, comparable value representing the given string.  The
    nuances of the comparable value are engineered to be desirable, assuming
    that the string is some kind of version string.  This algorithm is
    compatible with most common versioning patterns, including SemVer.
    """
    prerelease, _, build = version_string.partition('+')
    try: release = re.search(r'^[0-9\.]+', prerelease).group(0)
    except: release = ''
    prerelease = prerelease[len(release):]

    release    = filter(alpha_or_numeric_regex.match, alpha_or_numeric_regex.split(release))
    prerelease = filter(alpha_or_numeric_regex.match, alpha_or_numeric_regex.split(prerelease))
    build      = filter(alpha_or_numeric_regex.match, alpha_or_numeric_regex.split(build))

    release    = [int(x) if numeric_regex.match(x) else x[0] for x in release]
    prerelease = [int(x) if numeric_regex.match(x) else x[0] for x in prerelease]
    build      = [int(x) if numeric_regex.match(x) else x[0] for x in build]

    return [release, prerelease, build]


def sorted_release_names_from_releases(release_dicts):

    # ABK: This sort algorithm behaves a lot like Git does, and should be good enough in most
    #      cases.  If you're developing a fancy 2D graph of the releases, then the sort order
    #      doesn't matter at all, because you're going to manually read the before and after
    #      lists on each release to establish your topology.  For a more primitive 1D view
    #      (where everything is a flat list), having the list of releases pre-sorted in some
    #      sort of sane manner is handy, because it lets you just go down the list and print
    #      everything in order, despite the concept of non-linear graph flattening being
    #      somewhat non-trivial.

    # Keep track of the nodes we have remaining to print:
    todo = set(release_dicts.keys())

    def list_nodes_eligible_for_printing():

        # Nodes eligible for printing is defined as:

        result = [x for x in todo                           # Any release in todo...
                  if all([                                      # Where all...
                          y['name'] not in todo                         # have been printed
                          for y in release_dicts[x]['before']])]    # of its descendants...

        return result

    _ancestors = {}
    def get_ancestors(node):
        try:
            return _ancestors[node]
        except KeyError:
            result = set()
            for r in release_dicts[node]['after']:
                r = r['name']
                result.add(r)
                result = result | get_ancestors(r)
            _ancestors[node] = result
            return result

    _descendants = {}
    def get_descendants(node):
        try:
            return _descendants[node]
        except KeyError:
            result = set()
            for r in release_dicts[node]['before']:
                r = r['name']
                result.add(r)
                result = result | get_descendants(r)
            _descendants[node] = result
            return result

    def human_graph_sort_order(node):

        # An edge delta is used to predict which nodes in the graph are the most pleasing
        # to a human eye to print next.  In graph theory, "pleasing" roughly translates to
        # choosing a node that attaches to the most non-transitive exposed edges, or
        # exposes the fewest new non-transitive edges.

        release = release_dicts[node]

        # List all descendants:
        before = [x['name'] for x in release['before']]
        # Remove transitive descendants:
        for candidate in list(before):
            if candidate in set().union(*[get_ancestors(x) for x in before if x != candidate]):
                before.remove(candidate)

        # List all ancestors:
        after = [x['name'] for x in release['after']]
        # Remove transitive ancestors:
        for candidate in list(after):
            if candidate in set().union(*[get_ancestors(x) for x in after if x != candidate]):
                after.remove(candidate)

        # And here's our edge delta:
        edge_delta = len(after) - len(before)

        # It's common for edge deltas to be equal.  As a second-stage sort, let's look at
        # the index this node is in its descendants' ancestor list.  Generally speaking,
        # the lower the index, the more likely this is the trunk lineage; the higher the
        # index, the more likely this is a topic lineage.

        node_index = [release_dicts[x['name']]['after'] for x in release['before']]
        node_index = [zip(x, range(len(x))) for x in node_index]
        node_index = itertools.chain(*node_index)
        node_index = [x[1] for x in node_index if x[0]['name'] == node]
        node_index = sum(node_index)
        # Make it negative, so that it sorts in the same direction as the edge delta:
        node_index = 0 - node_index

        # It's rare, but it's possible for the combination of the edge delta and node index
        # to be equal.  As a third-stage sort, let's look at the total number of descendants.
        # Generally speaking, this tends to prioritize keeping the releases of longer-running
        # lineages grouped together in an unbroken series.  This pattern is completely
        # arbitrary and does not have a solid grounding in graph theory, so it may need
        # reworking in the future.  For now, it's a decent way to help keep the sort order
        # stable.
        num_of_descendants = len(get_descendants(node))
        # Make it negative, so that it sorts in the same direction as the edge delta:
        num_of_descendants = 0 - num_of_descendants

        # And return our magical sort order value:

        return edge_delta, node_index, num_of_descendants

    while todo:

        candidates = list_nodes_eligible_for_printing()

        if not candidates:
            # If we don't have any explicit candidates, then pick a node at random,
            # and warn the user that this is happening.
            for x in sorted(todo):
                log.warn('Having trouble flattening ancestry history: %s might be in the wrong position.', x)
                yield x
                todo.remove(x)
                break
            continue

        if len(candidates) > 1:
            # If we have more than one candidate, try to sort them.  The human_graph_sort_order()
            # function (above) tries to generate a sortable value for any given node that we can
            # use to identify which node is best to print next, but it's not perfect.
            #
            # Pre-load the sort order values (because we'll be analyzing them in a moment):
            candidates = [(c, human_graph_sort_order(c)) for c in candidates]

            # Sort by our magical sort values:
            candidates.sort(key=lambda x: x[1])

            # Identify duplicate sort values.  Duplicate sort values indicate scenarios where the
            # sort order function is not smart enough.  When duplicate sort values are found, warn
            # the user.
            #
            # Note that we don't actually care if there are *any* duplicates *anywhere* -- we only
            # care if there is an N-way tie for first place.
            nondeterministic_conflicts = [x[0] for x in candidates if x[1] == candidates[0][1]]
            if len(nondeterministic_conflicts) > 1:
                log.warn("Having trouble flattening ancestry history: can't decide which of %s should come first." % (
                         ' or '.join(nondeterministic_conflicts),))

            # Convert the candidates list back to its original schema (strip out the sort values).
            # We will arbitrarily pick the one at the beginning of the list.
            candidates = [x[0] for x in candidates]

        # Pick the candidate that is deemed the most desirable by our magical sort algorithm:
        yield candidates[0]
        todo.remove(candidates[0])
