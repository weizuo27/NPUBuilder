import os
import sys
import networkx as nx
import matplotlib.pyplot as plt
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path + "/..");
from IP import IP

def assignOriginalNodeMapping(gs, hw_layers):
    mappingNodes = dict()
    mappingIPs = dict()
    for g in gs:
        for n in gs[g].nodes:
            if n.type is "combineNode":
                for m in n.node_list:
                    if m.type in hw_layers:
                        mappingIPs[m.mappedIP.name] = m.mappedIP
            if n.type in hw_layers:
                mappingIPs[n.mappedIP.name] = n.mappedIP

    for g in gs:
        for n in gs[g].nodes:
            if n.type is "combineNode":
                for m in n.node_list:
                    if m.type in hw_layers:
                        mappingNodes[m.name] = mappingIPs[m.mappedIP.name]
            if n.type in hw_layers:
                mappingNodes[n.name] = mappingIPs[n.mappedIP.name]

    print mappingNodes

    for g in gs:
        for n in g.nodes:
            n.mappedIP = mappingNodes[n.name]

def drawGraph(g, mapping):
    h = nx.relabel_nodes(g, mapping)
    nx.draw(h, with_labels=True, font_weight = 'bold')
    plt.show()

def createIPGraph(gs, hw_layers):
    IP_g = nx.DiGraph()
    mapping = dict()
    for g in gs:
        for n in list(g.nodes):
            if n.type not in hw_layers:
                g.remove_node(n)
    assignOriginalNodeMapping(gs, hw_layers)
    #collect the set of IPs used 
    IPSet = set()
    for g in gs:
        for n in g.nodes:
            print 'aaa', n.mappedIP.name, n.mappedIP
            IPSet.add(n.mappedIP)
    print "bbb", len(IPSet)
    #create one node for an IP
    for ip in IPSet:
        IP_g.add_node(ip)
    #add the DDR node
    IPDDR = IP("DDR", "DDR", None, None)
    IP_g.add_node(IPDDR)

    print "ccc", len(list(IP_g.nodes))

    for n in IP_g.nodes:
        mapping[n] = n.name

    print "mapping", mapping

    #for each edge in the graph, add the stream edge
    for g in gs:
        for (s,t) in g.edges():
            print "s ->t", s.name , "->", t.name, s.mappedIP.name, "->", t.mappedIP.name
            IP_g.add_edge(s.mappedIP, t.mappedIP)
    #for the node that has not in degree or out degree, add edge to DDR
    for g in gs:
        for n in g.nodes():
            if g.in_degree(n) == 0:
                IP_g.add_edge(IPDDR, n.mappedIP)
            if g.out_degree(n) == 0:
                IP_g.add_edge(n.mappedIP, IPDDR)
#    drawGraph(IP_g, mapping)
    return IP_g
    

def readTemplate(funcType):
    memIns = []
    memOuts = []
    neces = []
    streamIns = []
    streamOuts = []

    f = open("./CodeGen/IPTemplates/"+str(funcType))
    fList = f.readlines()
    f.close()

    idx = 0
    while(idx < len(fList)):
        lList = fList[idx].split()
        if lList[0] == "MEMIN":
            inPortNums = int(lList[1])
            for i in range(inPortNums):
                idx+=1
                memIns.append(fList[idx].strip())
        elif lList[0] == "MEMOUT":
            outPortNums = int(lList[1])
            for i in range(outPortNums):
                idx+=1
                memOuts.append(fList[idx].strip())
        elif lList[0] == "STREAMIN":
            streamInNum = int(lList[1])
            for i in range(streamInNum):
                idx+=1
                streamIns.append(fList[idx].strip())
        elif lList[0] == "STREAMOUT":
            streamOutNum = int(lList[1])
            for i in range(streamOutNum):
                idx+=1
                streamOuts.append(fList[idx].strip())
        elif lList[0] == "NECESSARY":
            neceNum = int(lList[1])
            for i in range(neceNum):
                idx+=1
                neces.append(fList[idx].strip())
        else:
            print "Unsupported type, should be one of MEMIN, MEMOUT, STREAMIN, STREAMOUT, NECESSARY"
        idx+=1
    return memIns, memOuts, neces, streamIns, streamOuts


#mIn,mOut,neces, sIns, sOuts = readTemplate("Convolution")
#print "mIn", mIn
#print "mOut", mOut
#print "neces", neces
#print "sIns", sIns
#print "sOuts", sOuts