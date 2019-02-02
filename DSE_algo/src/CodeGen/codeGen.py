import networkx as nx
import matplotlib
import matplotlib.pyplot as plt
#plt.switch_backend('agg')
from copy import copy
from MUX import *
from codeGenUtils import *
from codeGenUtils2 import *

class ip:
    def __init__(self, name, type_):
        self.args = []
        self.name = name
        self.type = type_

#Add in mux nodes and edges
def expandGraph(g):
    muxSelTable = dict()
    expandingNodeList = []
    for n in g.nodes():
        if n.type == "DDR":
            continue
        inD = outD = 0
        for (s, t) in g.in_edges(n):
            if s.type == "DDR":
                continue
            inD += 1
        for (s, t) in g.out_edges(n):
            if t.type == "DDR":
                continue
            outD += 1
        if inD > 1:
            expandingNodeList.append((n, "in",inD))
        if outD > 1:
            expandingNodeList.append((n, "out", outD))

    #update the graph
    for n, inOrOut, D in expandingNodeList:
        print "dsdas", n.name, inOrOut, D
        if inOrOut == "in":
            muxtype = "MUX"+str(D)+"to1"
            mux = MUX(muxtype, D, 1)
            g.add_node(mux)
            for idx, (s, t) in enumerate(list(g.in_edges(n))):
                if s.type == "DDR":
                    continue
                g.add_edge(s, mux)
                g[s][mux]['weight'] = 1
                g.remove_edge(s, t)
            g.add_edge(mux, n)
            g[mux][n]['weight'] = 1
        else:
            muxtype = "MUX1to"+str(D)
            mux = MUX(muxtype, 1, D)
            g.add_node(mux)
            for idx, (s, t) in enumerate(list(g.out_edges(n))):
                if t.type =="DDR":
                    continue
                g.add_edge(mux, t)
                g[mux][t]['weight'] = 1
                g.remove_edge(s, t)
            g.add_edge(n, mux)
            g[n][mux]['weight'] = 1

def assignMuxSelTable(g):
    muxIdxTable = dict()
    muxSelTable = dict()
    for n in g.nodes:
        print "ccc", n.name
        if n not in muxIdxTable:
            muxIdxTable[n] = 0
        if "MUX" in n.name:
            if g.in_degree(n) > 1:
                for s, t in g.in_edges(n):
                    print s.name, t.name
                    muxSelTable[n, (s, t)] = muxIdxTable[n]
                    muxIdxTable[n] += 1
            elif g.out_degree(n) > 1:
                for s, t in g.out_edges(n):
                    print s.name, t.name
                    muxSelTable[n, (s, t)] = muxIdxTable[n]
                    muxIdxTable[n] += 1
    return muxSelTable

def assignStreamPorts(g, streamPortsNum, memInPortsNum, memOutPortsNum):
    Ports = dict()
    idx_stream = idx_memIn = idx_memOut = 0;
    for (s, t) in g.edges():
        if s.type == "DDR":
            Ports[(s, t)] = [x for x in range(idx_memIn, memInPortsNum+idx_memIn)]
            idx_memIn += memInPortsNum
        elif t.type == "DDR":
            Ports[(s, t)] = [x for x in range(idx_memOut, memOutPortsNum+idx_memOut)]
            idx_memOut += memOutPortsNum
        else:
            Ports[(s, t)] = [x for x in range(idx_stream, streamPortsNum+idx_stream)]
            idx_stream += streamPortsNum
    nx.set_edge_attributes(g, Ports, 'portNames')

def genStreamPorts(streamArgs, fileName):
    f = open(fileName, "a")
    for arg in streamArgs:
        f.write("\t\t static hls::stream< " + arg[0] + " > " + arg[1] + ";\n")
    f.close() 

def genSubFunction(n, fileName):
    if n.type == "DDR":
        return
    functionName = n.name+"::"+n.type
    if "MUX" in n.name:
        functionName = n.type
    f = open(fileName, 'a');
    f.write("\t\t"+functionName + "(\n");
    for arg in n.args:
        f.write("\t\t\t"+arg+",\n")
    f.write("\t\t);\n");
    f.close()
    

def genTop(g):
    topArgs = []
    streamArgs = []
    for n in g:
        if n.type == "DDR":
            continue
        a, b = (genWrapper(g, n))
        topArgs.append(a)
        streamArgs += b
    fileName = "top.cpp"
    genIncludeHeaders(fileName)
    genTopFunctionPre(topArgs, fileName)
    genHLSPragmas(fileName)
    genStreamPorts(list(set(streamArgs)), fileName)
    for n in g:
        genSubFunction(n, fileName)
    genTopFunctionSub(fileName)

def genWrapper(g, n):
    n.args = []
    streamArgs = []
    topArg = []
    memIns, memOuts, neces, streamIns, streamOuts = readTemplate(n.type)
#    print n.name, n.type, memIns, memOuts, neces, streamIns, streamOuts

    streamInFlag = not(g.in_degree(n) == 1 and list(g.in_edges(n))[0][0].type == "DDR")
    streamOutFlag = not(g.out_degree(n) == 1 and list(g.out_edges(n))[0][1].type == "DDR")
    for (s,t) in g.in_edges(n):
        if s.type == "DDR":
            n.memInFlag = True
            inEdge =(s,t)
            break
    for (s,t) in g.out_edges(n):
        if t.type == "DDR":
            n.memOutFlag = True
            outEdge = (s,t)
            break
    #MEM IN
    if(n.memInFlag):
        ports = g.edges[inEdge]['portNames']
        for i in range(len(list(ports))):
            portName = n.name + "_M_in"+str(ports[i])
            n.args.append(portName)
            topArg.append(memIns[i] + " " + portName)
    #MEM OUT
    if(n.memOutFlag):
        ports = g.edges[outEdge]['portNames']
#        print "ports", ports
        for i in range(len(list(ports))):
            portName = n.name + "_M_out"+str(ports[i])
            n.args.append(portName);
            topArg.append(memOuts[i] + " " + portName)
    #STREAM IN
    if(streamInFlag):
        for edge in g.in_edges(n):
            if edge[0].type == "DDR":
                continue
            ports = g.edges[edge]['portNames']
            for i in range(len(list(ports))):
                portName = "S"+str(ports[i])
                n.args.append(portName)
                streamArgs.append((streamIns[i], portName))
    #SRTEAM OUT
    if(streamOutFlag):
        for edge in g.in_edges(n):
            if edge[1].type == "DDR":
                continue
            ports = g.edges[edge]['portNames']
            for i in range(len(list(ports))):
                portName = "S"+str(ports[i])
                n.args.append(portName)
                streamArgs.append((streamOuts[i], portName))
    #NECESSARY:
    for i in range(len(neces)):
        portName = "M_ness_" + n.name + str(i)
        n.args.append(portName)
        topArg.append(neces[i] + " " + portName)
#    print "streamArgs", streamArgs
    return topArg, streamArgs

def genTopFunctionPre(topArgs, fileName):
    f = open(fileName, "w")

    f.write("void pipeSystem(\n");
    for args in topArgs:
        for arg in args:
            f.write("\t"+arg+",\n");
    f.write("){\n");
    f.close() 

def genTopFunctionSub(fileName):
    f=open(fileName, "a")
    f.write("}")
    f.close()
def genHLSPragmas(fileName):
    f=open(fileName, "a")
    f.write("\t#pragma HLS dataflow\n")
    f.write("\t#pragma HLS INTERFACE ap_stable port=ap_clk_div2\n")
    f.close()

def genIncludeHeaders(fileName):
    f =open(fileName, "a")
#FIXME
    f.close()

