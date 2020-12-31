"""
pyseano/db/release_sorting.py

As it turns out, sorting a list of releases is hard.
To improve readability and testability, the algorithm is isolated to here.
"""

import itertools
import logging
import sys

log = logging.getLogger(__name__)

if sys.hexversion < 0x3000000:
    range = xrange


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

        # And return our magical sort order value:

        return edge_delta, node_index

    while todo:

        candidates = list_nodes_eligible_for_printing()

        if not candidates:
            for x in sorted(todo):
                log.warn('Having trouble flattening ancestry history: %s might be in the wrong position.', x)
                yield x
                todo.remove(x)
                break
            continue

        if len(candidates) > 1:
            candidates.sort(key=human_graph_sort_order)

        # Pick the candidate that adds the fewest number of edges:

        yield candidates[0]
        todo.remove(candidates[0])
