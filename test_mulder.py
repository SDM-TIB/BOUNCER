#!/usr/bin/env python3.5

from multiprocessing import Process, Queue, active_children
from multiprocessing.queues import Empty

from mulder.molecule.MTManager import ConfigFile
from mulder.mediator.decomposition.MediatorDecomposer import MediatorDecomposer
from mulder.mediator.planner.MediatorPlanner import MediatorPlanner
from mulder.mediator.planner.MediatorPlanner import contactSource as contactsparqlendpoint
import sys, os, signal, getopt
from time import time
from mulder.access_control import User, AccessPolicy, Operation
from mulder.access_control.AccessControl import AccessControl

__author__ = 'kemele'


def nexttime(time1):
    global t1
    global tn
    global c1
    global cn

    time2 = time() - time1
    t1 = time2
    tn = time2


def conclude(res, p2, printResults, traces=True):

    signal.signal(12, onSignal2)
    global t1
    global tn
    global c1
    global cn
    ri = res.get()

    if printResults:
        if (ri == "EOF"):
            nexttime(time1)
            print ("Empty set.")
            printInfo()
            return

        while ri != "EOF":
            cn = cn + 1
            if cn == 1:
                time2 = time() - time1
                t1 = time2
                c1 = 1

            print (ri)
            if traces:
                nexttime(time1)
                printtraces()
            ri = res.get(True)

        nexttime(time1)
        printInfo()

    else:
        if ri == "EOF":
            nexttime(time1)
            printInfo()
            return

        while (ri != "EOF"):
            cn = cn + 1
            if cn == 1:
                time2 = time() - time1
                t1 = time2
                c1 = 1

            if traces:
                nexttime(time1)
                printtraces()
            ri = res.get(True)

        nexttime(time1)
        printInfo()


def printInfo():
    global tn
    if tn == -1:
        tn = time() - time1
    l = (qname + "\t" + str(dt) + "\t" + str(pt) + "\t" + str(t1) + "\t" + str(tn) + "\t" + str(c1) + "\t" + str(cn))

    print(l)


def printtraces():
    global tn
    if tn == -1:
        tn = time() - time1
    l = (qname + "," + "MULDER," + str(cn) + "," + str(tn))

    print(l)


def onSignal1(s, stackframe):
    cs = active_children()
    for c in cs:
      try:
        os.kill(c.pid, s)
      except OSError as ex:
        continue
    sys.exit(s)


def onSignal2(s, stackframe):
    printInfo()
    sys.exit(s)

def get_options(argv):
    try:
        opts, args = getopt.getopt(argv, "h:c:q:u:s:r:")
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    configfile = None
    queryfile = None
    tempType = 'MULDER'
    user = None
    isEndpoint = True
    plan = "b"
    adaptive = True
    withoutCounts = False
    printResults = False
    result_folder = './'
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
        elif opt == '-r':
            result_folder = arg

    if not configfile or not queryfile:
        usage()
        sys.exit(1)

    return (configfile, queryfile, user, isEndpoint, plan, adaptive, withoutCounts, printResults, result_folder)


def usage():
    usage_str = ("Usage: {program} -c <config.json_file>  -q <query>\n")
    print (usage_str.format(program=sys.argv[0]),)


if __name__ == '__main__':
    user = None
    #(configfile, queryfile, user, isEndpoint, plan, adaptive, withoutCounts, printResults, result_folder) = get_options(sys.argv[1:])

    queryss = open('queries/AC-BSBM/B1').read()
    config = ConfigFile('config/config.json')
    tempType = "MULDER" #"SemEP" "METIS"
    joinstarslocally = False

    global time1
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
    qname = 'Q1'
    time1 = time()
    if user is None:
        user = User("P5", url='http://www.example.org/access-control-ontology#auth_partner_094451')
    else:
        user = User("P5", url=user)

    server = 'http://localhost:9999/validate/retrieve'
    accesscontrol = AccessControl(server)

    dc = MediatorDecomposer(queryss, config, user, accesscontrol, tempType, joinstarslocally)

    print(queryss)
    quers = dc.decompose()
    dt = time() - time1
    print("============ Decomposed query+++++++++++++++")
    print(quers)
    print("============ Planning ===========================")
    if quers is None:
        print("Query decomposer returns None")
        exit()

    planner = MediatorPlanner(quers, True, contactsparqlendpoint, None, config)
    plan = planner.createPlan()
    pt = time() - time1
    print(plan)
    #exit()
    output = Queue()
    processqueue = Queue()
    #plan.execute(output)
    print("*+*+*+*+*+*+*+*+*+*+*+*+*+++++")
    i = 0
    p2 = Process(target=plan.execute, args=(output, processqueue, ))
    p2.start()
    p3 = Process(target=conclude, args=(output, p2, False, False))
    p3.start()
    signal.signal(12, onSignal1)

    while True:
        if not p3.is_alive():
            if p2.is_alive():
                try:
                    os.kill(p2.pid, 9)
                except Exception as ex:
                    print("Exception while terminating execution process", ex)
                    continue
                print('Number of processes to terminate: ', processqueue.qsize())
                while True:
                    try:
                        p = processqueue.get(False)
                        try:
                            os.kill(p.pid, 9)
                        except Exception as e:
                            continue
                    except Empty:
                        break

            else:
                break