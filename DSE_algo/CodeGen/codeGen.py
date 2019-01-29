import networkx as nx
import matplotlib
import matplotlib.pyplot as plt
#plt.switch_backend('agg')
from copy import copy
from MUX import *
from codeGenUtils import *

class ip:
    def __init__(self, name, type_):
        self.args = []
        self.name = name
        self.type = type_

#Add in mux nodes and edges
def expandGraph(g):
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
            expandingNodeList.append(n)
        if outD > 1:
            expandingNodeList.append(n)

    #update the graph
    for n in expandingNodeList:
        inD = g.in_degree(n)
        outD = g.out_degree(n)
        if inD > 1:
            muxtype = "MUX"+str(inD)+"to1"
            mux = MUX(muxtype, inD, 1)
            g.add_node(mux)
            for s, t in list(g.in_edges(n)):
                if s.type == "DDR":
                    continue
                g.add_edge(s, mux)
                g.remove_edge(s, t)
            g.add_edge(mux, n)
        elif outD > 1:
            muxtype = "MUX1to"+str(outD)
            mux = MUX(muxtype, 1, outD)
            g.add_node(mux)
            for s, t in list(g.out_edges(n)):
                if t.type =="DDR":
                    continue
                g.add_edge(mux, t)
                g.remove_edge(s, t)
            g.add_edge(n, mux)

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
    print n.name, n.type, memIns, memOuts, neces, streamIns, streamOuts

    memInFlag = memOutFlag = False
    streamInFlag = not(g.in_degree(n) == 1 and list(g.in_edges(n))[0][0].type == "DDR")
    streamOutFlag = not(g.out_degree(n) == 1 and list(g.out_edges(n))[0][1].type == "DDR")
    for (s,t) in g.in_edges(n):
        if s.type == "DDR":
            memInFlag = True
            inEdge =(s,t)
            break
    for (s,t) in g.out_edges(n):
        if t.type == "DDR":
            memOutFlag = True
            outEdge = (s,t)
            break
    #MEM IN
    if(memInFlag):
        ports = g.edges[inEdge]['portNames']
        for i in range(len(list(ports))):
            portName = n.name + "_M_in"+str(ports[i])
            n.args.append(portName)
            topArg.append(memIns[i] + " " + portName)
    #MEM OUT
    if(memOutFlag):
        ports = g.edges[outEdge]['portNames']
        print "ports", ports
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
    print "streamArgs", streamArgs
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
