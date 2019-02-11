import networkx as nx
import matplotlib
import matplotlib.pyplot as plt
#plt.switch_backend('agg')
from copy import copy
from MUX import *
from codeGenUtils import *
from codeGenUtils2 import *
from genDispatcher import *

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
        if n not in muxIdxTable:
            muxIdxTable[n] = 0
        if "MUX" in n.name:
            if g.in_degree(n) > 1:
                for s, t in g.in_edges(n):
                    muxSelTable[n, (s, t)] = muxIdxTable[n]
                    muxIdxTable[n] += 1
            elif g.out_degree(n) > 1:
                for s, t in g.out_edges(n):
                    muxSelTable[n, (s, t)] = muxIdxTable[n]
                    muxIdxTable[n] += 1
    return muxSelTable

def assignStreamPorts(g, streamPortsNum):
    Ports = dict()
    idx_stream = 0;
#    idx_memIn = idx_memOut = 0;
    for (s, t) in g.edges():
        if s.type == "DDR":
#            continue
            Ports[(s, t)] = [x for x in range(2)]
#            idx_memIn += memInPortsNum
        elif t.type == "DDR":
#            continue
            Ports[(s, t)] = [x for x in range(2)]
#            idx_memOut += memOutPortsNum
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
#    if "ip_l" in n.name:
#        return
    print "n.type", n.type, n.name
    if n.type == "Eltwise":
        functionName = n.name+"::"+n.type
        f = open(fileName, 'a')

        #add csim labels
        f.write("#ifdef __CSIM___\n")
        f.write("LABEL_"+n.name+":\n")
        f.write("#endif\n")

        f.write("\t\t"+functionName + "(\n")
#        if n.type == "Eltwise":
        #write left mem in

#        ip_l = n.ip_l
#        for arg in ip_l.args:
#            f.write("\t\t\t"+arg+",\n")
        for idx, arg in enumerate(n.args):
            if(idx != len(n.args)-1):
                f.write("\t\t\t"+arg+",\n")
            else:
                f.write("\t\t\t"+arg+"\n")
        f.write("\t\t);\n");

        #add csim labels
        f.write("#ifdef __CSIM___\n")
        f.write("goto LABEL_"+n.name+"_NEXT;\n")
        f.write("#endif\n")

        f.close()

    else:
        functionName = n.name+"::"+n.type
        if "MUX" in n.name:
            functionName = n.type
        f = open(fileName, 'a')

        #add csim labels
        f.write("#ifdef __CSIM___\n")
        f.write("LABEL_"+n.name+":\n")
        f.write("#endif\n")

        f.write("\t\t"+functionName + "(\n")
        for idx, arg in enumerate(n.args):
            if(idx != len(n.args)-1):
                f.write("\t\t\t"+arg+",\n")
            else:
                f.write("\t\t\t"+arg+"\n")
        #FIXME This is specific to chaidnn
        if(n.type == "Convolution"):
            f.write("#ifdef __SDSVHLS__\n")
            f.write("\t, ap_clk_div2\n")
            f.write("#else\n")
            f.write("\t, 0\n")
            f.write("#endif\n")
        f.write("\t\t);\n");

        #add csim labels
        f.write("#ifdef __CSIM___\n")
        f.write("goto LABEL_"+n.name+"_NEXT;\n")
        f.write("#endif\n")

        f.close()
    

def genTop(g):
    topArgs = []
    streamArgs = []
    ArgDispatchArgs = []

    memName = "int * MemArgs"
    memNameOnly = "MemArgs"

    topArgs.append([memName])

    #collect the IP names
    IPNames = []
    for n in g:
#        if "ip_l" in n.name:
#            continue
        IPNames.append(n.name)



    for n in g:
        if n.type == "DDR":
            continue
        a, b, c = (genWrapper(g, n))
        topArgs.append(a)
        streamArgs += b
        ArgDispatchArgs += c

    #genCPP
    fileName = "pipeSystem.cpp"
    genIncludeHeaders(fileName, IPNames)
    dispatcherDeclare(fileName, ArgDispatchArgs)
    genTopFunctionPre(topArgs, fileName)
    genHLSPragmas(fileName)
    genStreamPorts(list(set(streamArgs)), fileName)
    dispatcherCall(fileName, memNameOnly, ArgDispatchArgs)

    for n in g:
        genSubFunction(n, fileName)
    genTopFunctionRail(fileName)

    #genHeaderFile
    fileName = "pipeSystem.h"
    genHeaderFilePre(fileName)
    genSDSOCZero_Copy(fileName, topArgs)
    genSDSOCSYS_Port(fileName, topArgs)
    genTopFunctionPre(topArgs, fileName, True)
    genHeaderFileRail(fileName)

    #genWrapperDNN file
    wrapperFileName = "dnn_wrapper.cpp"
    genWrapperDnnFile(wrapperFileName, topArgs)

    #genIPPack cmds
    genIPPackCmd("ippackGen.sh", "ipNameList", g)
def genWrapper(g, n):
    n.args = []
    streamArgs = []
    topArg = []
    dispatcherList = []
    memIns, memOuts, neces, streamIns, streamOuts = readTemplate(n.type)

    n.streamInFlag = not(g.in_degree(n) == 1 and list(g.in_edges(n))[0][0].type == "DDR") and g.in_degree(n) > 0
    n.streamOutFlag = not(g.out_degree(n) == 1 and list(g.out_edges(n))[0][1].type == "DDR") and g.out_degree(n) > 0

    for (s,t) in g.in_edges(n):
        if s.type == "DDR":
            n.memInFlag = True
            break
    for (s,t) in g.out_edges(n):
        if t.type == "DDR":
            n.memOutFlag = True
            break
    if(n.type == "Eltwise"):
    #add mem-in left
        for i in range(len(memIns)):
            portName =n.name + "il"+str(i)
            n.args.append(portName)
            topArg.append(memIns[i] + " " + portName)
    #MEM IN
    if(n.memInFlag):
#        ports = g.edges[inEdge]['portNames']
#        for i in range(len(list(ports))):
        for i in range(len(memIns)):
            portName = n.name+ "i"+str(i)
            n.args.append(portName)
            topArg.append(memIns[i] + " " + portName)
    #MEM OUT
    if(n.memOutFlag):
#        ports = g.edges[outEdge]['portNames']
#        print "ports", ports
#        for i in range(len(list(ports))):
        for i in range(len(memOuts)):
            portName = n.name + "o"+str(i)
            n.args.append(portName);
            topArg.append(memOuts[i] + " " + portName)
    #STREAM IN
    if(n.streamInFlag):
        for edge in g.in_edges(n):
            if edge[0].type == "DDR":
                continue
            ports = g.edges[edge]['portNames']
            for i in range(len(list(ports))):
                portName = "S"+str(ports[i])
                n.args.append(portName)
                streamArgs.append((streamIns[i], portName))
    #SRTEAM OUT
    if(n.streamOutFlag):
        for edge in g.out_edges(n):
            if edge[1].type == "DDR":
                continue
            ports = g.edges[edge]['portNames']
            for i in range(len(list(ports))):
                portName = "S"+str(ports[i])
                n.args.append(portName)
                streamArgs.append((streamOuts[i], portName))
    #NECESSARY:
    notFirstLayer = 1 -int(n.firstLayer)
    for i in range(len(neces) - notFirstLayer):
        portName = "n" + n.name + str(i)
        n.args.append(portName)
        topArg.append(neces[i] + " " + portName)
    #Args:
#    if "ip_l" in n.name:
#        return topArg, streamArgs, dispatcherList
        
    if n.type == "Convolution_g":
        if n.streamInFlag:
            portName = "sArg"+n.name + "Div"
            n.args.append(portName)
            streamArgs.append(("int", portName))
            dispatcherList.append((portName, 'Divider'))

        portName = "sArg"+n.name
        n.args.append(portName)
        streamArgs.append(("int", portName))
        dispatcherList.append((portName, n.type))

        if n.streamOutFlag:
            portName = "sArg"+n.name + "Comb"
            n.args.append(portName)
            streamArgs.append(("int", portName))
            dispatcherList.append((portName, 'Combiner'))
    else:
        portName = "sArg"+n.name
        n.args.append(portName)
        streamArgs.append(("int", portName))
        dispatcherList.append((portName, n.type))

    #dispatcherList:
        
#    print "streamArgs", streamArgs
    return topArg, streamArgs, dispatcherList

def genTopFunctionPre(topArgs, fileName, headerFile = False):
    f = open(fileName, "a")

    f.write("void pipeSystem(\n");
    args_cmd = ""
    for args in topArgs:
        for arg in args:
            args_cmd += ("\t"+arg+",\n")

    args_cmd = args_cmd[0:-2] + "\n"
    f.write(args_cmd)

    f.write("#ifdef __SDSVHLS__\n")
    f.write("\t, bool ap_clk_div2\n")
    f.write("#endif\n")
    
    if headerFile:
        f.write(");\n")
    else:
        f.write("){\n")
    f.close() 

def genTopFunctionRail(fileName):
    f=open(fileName, "a")
    f.write("LABEL_END:\n")
    f.write("\treturn;" )
    f.write("}")
    f.close()

def genHLSPragmas(fileName):
    f=open(fileName, "a")
    f.write("\t#pragma HLS dataflow\n")
    f.write("\t#pragma HLS INTERFACE ap_stable port=ap_clk_div2\n")
    f.close()

def genIncludeHeaders(fileName, IPNames):
    f =open(fileName, "w")
    f.write("#include <ap_int.h>\n")
    f.write("#include <hls_stream.h>\n")
    f.write("#include \"pipeSystem.h\"\n")
    f.write("#ifdef __CSIM___\n")
    f.write("#include \"IPorder.h\"\n")
    f.write("#endif\n")
    for ipName in IPNames:
        if "IP" not in ipName:
            continue
        f.write("#include \"../" + ipName+"/"+ipName+".h\"\n")
    f.write("#include \"../otherIPs/otherIPs.hpp\"\n")
    f.close()

##################Gen header file functions
def genHeaderFilePre(fileName):
    f = open(fileName, "w")
    f.write("#include <ap_int.h>\n")
    f.write("#ifndef _PIPE_SYSTEM_H_\n")
    f.write("#define _PIPE_SYSTEM_H_\n")

    f.write("#ifdef __HLS_SYN__\n")
    f.write("#define __SDSVHLS__\n")
    f.write("#endif\n")

    f.close()

def genSDSOCZero_Copy(fileName, topArgs):
    f = open(fileName, 'a')
    for args in topArgs:
        for arg in args:
            argName = arg.split()[-1]
            if arg == "MemArgs":
                length = 1024
            else:
                length = 2 * 200704
            f.write("#pragma SDS data zero_copy("+argName+" [0:"+str(length)+"])\n")
    f.close()

def genSDSOCSYS_Port(fileName, topArgs):
    idx = 0
    MaxPorts = 4
    f = open(fileName, 'a')
    for args in topArgs:
        for arg in args:
            argName = arg.split()[-1]
            f.write("#pragma SDS data sys_port("+argName+\
                    ": ps_e_S_AXI_HP"+str(idx)+"_FPD)\n")
            idx = (idx + 1)%MaxPorts
    f.close()

def genHeaderFileRail(fileName):
    f = open(fileName, "a")
    f.write("#endif\n")
    f.close()

def genWrapperDnnFile(fileName, topArgs):
    f =open(fileName, "w")
    f.write("#ifdef __SDSOC\n")
    f.write("#include \"pipeSystem.h\"\n")
    f.write("#endif\n")
    f.write("#include \"ap_int.h\"\n")
    f.write("int ConvolutionPipeWrapper(\n")

    args_cmd = ""
    for args in topArgs:
        for arg in args:
            args_cmd += "\t"+arg+",\n"
    args_cmd = args_cmd[0:-2] + "\n"
    f.write(args_cmd)
    f.write("){\n")

    f.write("#if __SDSOC\n")
    f.write("#pragma SDS async(1)\n")
    f.write("#endif\n")

    #call pipeSystem
    f.write("\tpipeSystem(\n")
    args_cmd = ""
    for args in topArgs:
        for arg in args:
            argName = arg.split()[-1]
            args_cmd += ("\t\t" + argName + ",\n")
    args_cmd = args_cmd[0:-2] + "\n"
    f.write(args_cmd)
    f.write("\t);\n")
    f.write("\treturn 0;\n")
    f.write("}\n")

    f.close()

def genIPPackCmd(fileName, fileNameIPNameList, IP_g):
    f = open(fileName, 'w')
    for ip in IP_g:
        if "IP" not in ip.name:
            continue
        if ip.type == "Convolution":
            IPNAME = ip.name

            XI_KER_PROC, XI_PIX_PROC, XI_ISTAGE_BUFF, \
            XI_OSTAGE_BUFF, XI_WEIGHT_BUFF = ip.paramList

            STREAM_OUT = int(ip.streamOutFlag)
            STREAM_IN = int(ip.streamInFlag)
            MEM_IN = int(ip.memInFlag)
            MEM_OUT = int(ip.memOutFlag)
            LAYER1 = int(ip.firstLayer)

            paramList = ["IPCONV", IPNAME, XI_ISTAGE_BUFF, XI_OSTAGE_BUFF, XI_WEIGHT_BUFF,\
            XI_KER_PROC, XI_PIX_PROC, STREAM_OUT, STREAM_IN, MEM_IN, MEM_OUT, LAYER1]
            paramList = map(str, paramList)

        elif ip.type == "Pooling":
            IPNAME = ip.name
            STREAM_OUT = int(ip.streamOutFlag)
            STREAM_IN = int(ip.streamInFlag)
            MEM_IN = int(ip.memInFlag)
            MEM_OUT = int(ip.memOutFlag)
            paramList = ["IPPOOL", IPNAME, MEM_IN, MEM_OUT, STREAM_IN, STREAM_OUT]
            paramList = map(str, paramList)
        elif ip.type == "Eltwise":
            IPNAME = ip.name
#            if "ip_l" in ip.name:
#                continue
#            L_STREAM_IN = int(ip.ip_l.streamInFlag)
#            L_MEM_IN = int(ip.ip_l.memInFlag)
            L_STREAM_IN = 0
            L_MEM_IN = 1

            R_STREAM_IN = int(ip.streamInFlag)
            R_MEM_IN = int(ip.memInFlag)

            STREAM_OUT = int(ip.streamOutFlag)
            MEM_OUT = int(ip.memOutFlag)

            paramList = ["IPELEADD", IPNAME, L_STREAM_IN, L_MEM_IN, R_STREAM_IN, R_MEM_IN, STREAM_OUT, MEM_OUT]
            paramList = map(str, paramList)

        else:
            print "Unsupprted IP type"
            exit()
        f.write("python ippack.py " + " ".join(paramList)+"\n")
            
    fw = open(fileNameIPNameList, 'w')
    for ip in IP_g:
        if ip.type == "DDR":
            continue
        fw.write(ip.name+"\n")
    fw.close()
    f.close()
