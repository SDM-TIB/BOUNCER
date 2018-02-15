
__author__ = "Kemele M. Endris"

import networkx as nx
import matplotlib.pyplot as plt

from mulder.mediator.decomposition import utils


def append_dependency(depends, s, s2, label, context):
    if s in depends:
        if label in depends[s]:
            if s2 in depends[s][label]:
                depends[s][label][s2].append(context)
            else:
                depends[s][label][s2] = [context]
        else:
            depends[s][label] = {s2: [context]}
    else:
        depends[s] = {label: {s2: [context]}}

    return depends


def create_dependency_graph(res, stars, query, policies, queryConnections):
    """
        Return set of dependency graphs, if exists, for a set of stars with a given policy
    :param res: matching molecule templates per star {s:[M1, M2, ..], ..}
    :param stars: set of star shaped subqueries {s:[tp1, tp2, ..], ..}
    :param projArgs:
    :param policies:
    :param queryConnections:
    :return:
    """
    dependency_graph = []
    # osConn = getStarsConnectionsOS(stars)
    # ooConn = getStarsConnectionsOO(stars, query.prefs)
    # projVars = query.args

    depends = dict()
    deniedProjections = dict()

    for s in policies:
        for m in policies[s]:
            for policy in policies[s][m]:
                # TODO: send osConn and ooConn as queryConnections to get the correct label for NonJoin dependencies,
                # TODO: and may be projVars too
                label, dVars = get_label(s, m, policy, queryConnections, stars, query)
                # label: 0 - Independent(I), -1 - Dependent on Join (DJ), -2 - Dependent on Non Join (DNJ), and
                # 1 - Dependent on Both (DJ and DNJ), and 2 - Dependency can not be satisfied
                if label == 0:
                    preds = [p for c in list(dVars.values()) for p in c]
                    context = {"molecule": m, 'dataset': policy.dataset, "predicates": preds}
                    depends = append_dependency(depends, s, s, 'I', context)
                elif label == -1:
                    for s2 in dVars:
                        context = {"molecule": m, 'dataset': policy.dataset, "predicates": dVars[s2]}
                        depends = append_dependency(depends, s, s2, 'DJ', context)
                elif label == -2:
                    # if subject is constant, then this star can be treated as Independent
                    if stars[s][0].subject.constant:
                        preds = [p for c in list(dVars.values()) for p in c]
                        context = {"molecule": m, 'dataset': policy.dataset, "predicates": preds}
                        depends = append_dependency(depends, s, s, 'I', context)
                        continue

                    cVars = []
                    cpVars = {}
                    for c in queryConnections:
                        if s in queryConnections[c]:
                            cVars.append(c)
                            preds = getPredicates(stars[s], query.prefs)
                            cpVars[c] = preds
                    if len(cVars) == 0:
                        return {}
                    preds = [p for c in list(dVars.values()) for p in c]
                    for s2 in cpVars:
                        context = {"molecule": m, 'dataset': policy.dataset, "predicates": preds}
                        depends = append_dependency(depends, s, s2, 'DNJ', context)

                    # context = {"Molecule": m, "policy": policy, "predicates": cpVars}
                    # depends = append_dependency(depends, s, s2, 'DNJ', context)
                    #
                elif label == 1:
                    jVars = dVars[0]
                    njVars = dVars[1]
                    for s2 in jVars:
                        context = {"molecule": m, 'dataset': policy.dataset, "predicates": jVars[s2]}
                        depends = append_dependency(depends, s, s2, 'DJ', context)

                    if stars[s][0].subject.constant:
                        continue
                    cVars = []
                    cpVars = {}
                    for c in queryConnections:
                        if s in queryConnections[c]:
                            cVars.append(c)
                            preds = getPredicates(stars[s], query.prefs)
                            cpVars[c] = preds
                    if len(cVars) > 0:
                        preds = [p for c in list(dVars.values()) for p in c]
                        for s2 in cpVars:
                            context = {"molecule": m, 'dataset': policy.dataset, "predicates": preds}
                            depends = append_dependency(depends, s, s2, 'DNJ', context)

                        # context = {"Molecule": m, "policy": policy, "predicates": cpVars}
                        # depends = append_dependency(depends, s, s2, 'DNJ', context)
                elif label == 2:
                    # If projection variable has no access grant
                    for s2 in dVars:
                        context = {"molecule": m, 'dataset': policy.dataset, "predicates": dVars[s2]}
                        depends = append_dependency(depends, s, s2, 'NX', context)
                        if s in deniedProjections:
                            deniedProjections[s].append(s2)
                        else:
                            deniedProjections[s] = [s2]

                if 'DJ' in depends and len(depends[s]['DJ']) > 1:
                    print("Multiple dependency graph must be created with one DJ to others (DNJ+I)")

                if 'DNJ' in depends and len(depends[s]['DNJ']) > 1:
                    print("Multiple dependency graph must be created with one DNJ to others (DJ+I)")

    # This was checked in AccessControl.get_runnable_sequences() for sanity check
    if len(deniedProjections) > 0:
        # for each denied proj, there exist at least one other dependency: DJ, I, or DNJ
        for d in deniedProjections:
            if 'DJ' in depends[d] or 'DNJ' in depends[d] or 'I' in depends[d]:
                continue
            else:
                return {}

    multipleDependency = [s for s in depends if 'DJ' in depends and len(depends[s]['DJ']) > 1 or 'DNJ' in depends and len(depends[s]['DNJ']) > 1]
    if len(multipleDependency) > 0:
        singledependencies = [s for s in depends if 'DJ' in depends and len(depends[s]['DJ']) <= 1 and 'DNJ' in depends and len(depends[s]['DNJ']) <= 1]
        multigraph = get_possible_dependencies(multipleDependency)
        for r in multigraph:
            dependency_graph.append(singledependencies+r)

    else:
        dependency_graph = [depends]
    return dependency_graph


def get_possible_dependencies(multipleDependency):
    multi = multipleDependency.copy()
    res = []
    while len(multi) > 0:
        dep = []
        to_remove = []
        for m in multi:
            if len(multi[m]) == 0:
                to_remove.append(m)
                continue

            dep.append(multi[m].pop())

        for r in to_remove:
            multi.remove(r)
        if len(dep) > 0:
            res.append(dep)

    return res


def get_label(s, m, policy, queryConn, stars, query):
    """
    Get the type of dependency 0 = Independent, -1 = Dependent on Join, -2 = Dependent on Non Join, and
        1 = dependent on both Join and Non-Join varibales
    :param s: subject var of star
    :param m:  molecule template name
    :param policy: access policy for this (star, molecule, dataset)
    :param queryConn: O-S connection of query
    :param stars: star-shaped subqueries
    :param query: complete query with projection and prefixes
    :return:
    """
    starTPs = stars[s]
    sVars = getPredicatesAndVars(starTPs, query.prefs)
    denied = list(set(sVars.values()).intersection(set(policy.properties_denied)))
    projections = [p.name for p in query.args]
    if len(denied) > 0:
        denied_vars = [k for k in sVars.keys() if sVars[k] in denied]
        # check if this star contains projection vars that have no access grant
        for p in sVars:
            if p in projections and p in denied_vars:
                # No Access granted for this star
                return 2, {p: [sVars[p]]}

        if len(queryConn[s]) > 0:
            isOnJoin = False
            isOnNJoin = False
            joinVars = dict()
            nonjoinVars = dict()
            for j in denied_vars:
                if j in queryConn[s]:
                    isOnJoin = True
                    if j in joinVars:
                        joinVars[j].append(sVars[j])
                    else:
                        joinVars[j] = [sVars[j]]
                else:
                    isOnNJoin = True
                    if j in nonjoinVars:
                        nonjoinVars[j].append(sVars[j])
                    else:
                        nonjoinVars[j] = [sVars[j]]

            if isOnJoin and isOnNJoin:
                return 1, (joinVars, nonjoinVars)
            if isOnJoin:
                return -1, joinVars
            else:
                return -2, nonjoinVars

        else:
            njvars = {}
            for j in denied_vars:
                if j in njvars:
                    njvars[j].append(sVars[j])
                else:
                    njvars[j] = [sVars[j]]
            return -2, {k: [sVars[k]] for k in sVars.keys() if sVars[k] in denied}

    return 0, {k: [sVars[k]] for k in sVars}


def getStarsConnectionsOS(stars):
    """
    extracts links between star-shaped sub-queries
    :param stars: map of star-shaped sub-queries with its root (subject) {subject: [triples in BGP]}
    :return: map of star-shaped sub-query root name (subject) with its connected sub-queries via its object node.
     {subj1: [subjn]} where one of subj1's triple pattern's object node is connected to subject node of subjn
    """
    conn = dict()
    for s in stars.copy():
        ltr = stars[s]
        conn[s] = []
        for c in stars:
            if c == s:
                continue
            for t in ltr:
                if t.theobject.name == c:
                    if c not in conn[s]:
                        conn[s].append(c)
                    break

    return conn


def getStarsConnectionsOO(stars, prefixes):
    """
    extracts links between star-shaped sub-queries
    :param stars: map of star-shaped sub-queries with its root (subject) {subject: [triples in BGP]}
    :return: map of star-shaped sub-query root name (subject) with its connected sub-queries via its object node.
     {subj1: [subjn]} where one of subj1's triple pattern's object node is connected to subject node of subjn
    """
    conn = dict()
    for s in stars.copy():
        ltr = stars[s]
        conn[s] = []
        predvars = getPredicatesAndVars(ltr, prefixes)
        for c in stars:
            if c == s:
                continue
            cltr = stars[c]
            cpredvars = getPredicatesAndVars(cltr, prefixes)
            shared = set(predvars.keys()).intersection(cpredvars.keys())
            if len(shared) > 0:
                conn[s].append(c)

    return conn


def getPredicatesAndVars(ltr, prefixes):

    # NOTE: this method works only if triple patterns contain only distinct object variable
    # If tp1 and tp2 uses same obj name, then only one will survive
    res = {tr.theobject.name: utils.getUri(tr.predicate, utils.getPrefs(prefixes))[1:-1]
           for tr in ltr if tr.predicate.constant and not tr.theobject.constant}

    return res


def getPredicates(ltr, prefixes):

    preds = [utils.getUri(tr.predicate, utils.getPrefs(prefixes))[1:-1] for tr in ltr if tr.predicate.constant]

    return preds


def is_cyclic(G):
    """
    Check if a Directed graph contains cycle or not
    :param G: a directed graph nx.DiGraph()
    :return: True if G is strongly connected or contains strongly connected components with more than one node;
            False otherwise
    """
    if len(list(G.edges())) > 0 and nx.is_strongly_connected(G):
        return True
    conComp = sorted(nx.strongly_connected_components(G))
    cycle = [True for c in conComp if len(c) > 1]
    if len(cycle) > 0:
        return True

    return False

def draw_graph(G):
    nx.draw(G, with_labels=True, node_size=2900, width=3, node_color="blue")
    plt.show()


def make_di_graph(g):
    G = nx.DiGraph()
    for s in g:
        if 'DJ' in g[s]:
            G = add_component(G, s, 'DJ', g[s]['DJ'])

        if 'DNJ' in g[s]:
            G = add_component(G, s, 'DNJ', g[s]['DNJ'])

        if 'I' in g[s]:
            G = add_component(G, s, 'I', g[s]['I'], edge=False)

    return G


def add_component(G, s, label, values, edge=True):
    for var in values:
        datasets = [d['dataset'] for d in values[var]]
        molecules = [d['molecule'] for d in values[var]]
        predicates = [p for pred in values[var] for p in pred['predicates']]
        if edge:
            G.add_edge(s, var, relation=label, dataset=datasets, molecule=molecules, predicate=predicates)
        else:
            G.add_node(s, relation=label, dataset=datasets, molecule=molecules, predicate=predicates)
    return G


def get_outdegrees(G):
    """
    Return out degree of nodes in G - {node: outdegree, ..}
    :param G: a directed graph - nx.DiGraph or nx.MultiDiGraph
    :return:
    """
    if not (isinstance(G, nx.DiGraph) or isinstance(G, nx.MultiDiGraph)):
        return {}

    outdegree = {n[0]: n[1] for n in sorted(G.out_degree())}

    return outdegree


def get_di_neighbors(G):
    """
    Return a direct neighbors of nodes in G (i.e., B-> [A, ..], ...) - {B: [A ..], ..}
    :param G: a directed graph - nx.DiGraph or nx.MultiDiGraph
    :return:
    """
    if not (isinstance(G, nx.DiGraph) or isinstance(G, nx.MultiDiGraph)):
        return {}

    nodes = sorted(G.nodes())
    neighbors = {n: sorted(G.neighbors(n)) for n in nodes}

    return neighbors


def get_incoming_neighbors(G):
    """
    Return a list of nodes that have a direct edge to a node A (i.e., B -> A, ..) - {A:[B, ..], ..}
    :param G: a directed graph - nx.DiGraph or nx.MultiDiGraph
    :return:
    """
    if not (isinstance(G, nx.DiGraph) or isinstance(G, nx.MultiDiGraph)):
        return {}

    nodes = sorted(G.nodes())
    neighbors = get_di_neighbors(G)

    inneighbors = {n: [] for n in nodes}
    for n in neighbors:
        for m in neighbors[n]:
            if m in inneighbors:
                inneighbors[m].append(n)
            else:
                inneighbors[m] = [n]

    return inneighbors


def contains_independent_node(G):
    """
    Check if a Directed graph
    :param G:
    :return:
    """
    if not (isinstance(G, nx.DiGraph) or isinstance(G, nx.MultiDiGraph)):
        print("PolicyUtils.contains_independent_node(): G is not a directed Graph")
        return False

    outdegree = get_outdegrees(G)
    S = [s for s in outdegree if outdegree[s] == 0]
    if len(S) > 0:
        return True

    return False
