
import requests
import json
from http import HTTPStatus

class AccessPolicy(object):
    """
    Defines an access policy for a single operation
    """
    def __init__(self, server, user="MULDER", dataset=None, molecule=None, operation=None, properties_granted=None, properties_denied=None, properties_join_on_fed=None):
        self.server = server
        self.user = user
        self.dataset = dataset
        self.molecule = molecule
        self.operation = operation
        self.properties_granted = properties_granted
        self.properties_denied = properties_denied
        self.properties_join_on_fed = properties_join_on_fed

    def get_policy(self, user, operation, molecule, properties, dataset="*"):
        req = dict()
        req['authorizedTo'] = user.url
        req['authenticationToken'] = ""
        req['operation'] = {"type": operation.opr,
                            "resource": {"subject": molecule,
                                         "properties": properties}}

        response = request_mock(self.server, req)
        if not response:
            return [AccessPolicy(user, dataset, molecule, operation, properties_granted=[], properties_denied=properties)]

        auth = response["authorizations"]
        props = auth['properties']

        accesspolicies = []

        for ap in props:
            dataset = ap
            properties_granted = props[ap]
            denied = []
            for p in properties:
                if p not in properties_granted:
                    denied.append(p)
            apolicy = AccessPolicy(user, dataset, molecule, operation, properties_granted, denied)
            accesspolicies.append(apolicy)

        return accesspolicies

    def __repr__(self):
        if self.properties_denied is None:
            denied = []
        else:
            denied = str(self.properties_denied)

        if self.properties_granted is None:
            granted = []
        else:
            granted = str(self.properties_granted)

        if self.properties_join_on_fed is None:
            join_on_fed = []
        else:
            join_on_fed = str(self.properties_join_on_fed)
        output = "{\n" \
                 "\tUser/Mediator: " + str(self.user) + "\n" \
                 "\tDataset: " + self.dataset + "\n" \
                 "\tMolecule: " + self.molecule + "\n" \
                 "\tOperation: " + str(self.operation) + "\n" \
                 "\tPublic properties: " + str(granted) + "\n" \
                 "\tLocally Joinable properties:  " + str(denied) + "\n" \
                 "\tProperties Joinable on Mediator:  " + str(join_on_fed) + "\n" \
                                                                                                            "}"
        return output


class User(object):

    def __init__(self, name, url, role="Partner"):
        self.name = name
        self.url = url
        self.role = role

    def __repr__(self):
        return self.name + " (" + self.url + ")[" + self.role + "]"


class Operation(object):
    def __init__(self, opr='RETRIEVE_OPERATION'):
        self.opr = opr

    def __repr__(self):
        return self.opr

    def __str__(self):
        return self.__repr__()


class OldDecomposerMethods_backup():
    def getAccessPolicies(self, res, stars):
        accessPolicies = dict()
        for r in res:
            mols = res[r]
            ltr = stars[r]
            apolicies = dict()
            for m in mols:
                preds = self.getPredicates(ltr)
                aps = self.accessControl.get_policy(user=self.user,
                                                    molecule=m,
                                                    properties=preds,
                                                    operation=Operation())
                apolicies[m] = aps

            accessPolicies[r] = apolicies

        self.accesspolicy = accessPolicies

        return accessPolicies

    def isRunnable(self, res, stars):
        if not self.projectionGranted(res, stars):
            return False

        dependency = self.createDependencyGraph(res, stars)
        print("dependency:")
        print(dependency)
        #TODO: make sure the dependency graph is weakly connected
        #TODO: this means there is star that is not dependent on other stars
        # for each s in stars: if s not in dependency, then start from this star
        # if there is any other star depend on non-dependent star, then combine them (as node in tree)
        for d in dependency:
            if len(dependency[d]) > 1:
                rev = dict()
                for v in dependency[d]:
                    for x in dependency[d][v]:
                        if x in rev:
                            rev[x].append(v)
                        else:
                            rev[x] = [v]
                for x in rev:
                    if len(rev[x]) > 1:
                        for v in rev[x]:
                            if v not in dependency:
                                dependency[d] = {v: [x]}

        print(dependency)
        # if a star is dependent on more than one star with same predicates
        #       and one of them are non-dependent star, then remove the other stars
        return True

    def createDependencyGraph(self, res, stars):
        so_conn = self.getStarsConnections(stars)
        oo_conn = self.getStarsConnectionsOO(stars)
        dependency = dict()

        # S-O connections (object part of star s is connected to subject part of star o)
        for s in so_conn:
            if len(so_conn[s]) > 0:
                sltr = stars[s]
                svars = self.getPredicatesAndVars(sltr)

                for o in so_conn[s]:

                    for m in res[s]:
                        policy = self.accesspolicy[s][m]
                        for p in policy:
                            shared = set(svars.values()).intersection(set(p.properties_denied))
                            if len(shared) > 0:
                                shared = list(shared)
                                if s in dependency:
                                    if o in dependency[s]:
                                        dependency[s][o].extend(list(shared))
                                    else:
                                        dependency[s][o] = shared
                                else:
                                    dependency[s] = {o: shared}

                    for m in res[o]:
                        oltr = stars[o]
                        ovars = self.getPredicatesAndVars(oltr)
                        policy = self.accesspolicy[o][m]
                        for p in policy:
                            shared = set(ovars.values()).intersection(set(p.properties_denied))
                            if len(shared) > 0:
                                shared = list(shared)
                                if o in dependency:
                                    if s in dependency:
                                        dependency[o][s].extend(shared)
                                    else:
                                        dependency[o][s] = shared
                                else:
                                    dependency[o] = {s: shared}

        # O-O connections (stars that share object part of triple patterns)
        for s in oo_conn:
            if len(oo_conn[s]) > 0:
                sltr = stars[s]
                spredvars = self.getPredicatesAndVars(sltr)

                for o in oo_conn[s]:
                    for m in res[s]:
                        policy = self.accesspolicy[s][m]
                        for p in policy:
                            shared = set(spredvars.values()).intersection(set(p.properties_denied))
                            if len(shared) > 0:
                                shared = list(shared)
                                if s in dependency:
                                    if o in dependency[s]:
                                        dependency[s][o].extend(list(shared))
                                    else:
                                        dependency[s][o] = shared
                                else:
                                    dependency[s] = {o: shared}
                    for m in res[o]:
                        oltr = stars[o]
                        ovars = self.getPredicatesAndVars(oltr)
                        policy = self.accesspolicy[o][m]
                        for p in policy:
                            shared = set(ovars.values()).intersection(set(p.properties_denied))
                            if len(shared) > 0:
                                shared = list(shared)
                                if o in dependency:
                                    if s in dependency:
                                        dependency[o][s].extend(shared)
                                    else:
                                        dependency[o][s] = shared
                                else:
                                    dependency[o] = {s: shared}

        return dependency

    def projectionGranted(self, res, stars):

        projvars = [a.name for a in self.query.args]
        granted = True
        for r in res:
            mols = res[r]
            ltr = stars[r]
            predvars = self.getPredicatesAndVars(ltr)
            pvars = set(projvars).intersection(set(predvars.keys()))
            if len(pvars) > 0:
                for v in pvars:
                    g = False
                    for m in mols:
                        policy = self.accesspolicy[r][m]
                        for p in policy:
                            if predvars[v] in p.properties_granted:
                                g = True
                                break
                        if g:
                            break
                    if not g:
                        granted = False
                        break

            if r in projvars:
                g = False
                for m in mols:
                    policy = self.accesspolicy[r][m]
                    for p in policy:
                        if len(p.properties_granted) > 0:
                            g = True
                            break

                    if g:
                        break

                if not g:
                    granted = False
                    break

        return granted


def request_server(server, request):
    r = requests.post(server, data=json.dumps(request))

    if r.status_code == HTTPStatus.OK:
        res = r.text
        res = eval(res)
        return res

    return None


def request_mock(server, request):
    statements = {
        "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/Product": {
        "authorizations": {
            "subject": "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/Product",
            "properties": {
                "ds-product":["http://www.w3.org/2000/01/rdf-schema#label"]
                }
           }
        },
        "http://xmlns.com/foaf/0.1/Person": {
        "authorizations": {
            "subject": "http://xmlns.com/foaf/0.1/Person",
            "properties": {
                "ds-person": ["http://xmlns.com/foaf/0.1/name"] #"http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/country"
                }
           }
        },
        "http://purl.org/stuff/rev#Review": {
            "authorizations": {
                "subject": "http://purl.org/stuff/rev#Review",
                "properties": {
                    "ds-review": ["http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/reviewFor",
                    "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/rating3",
                    "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/rating1",
                    "http://purl.org/stuff/rev#reviewer",
                    "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/reviewDate",
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                    "http://purl.org/stuff/rev#text",
                    "http://purl.org/dc/elements/1.1/date",
                    #"http://purl.org/dc/elements/1.1/title",
                    "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/rating4",
                    "http://www4.wiwiss.fu-berlin.de/bizer/bsbm/v01/vocabulary/rating2",
                    "http://purl.org/dc/elements/1.1/publisher"]
                }
            }
        }
    }

    mole = request['operation']['resource']['subject']

    return statements[mole]
