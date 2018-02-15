import pprint
import os
import urllib
import httplib
import json
import random


def get_links(endpoint1, rdfmt1, endpoint2, rdfmt2):
    print '============================================================'
    print 'between endpoints:', endpoint1, ' --> ', endpoint2
    for c in rdfmt1:
        for p in c['predicates']:
            reslist = get_external_links(endpoint1, c['rootType'], p['predicate'], endpoint2, rdfmt2)
            if len(reslist) > 0:

                c['linkedTo'].extend(reslist)
                c['linkedTo'] = list(set(c['linkedTo']))
                p['range'].extend(reslist)
                p['range'] = list(set(p['range']))
                print 'external links found for ', c['rootType'], '->', p['predicate'], reslist


def contactSource(query, referer, server, path):
    json = "application/sparql-results+json"
    params = urllib.urlencode({'query': query, 'format': json})
    headers = {"User-Agent": "mulder", "Accept": "*/*", "Referer": referer, "Host": server}
    try:
        conn = httplib.HTTPConnection(server)
        conn.request("GET", "/" + path + "?" + params, None, headers=headers)
        response = conn.getresponse()
        reslist = []
        if response.status == httplib.OK:
            res = response.read()
            res = res.replace("false", "False")
            res = res.replace("true", "True")
            res = eval(res)

            if type(res) is dict:
                if "results" in res:
                    for x in res['results']['bindings']:
                        for key, props in x.iteritems():
                            '''suffix =''
                            if props['type'] == 'typed-literal':
                                suffix = "^^<" + props['datatype'].encode("utf-8") + ">"
                            elif "xml:lang" in props:
                                suffix = '@' + props['xml:lang']
                            '''
                            x[key] = props['value'].encode('utf-8')
                    reslist = res['results']['bindings']
                else:
                    reslist.append(res['boolean'])
            return reslist, len(reslist)
        else:
            print response.reason, response.status, query

    except Exception as e:
        print "Exception during query execution to", referer, ': ', e.message, query
    return None, -2


def get_external_links(endpoint1, rootType, pred, endpoint2, rdfmt2):
    query = 'SELECT DISTINCT ?o  WHERE {?s a <' + rootType + '> ; <' + pred + '> ?o . FILTER (isIRI(?o))}'
    referer = endpoint1
    server = endpoint1.split("http://")[1]
    (server, path) = server.split("/", 1)
    reslist = []
    limit = 10
    offset = 0
    numrequ = 0
    checked_inst = []
    while True:
        query_copy = query + " LIMIT " + str(limit) + " OFFSET " + str(offset)
        res, card = contactSource(query_copy, referer, server, path)
        numrequ += 1
        if card == -2:
            limit = limit / 2
            if limit == 0:
                break

            continue
        if numrequ == 100:
            break
        if card > 0:
            rand = random.randint(0, card - 1)
            inst = res[rand]
            if inst['o'] in checked_inst:
                offset += limit
                continue
            for c in rdfmt2:

                exists = link_exist(inst['o'], c['rootType'], endpoint2)
                if exists:
                    reslist.append(c['rootType'])
                    print inst['o'], ',', c['rootType']
            reslist = list(set(reslist))
        if card < limit:
            break

        offset += limit

    return reslist


def link_exist(s, c, endpoint):

    query = "ASK {<" + s + '>  a  <' + c + '> } '
    referer = endpoint
    server = endpoint.split("http://")[1]
    (server, path) = server.split("/", 1)
    res, card = contactSource(query, referer, server, path)
    if card > 0:
        if res[0]:
            print "ASK result", res, endpoint
        return res[0]
    if res is None:
        print 'bad request on, ', s, c
    return False


def read_rdfmts(folder):
    files = os.listdir(folder)
    print 'The following files are being combined:'
    pprint.pprint(files)

    molecules = {}
    print 'Number of molecules in:'
    for m in files:
        with open(folder + '/' + m) as f:
            rdfmt = json.load(f)
            key = rdfmt[0]['wrappers'][0]['url']
            molecules[key] = rdfmt
            print '-->', m, '=', len(rdfmt)
    print 'Total number of endpoints: ', len(molecules)

    return molecules


def combine_single_source_descriptions(rdfmts):

    print 'The following RDF-MTs are being combined:'
    pprint.pprint(rdfmts.keys())
    molecule_dict = {}
    molecules_tomerge = {}
    molecules = []
    print 'Number of molecules in:'
    for rdfmt in rdfmts:
        for m in rdfmts[rdfmt]:
            if m['rootType'] in molecule_dict:
                molecules_tomerge[m['rootType']] = [molecule_dict[m['rootType']]]
                molecules_tomerge[m['rootType']].append(m)
                del molecule_dict[m['rootType']]

                continue

            molecule_dict[m['rootType']] = m

        #molecules.extend(rdfmts[rdfmt])
        print '-->', rdfmt, '=', len(rdfmts[rdfmt])
    for m in molecule_dict:
        molecules.append(molecule_dict[m])

    for root in molecules_tomerge:
        mols = molecules_tomerge[root]
        res = {'rootType': root,
               'linkedTo': [],
               'wrappers': [],
               'predicates': []}
        for m in mols:
            res['wrappers'].append(m['wrappers'][0])
            res['linkedTo'].extend(m['linkedTo'])
            res['linkedTo'] = list(set(res['linkedTo']))
            predicates = {}
            for p in m['predicates']:
                if p['predicate'] in predicates:
                    predicates[p['predicate']]['range'].extend(p['range'])
                    predicates[p['predicate']]['range'] = list(set(predicates[p['predicate']]['range']))
                else:
                    predicates[p['predicate']] = p

            for p in predicates:
                res['predicates'].append(predicates[p])

        molecules.append(res)

    print 'Total number of molecules: ', len(molecules)

    return molecules


if __name__ == "__main__":
    enpointmaps = {"http://0.0.0.0:7100/sparql": '../templates/iasis/goa-rdfmts.json',
                   "http://0.0.0.0:7102/sparql": '../templates/iasis/reactome-rdfmts.json',
                   "http://0.0.0.0:7101/sparql": '../templates/iasis/kegg-rdfmts.json'}

    pp = pprint.PrettyPrinter(indent=2)
    rdfmts = read_rdfmts('../templates/iasis')

    for endpoint1 in rdfmts:
        print endpoint1
        if '18890' in endpoint1 or '18894' in endpoint1:
            continue
        for endpoint2 in rdfmts:
            if '18890' in endpoint2 or '18894' in endpoint2:
                continue
            if endpoint1 == endpoint2:
                continue
            get_links(endpoint1, rdfmts[endpoint1], endpoint2, rdfmts[endpoint2])

    molecules = combine_single_source_descriptions(rdfmts)
    with open('../templates/iasis/all-rdfmts-tcgaluad-goa-reactome-kegg-cosmic.json', 'w+') as f:
        json.dump(molecules, f)
