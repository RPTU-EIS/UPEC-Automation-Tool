from itertools import pairwise

from src.constants import FANOUT


def shortest_path(fanin, fanout, source: str, target: str, fan_direction: bool) -> pairwise:
    """Finds the shortest path between the source signal and the target signal.

    Note:
        Based on bidirectional_shortest_path() of **NetworkX**

    Args:
        source: Name of the source signal
        target: Name of the target signal
        fan_direction: Direction of the analysis (**True:** Fan-out | **False:** Fan-in)

    Returns:
        Pairwise source and target signals
    """

    if fan_direction == FANOUT:
        result = shortest_path_helper(fanin, fanout, source, target)
    else:
        result = shortest_path_helper(fanin, fanout, target, source)

    # If there is no path
    if result is None:
        return None

    pred, succ, w = result

    path = []
    while w is not None:
        path.append(w)
        w = pred[w]

    path.reverse()

    w = succ[path[-1]]
    while w is not None:
        path.append(w)
        w = succ[w]

    return pairwise(path)


def shortest_path_helper(fanin, fanout, source: str, target: str) -> tuple[dict, dict, str] | None:
    """
    Note:
        Based on _bidirectional_pred_succ() of **NetworkX**

    Args:
        source: Name of the source signal
        target: Name of the target signal

    Returns:
        Dictionary of predecessors from w to the source
        Dictionary of successors from w to the target
        w
    """
    if target == source:
        return {target: None}, {source: None}, source

    g_pred = fanin
    g_succ = fanout

    pred = {source: None}
    succ = {target: None}

    forward_fringe = [source]
    reverse_fringe = [target]

    while forward_fringe and reverse_fringe:
        if len(forward_fringe) <= len(reverse_fringe):
            w, forward_fringe = BFS_search(forward_fringe, g_succ, pred, succ)
        else:
            w, reverse_fringe = BFS_search(reverse_fringe, g_pred, succ, pred)

        if w is not None:
            return pred, succ, w
    return None


def BFS_search(fringe, graph, visited_this_side, visited_other_side):
    next_fringe = []
    for v in fringe:
        for w in graph.get(v, []):
            if w not in visited_this_side:
                visited_this_side[w] = v
                next_fringe.append(w)
            if w in visited_other_side:
                return w, next_fringe
    return None, next_fringe
