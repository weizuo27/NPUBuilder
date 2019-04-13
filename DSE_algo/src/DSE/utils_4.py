from IP import IP
import math
from copy import deepcopy
def constructIPTable(IPs, DSP_budget, layerQueue, explore_IP_types, pipelineLength):
    '''
    To construnct the IP_table.
    Basically, according to the resource consumption of each IP, the maximum numbers of IPs of that type can be allocated is
    min(floor(*_budget/IP.*_budget))
    Args: 
        IPs: The list of IPs which are available to choose from
        *_budget: The budget of each resource type
        layerQueue: The dict of layers that are in the application (NN).
            Key: The layer type.  Value: The list of layers that are in that type
    return: 
        IP_table: The dictionary. Key is the IP_type. Value is a list of IP * (number of IPs that can fit into the FPGA)
    '''
    #NOTE: Assume ALL the IPs in the table, the types appear in the the application.
    #Namely, there is no type of the IP that cannot be used in the application

    IP_table = dict()
    maxIPnum = 0
    minResourceIP = dict() #The minimum resource for each IP. key: IP_type. value [BRAM, DSP, FF, LUT]
    for ip in IPs:
        if ip.type not in minResourceIP:
            minResourceIP[ip.type] = ip.DSP
        else:
            minDSP = minResourceIP[ip.type]
            minResourceIP[ip.type] = min(minDSP, ip.DSP)

    minDSP_total = 0;
    
    for t in minResourceIP:
        minDSP_total += minResourceIP[t]
    
    for ip in IPs:
        DSP_budget_local = DSP_budget - (minDSP_total - minResourceIP[ip.type])
        if ip.type not in explore_IP_types:
            IP_table[ip.type] = [ip]
        else:
            IP_resource = DSP_budget_local/ip.DSP
            IP_num = 0
            for g in layerQueue:
                if ip.type not in layerQueue[g]:
                    continue
                else:
                    IP_num = max(IP_num, min(IP_resource, len(layerQueue[g][ip.type])))
        
            IP_num = min(IP_num, pipelineLength)

        IP_type = ip.type
        maxIPnum = max(maxIPnum, IP_num)
        for i in range(IP_num):
            new_ip = deepcopy(ip)
            new_ip.name += ("_"+str(i))
            if IP_type in IP_table:
                IP_table[IP_type].append(new_ip)
            else:
                IP_table[IP_type] = [new_ip]
    return IP_table

def generateIPs(fileName, containedHwType, numIPs):
    """
    To generate the list of IPs from the IP_config file.
    Args:
        fileName: The string, indicate the IP_config file name
        containedHwType: The layer types that in a NN which can be mapped to HW
    Return:
        IPs: The list of IPs that are to be considered
    """
    IPs = list()
    f = open(fileName, "r")
    next(f) #Skip the first line since the first line is just the name of each column
    for l in f:
        IP_name, layer_type, BRAM, DSP, FF, LUT, XI_KER_PROC, XI_PIX_PROC, \
        XI_IBUFF_DEPTH, XI_OBUFF_DEPTH, XI_WEIGHTBUFF_DEPTH  = (l.replace(" ", "")).split(",")
        if layer_type not in containedHwType:
            continue
        IP_inst = IP(IP_name, layer_type, map(int, [BRAM, DSP, FF, LUT]), \
                [XI_KER_PROC, XI_PIX_PROC, XI_IBUFF_DEPTH, XI_OBUFF_DEPTH, XI_WEIGHTBUFF_DEPTH], numIPs)
        IPs.append(IP_inst)
    f.close()
    return IPs

def printViolationPath(vioPath):
    print "Violation path"
    for i, mappedIP in vioPath:
        print i.name, mappedIP,  "-->"
        
def isPipelined(s_node, t_node):
    """
    The function to check whether two nodes are pipelined
    Args:
        s_node: The source node 
        t_node: The target node
    Return:
        bool: True if they are pipelined, False otherwise
    """
#FIXME: This only works for NNs that is a chain
    return t_node.Pipelined

def computeIPLatencyPerLayer(IP_table, layerQueue, hw_layers):
    def keyComp(elem_tuple):
        return elem_tuple[1] #Return latency

    layerIpLatencyTable = dict()

    for g in layerQueue:
        for layer_type in layerQueue[g]:
            if layer_type not in hw_layers:
                continue
            layer_q = layerQueue[g][layer_type]
            ip_q = IP_table[layer_type]
            for layer_inst in layer_q:
                row = []
                row_final = []
                for idx, ip in enumerate(ip_q):
                    lat = layer_inst.computeLatencyIfMappedToOneIP(ip)
                    row.append((ip, lat, idx))

                row.sort(key=keyComp)
                for ip, lat, idx in row:
                    row_final.append((idx,ip))
                layerIpLatencyTable[layer_inst] = [row, row_final]
    return layerIpLatencyTable

def unconstrMapping(g, layerQueue, layerIpLatencyTable, IP_table, explore_IP_types):
    bram, dsp, ff, lut = 0, 0, 0, 0
    for l_type in layerQueue:
        for l in layerQueue[l_type]:
            if l in layerIpLatencyTable:
                minIP, lat, idx = layerIpLatencyTable[l][0][0]
                l.mappedIP = minIP
                bram += minIP.BRAM
                dsp += minIP.DSP
                ff += minIP.FF
                lut += minIP.LUT
    for n in g.G.nodes:
        idx = 0;
        if n.type not in explore_IP_types:
            n.set_IP(deepcopy(IP_table[n.type][idx]))
            idx += 1
        if n == g.root:
            n.Pipelined = False
        else:
            n.Pipelined = True
    return bram, dsp, ff, lut
 
import operator as op
from functools import reduce

def ncr(n, r):
    r = min(r, n-r)
    numer = reduce(op.mul, range(n, n-r, -1), 1)
    denom = reduce(op.mul, range(1, r+1), 1)
    return numer / denom
