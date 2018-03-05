#!/usr/bin/env python

__author__ = 'kemele'

import getopt
import string

import sys, os, signal

from multiprocessing import Process, Queue, active_children, Manager
from time import time
import logging


from mulder.molecule.MTManager import ConfigFile
from mulder.mediator.decomposition.MediatorDecomposer import MediatorDecomposer
from mulder.mediator.planner.MediatorPlanner import MediatorPlanner
from mulder.mediator.planner.MediatorPlanner import contactSource

from mulder.access_control import User, AccessPolicy, Operation
from mulder.access_control.AccessControl import AccessControl

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.FileHandler('.decompositions.log')
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def runQuery(queryfile, configfile, user, isEndpoint, res, qplan, adaptive, withoutCounts, printResults):

    '''if isEndpoint:
        contact = contactSource
    else:
        contact = contactWrapper
    '''
    query = open(queryfile).read()
    pos = queryfile.rfind("/")
    qu = queryfile[pos+1:]
    pos2 = qu.rfind(".")
    tempType  = 'MULDER'

    if pos2 > -1:
        qu = qu[:pos2]
    global qname
    global t1
    global tn
    global c1
    global cn
    global dt
    global pt
    c1 = 0
    cn = 0
    t1 = -1
    tn = -1
    dt = -1
    global time1
    qname = qu
    endpointType = 'V'
    logger.info("Query: " + qname)

    config = ConfigFile(configfile)

    if user is None:
        user = User("P5", url='http://www.example.org/access-control-ontology#auth_partner_094451')
    else:
        user = User("P5", url=user)

    server = 'http://localhost:9999/validate/retrieve'
    accesscontrol = AccessControl(server)
    time1 = time()
    joinstarslocally = False

    mdq = MediatorDecomposer(query, config, user, accesscontrol, tempType, joinstarslocally)
    new_query = mdq.decompose()

    dt = time() - time1

    if (new_query == None): # if the query could not be answered by the endpoints
        time2 = time() - time1
        t1 = time2
        tn = time2
        pt = time2
        printInfo()
        return

    planner = MediatorPlanner(new_query, True, contactSource, None, config)
    plan = planner.createPlan()
    logger.info("Plan:")
    logger.info(plan)
    pt = time() - time1
    #print 'creando procesos'
    p2 = Process(target=plan.execute, args=(res,))
    p2.start()
    p3 = Process(target=conclude, args=(res, p2, printResults))
    p3.start()
    signal.signal(12, onSignal1)

    while True:
        if p2.is_alive() and not p3.is_alive():
            try:
                os.kill(p2.pid, 9)
            except Exception as ex:
                continue
            break
        elif not p2.is_alive() and not p3.is_alive():
            break


def conclude(res, p2, printResults):

    signal.signal(12, onSignal2)
    global t1
    global tn
    global c1
    global cn
    ri = res.get()

    if (printResults):
        if (ri == "EOF"):
            time2 = time() - time1
            t1 = time2
            tn = time2
            print ("Empty set.")
            printInfo(p2)
            return

        while (ri != "EOF"):
            cn = cn + 1
            if cn == 1:
                time2=time() - time1
                t1 = time2
                c1 = 1
            print (ri)
            ri = res.get(True)
        printInfo(p2)

    else:
        if (ri == "EOF"):
            time2 = time() - time1
            t1 = time2
            tn = time2
            printInfo(p2)
            return

        while (ri != "EOF"):
            cn = cn + 1
            if cn == 1:
                time2 = time() - time1
                t1 = time2
                c1 = 1
            #print cn, ri
            ri = res.get(True)
        printInfo(p2)


def printInfo(p2=None):
    global tn
    if tn == -1:
       tn = time() - time1
    l = (qname + "\t" + str(dt) + "\t" + str(pt) + "\t" + str(t1) + "\t" + str(tn) + "\t" + str(c1) + "\t" + str(cn))

    print(l)
    logger.info(l)
    if p2 is not None:
        p2.terminate()


def onSignal1(s, stackframe):
    cs = active_children()
    for c in cs:
        try:
            os.kill(c.pid, 9)
        except OSError as ex:
            continue
    sys.exit(s)


def onSignal2(s, stackframe):
    printInfo()
    sys.exit(s)


def get_options(argv):
    try:
        opts, args = getopt.getopt(argv, "h:c:q:u:s:")
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    configfile = None
    queryfile = None
    #buffersize = 1638400
    tempType = "MULDER"
    user = None
    isEndpoint = True
    plan = "b"
    adaptive = True
    withoutCounts = False
    printResults = False

    for opt, arg in opts:
        if opt == "-h":
            usage()
            sys.exit()
        elif opt == "-c":
            configfile = arg
        elif opt == "-q":
            queryfile = arg
        elif opt == "-u":
            user = arg
        elif opt == "-s":
            isEndpoint = arg == "True"

    if not configfile or not queryfile:
        usage()
        sys.exit(1)
    return (configfile, queryfile, user, isEndpoint, plan, adaptive, withoutCounts, printResults)


def usage():
    usage_str = ("Usage: {program} -c <config.json_file>  -q <query_file> -u "
                 +"<user-url> " # -o <sparql1.1> -d " +"<decomposition>  -k <special>
                 +"\n where \n"
                  "<user-url> user url"
                 +"\n")
    print(usage_str.format(program = sys.argv[0]))


def main(argv):
    res = Queue()
    time1 = time()
    (configfile, queryfile, user, isEndpoint, plan, adaptive, withoutCounts, printResults) = get_options(argv[1:])
    try:
        runQuery(queryfile, configfile, user, isEndpoint, res, plan, adaptive, withoutCounts, printResults)
    except Exception as ex:
        print (ex)


if __name__ == '__main__':
    main(sys.argv)
