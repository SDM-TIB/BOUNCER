
import requests
import json
from http import HTTPStatus

from mulder.access_control import AccessPolicy, User, Operation
from mulder.access_control import PolicyUtility


class AccessControl(object):

    def __init__(self, server='http://localhost:9999/validate/retrieve'):
        self.server = server
        self.accesspolicy = {}

    def get_policy(self, user, operation, molecule, properties, dataset="*"):
        req = dict()
        req['authorizedTo'] = user.url
        req['authenticationToken'] = ""
        req['operation'] = {"type": operation.opr,
                            "resource": {"subject": molecule,
                                         "properties": properties}}

        response = request_server(self.server, req)
        print(response)
        if not response or 'authorizations' not in response:
            return [AccessPolicy("", user=user, dataset=dataset, molecule=molecule, operation=operation, properties_granted=[], properties_denied=properties)]

        auth = response["authorizations"]
        props = auth['properties']

        accesspolicies = []

        for ap in props:
            # dataset = ap
            dataset = getmappedds(ap)
            properties_granted = props[ap]
            denied = []
            for p in properties:
                if p not in properties_granted:
                    denied.append(p)
            apolicy = AccessPolicy("", user, dataset, molecule, operation, properties_granted, denied)
            accesspolicies.append(apolicy)

        return accesspolicies

    def get_access_policies(self, res, stars, query, user):
        """
        Return access policies associated with each (star,moleculetemplate) pairs for a user
        :param res: matching molecule templates per star {s:[M1, M2, ..], ..}
        :param stars: set of star shaped subqueries {s:[tp1, tp2, ..], ..}
        :param query: full query that contains all stars
        :param user: user for which the policy is being retrieved for
        :return: set of access policies per (star, moleculeTemplate) pair
                {
                    s1: {M1: [AccessPolicy1, AccessPolicy2, ..], M2:[..], ..},
                    s2: {M3: [.. ], M4:[.. ], ..}, ..
                }
        """
        accessPolicies = dict()
        for r in res:
            mols = res[r]
            ltr = stars[r]
            apolicies = dict()
            for m in mols:
                preds = PolicyUtility.getPredicates(ltr, query.prefs)
                aps = self.get_policy(user=user,
                                      molecule=m,
                                      properties=preds,
                                      operation=Operation())
                apolicies[m] = aps

            accessPolicies[r] = apolicies

        self.accesspolicy = accessPolicies

        return accessPolicies

    def get_runnable_sequences(self, res, stars, query, policies, queryConnections):
        """
         Return list of executable query plans for a given query and access policy
        :param res:
        :param stars:
        :param query:
        :param policies:
        :param queryConnections:
        :return:
        """
        # Sanity check: if projected variables have access grant
        if not self.is_projection_granted(query, stars, policies):
            print("Projection is not granted")
            return []
        depGraphs = PolicyUtility.create_dependency_graph(res, stars, query, policies, queryConnections)
        execGraphs = []

        print("Dependency graph:", depGraphs)
        for g in depGraphs:
            G = PolicyUtility.make_di_graph(g)
            # PolicyUtility.draw_graph(G)
            # check if a graph is cyclic or it contains a node with no outgoing edge
            if PolicyUtility.is_cyclic(G) or not PolicyUtility.contains_independent_node(G):
                continue

            # get run sequences of G: if len > 0 then it can be executed
            sequences = self.get_run_sequences(G)
            if len(sequences) > 0:
                execGraphs.append(sequences)

        return execGraphs

    def is_runnable(self, res, stars, query, policies, queryConnections):
        """
        Check if the BGP is executable or not
        :param res:
        :param stars:
        :param policies:
        :return: True if the dependency graph(s) contains at least one execution sequence;
                 False otherwise
        """

        depGraphs = PolicyUtility.create_dependency_graph(res, stars, query, policies, queryConnections)
        execGraphs = []
        print("Dependency graph:", depGraphs)
        for g in depGraphs:
            print("g", g)
            G = PolicyUtility.make_di_graph(g)
            PolicyUtility.draw_graph(G)
            # check if a graph is cyclic or it contains a node with no outgoing edge
            if PolicyUtility.is_cyclic(G) or not PolicyUtility.contains_independent_node(G):
                continue

            # get run sequences of G: if len > 0 then it can be executed
            sequences = self.get_run_sequences(G)
            if len(sequences) > 0:
                print("Sequences:", sequences)
                execGraphs.append(G)

        print("Executable Graphs:", execGraphs)
        if len(execGraphs) > 0:
            return True

        return False

    def get_run_sequences(self, G):
        """

        :param G:
        :return:
        """
        outdegree = PolicyUtility.get_outdegrees(G)
        S = [s for s in outdegree if outdegree[s] == 0]

        if len(S) == 0:
            print("AccessControl.get_run_sequences(): all stars are dependent on each other. Cannot be executed")
            return {}

        inneighbors = PolicyUtility.get_incoming_neighbors(G)

        nodes = sorted(G.nodes())
        disconnectedNodes = [n for n in nodes if n in S and len(inneighbors[n]) == 0]
        for d in disconnectedNodes:
            nodes.remove(d)

        if len(nodes) == 0:
            return self.prepare_exec_plan( {n:n for n in list(G.nodes())}, G)

        independent = self.get_independents(G, S)

        if len(independent) == 0:
            print("AccessControl.get_run_sequences(): No independent Joins between (independent, dependent) stars")
            return {}

        executeable = set()
        while len(independent) > 0:
            bucket = {}
            solvable = False
            executed = set()
            for i in independent:

                # Get incoming links to i
                Ns = inneighbors[i]

                # If there is no incoming link to i, then this sub-graph is solvable
                if len(Ns) == 0:
                    # Ns == 0 - might mean we have reached the end of the (reverse) graph traversal of this sub graph
                    solvable = True
                    if not isinstance(independent[i], list) and independent[i] in executed:
                        bucket = {i: [bucket]}
                    elif i in bucket:
                        bucket[i].append(independent[i])
                    else:
                        bucket[i] = independent[i]

                # For each incoming link n to i
                for n in Ns:
                    # If n has outgoing link only to i, then (n and i) are joinable (solvable)
                    if outdegree[n] == 1:
                        solvable = True
                        if not isinstance(independent[i], list) and independent[i] in executed:
                            val = [bucket]
                            if n in bucket:
                                bucket = {}
                                bucket[n].append({i: val})
                            else:
                                bucket = {}
                                bucket[n] = [{i: val}]
                        else:
                            if n in bucket:
                                bucket[n].append({i: independent[i]})
                            else:
                                bucket[n] = [{i: independent[i]}]

                        # add n as executed (solved) node
                        executed.add(n)

                    else:
                        # flag if (n,i) can be solved
                        solved = True
                        # all nodes connected to n, via out going links of n, except i,
                        # should be either executable (solved in previous steps) or independent nodes.
                        # if not, then this graph has no solution. (solved =False)
                        for m in G.out_edges(n):
                            if m[1] != i and m[1] != independent[i] and m[1] not in executeable:
                                solved = False
                                break

                        # If all m's connected to n are already solved, then this link (i,n) is also solvable
                        if solved:
                            solvable = True
                            if not isinstance(independent[i], list) and independent[i] in executed:
                                val = [bucket]
                                if n in bucket:
                                    bucket = {}
                                    bucket[n].append({i: val})
                                else:
                                    bucket = {}
                                    bucket[n] = [{i: val}]
                            else:
                                if n in bucket:
                                    bucket[n].append({i: independent[i]})
                                else:
                                    bucket[n] = [{i: independent[i]}]

                            # add n as executed (solved) node
                            executed.add(n)

                # add i as executed (solved) node
                executed.add(i)

                # add independent[i] as executed (solved) node, if it is a single node ( initial connection).
                # initial independents are found from the first step of this algorithm
                if not (isinstance(independent[i], list)):
                    executed.add(independent[i])

            if not solvable:
                print("AccessControl.get_run_sequences(): Found unexecutable link. Not permited!")
                return {}
            # make union between executed (solved) nodes in this iteration to global executable (solved) nodes
            executeable = executeable.union(executed)

            # if all nodes are in executables, then this graph can be solved, Algorithm exits
            # return the plan
            if len(executeable) == len(nodes):
                if len(disconnectedNodes) > 0:
                    for d in disconnectedNodes:
                        bucket[d] = d

                results = self.prepare_exec_plan(bucket, G)

                return results

            if independent == bucket:
                print("AccessControl.get_run_sequences(): It is not solvable")
                return {}

            # reset independent joins to the new joins found in this iteration
            independent = bucket

        return {}

    def prepare_exec_plan(self, bucket, G):
        nodes_data = list(G.nodes(data=True))
        edges_data = list(G.edges(data=True))
        stars_data = {}
        self.get_graph_data(nodes_data, stars_data, True)
        self.get_graph_data(edges_data, stars_data, False)
        results = dict()
        results = self.attach_data(bucket, stars_data, results)

        return results

    def attach_data(self, bucket, stars_data, results):
        for s in bucket:
            if isinstance(bucket[s], list):
                results[s] = stars_data[s]
                results[s]['depends'] = []
                for r in bucket[s]:
                    iresult = dict()
                    iresult = self.attach_data(r, stars_data, iresult)
                    results[s]['depends'].append(iresult)
            else:

                leaf = {bucket[s]: stars_data[bucket[s]]}
                results[s] = stars_data[s]
                if s == bucket[s]:
                    results[s]['depends'] = {}
                else:
                    results[s]['depends'] = leaf

        return results

    def get_graph_data(self, data, output, isNode = True):
        if isNode:
            i = 1
        else:
            i = 2

        for n in data:
            if len(n[i]) > 0:
                data = {"molecules": n[i]['molecule'], 'dataset': n[i]['dataset'], 'depends': {}, 'relation': n[i]['relation'], 'predicate': n[i]['predicate']}
                output[n[0]] = data

    def get_independents(self, G, S):
        """

        :param G:
        :param S:
        :return:
        """
        soln = []
        bucket = []
        independents = dict()
        solvable = True
        inneighbors = PolicyUtility.get_incoming_neighbors(G)
        outdegree = PolicyUtility.get_outdegrees(G)
        while len(S) > 0:
            s = S.pop()
            Ns = inneighbors[s]

            if len(Ns) == 0:
                continue
            for n in Ns:
                if n in outdegree and outdegree[n] == 1:
                    bucket.append((s, n))
                    independents[n] = s
                    soln.append(s)
                    soln.append(n)
                else:
                    solved = True
                    for m in inneighbors[n]:
                        if m not in soln:
                            solved = False
                            break
                    if solved:
                        bucket.append((s, n))
                        soln.append(s)
                        soln.append(n)
                    else:
                        solvable = False
                        break
                if not solvable:
                    break
        if not solvable:
            print("cannot be executed! No independent Star (Node)")
            return {}

        return independents

    def is_projection_granted(self, query, stars, policies):
        """
         Check if all projection variables have at least one star for which Access is Granted

        :param query:
        :param stars:
        :param policies:
        :return:
        """
        projGrants = {p.name: [] for p in query.args}
        starsVars = []
        for s in policies:
            for m in policies[s]:
                for policy in policies[s][m]:
                    starTPs = stars[s]
                    sVars = PolicyUtility.getPredicatesAndVars(starTPs, query.prefs)
                    predicates = list(set(sVars.values()))
                    starsVars.extend(list(set(sVars.keys())))
                    denied = list(set(sVars.values()).intersection(set(policy.properties_denied)))
                    if len(denied) > 0:
                        denied_vars = [k for k in sVars.keys() if sVars[k] in denied]
                        for p in projGrants:
                            if p in sVars.keys() and p not in denied_vars:
                                projGrants[p].append(s)
                    else:
                        for p in sVars:
                            if p in projGrants:
                                projGrants[p].append(s)

        denied_projections = [p for p in projGrants if len(projGrants[p]) == 0 and p in starsVars]
        if len(denied_projections) > 0:
            return False
        return True


def request_server(server, request):
    r = requests.post(server, data=json.dumps(request))

    if r.status_code == HTTPStatus.OK:
        res = r.text
        res = eval(res)
        return res

    return None


def request_mock(server, request):
    statements = {
        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/Producer":{
        "authorizations": {
            "subject": "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/Producer",
            "properties": {
                "ds-producer":[
                    "http://purl.org/dc/elements/1.1/publisher",
                    "http://www.w3.org/2000/01/rdf-schema#label",
                    "http://www.w3.org/2000/01/rdf-schema#comment",
                    "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/country",
                    "http://purl.org/dc/elements/1.1/date",
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                    "http://xmlns.com/foaf/0.1/homepage"
                ]
                }
           }
        },
        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/Product": {
            "authorizations": {
                "subject": "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/Product",
                "properties": {
                    "ds-product": [
                        #"http://www.w3.org/2000/01/rdf-schema#comment",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/productPropertyNumeric6",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/productPropertyNumeric1",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/productPropertyNumeric2",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/productPropertyNumeric3",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/productPropertyNumeric5",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/productFeature",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/producer",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/productPropertyTextual1",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/productPropertyTextual2",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/productPropertyTextual4",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/productPropertyTextual5",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/productPropertyTextual6",
                        "http://purl.org/dc/elements/1.1/publisher",
                        "http://purl.org/dc/elements/1.1/date",
                        "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/productPropertyNumeric4",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/productPropertyTextual3",
                        "http://www.w3.org/2000/01/rdf-schema#label"
                    ]
                }
            }
        },
        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/ProductType": {
        "authorizations": {
            "subject": "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/ProductType",
            "properties": {
                "ds-productType":[
                    "http://purl.org/dc/elements/1.1/publisher",
                    "http://www.w3.org/2000/01/rdf-schema#subClassOf",
                    "http://purl.org/dc/elements/1.1/date",
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                    "http://www.w3.org/2000/01/rdf-schema#comment",
                    "http://www.w3.org/2000/01/rdf-schema#label"
                ]
                }
           }
        },
        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/Vendor": {
            "authorizations": {
                "subject": "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/Vendor",
                "properties": {
                    "ds-vendor": [
                        "http://xmlns.com/foaf/0.1/homepage",
                        "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                        "http://purl.org/dc/elements/1.1/publisher",
                        "http://www.w3.org/2000/01/rdf-schema#label",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/country",
                        "http://www.w3.org/2000/01/rdf-schema#comment",
                        "http://purl.org/dc/elements/1.1/date"
                    ]
                }
            }
        },
        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/Offer": {
            "authorizations": {
                "subject": "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/Offer",
                "properties": {
                    "ds-offer": [
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/deliveryDays",
                        "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/validTo",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/price",
                        "http://purl.org/dc/elements/1.1/date",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/vendor",
                        "http://purl.org/dc/elements/1.1/publisher",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/product",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/offerWebpage",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/validFrom"
                    ]
                }
            }
        },
        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/ProductFeature": {
            "authorizations": {
                "subject": "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/ProductFeature",
                "properties": {
                    "ds-productFeature": [
                        "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                        "http://purl.org/dc/elements/1.1/publisher",
                        "http://purl.org/dc/elements/1.1/date",
                        "http://www.w3.org/2000/01/rdf-schema#comment",
                        "http://www.w3.org/2000/01/rdf-schema#label"
                    ]
                }
            }
        },
        "http://xmlns.com/foaf/0.1/Person": {
        "authorizations": {
            "subject": "http://xmlns.com/foaf/0.1/Person",
            "properties": {
                "ds-person": [
                    "http://xmlns.com/foaf/0.1/mbox_sha1sum",
                    "http://purl.org/dc/elements/1.1/date",
                    "http://purl.org/dc/elements/1.1/publisher",
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                    "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/country",
                    "http://xmlns.com/foaf/0.1/name"
                              ]
                }
           }
        },
        "http://purl.org/stuff/rev#Review": {
            "authorizations": {
                "subject": "http://purl.org/stuff/rev#Review",
                "properties": {
                    "ds-review": [
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/reviewFor",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/rating3",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/rating1",
                        "http://purl.org/stuff/rev#reviewer",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/reviewDate",
                        "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                        "http://purl.org/stuff/rev#text",
                        "http://purl.org/dc/elements/1.1/date",
                        "http://purl.org/dc/elements/1.1/title",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/rating4",
                        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/rating2",
                        "http://purl.org/dc/elements/1.1/publisher"
                        ]
                }
            }
        }
    }

    mole = request['operation']['resource']['subject']

    return statements[mole]


def getmappedds(ap):
    if "11891" in ap:
        return "http://0.0.0.0:11892/sparql"
    elif "11892" in ap:
        return "http://0.0.0.0:11893/sparql"
    elif "11893" in ap:
        return "http://0.0.0.0:11899/sparql"
    elif "11894" in ap:
        return "http://0.0.0.0:11898/sparql"
    elif "11895" in ap:
        return "http://0.0.0.0:11894/sparql"
    elif "11896" in ap:
        return "http://0.0.0.0:11895/sparql"
    elif "11897" in ap:
        return "http://0.0.0.0:11897/sparql"
    elif "11898" in ap:
        return "http://0.0.0.0:11896/sparql"

    return ap


if __name__=='__main__':

    server = 'http://localhost:9999/validate/retrieve'
    ac = AccessControl(server)
    aps = ac.get_policy(User("P5", url='http://www.example.org/access-control-ontology#auth_partner_1961b5'),
                        Operation('RETRIEVE_OPERATION'),
                        'http://purl.org/stuff/rev#Review',
                        ["http://purl.org/dc/elements/1.1/date"])

    from pprint import pprint
    pprint(aps)

