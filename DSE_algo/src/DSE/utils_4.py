from IP import IP
import math
from copy import deepcopy
def constructIPTable(IPs, BRAM_budget, DSP_budget, FF_budget, LUT_budget, layerQueue, explore_IP_types, pipelineLength):
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
            minResourceIP[ip.type] = [ip.BRAM, ip.DSP, ip.FF, ip.LUT]
        else:
            minBRAM, minDSP, minFF, minLUT = minResourceIP[ip.type]
            minResourceIP[ip.type] = [min(minBRAM, ip.BRAM), min(minDSP, ip.DSP), min(minFF, ip.FF), min(minLUT, ip.LUT)]

    minBRAM_total = 0;
    minDSP_total = 0;
    minFF_total = 0;
    minLUT_total = 0;
    
    for t in minResourceIP:
        minBRAM_total += minResourceIP[t][0]
        minDSP_total += minResourceIP[t][1]
        minFF_total += minResourceIP[t][2]
        minLUT_total += minResourceIP[t][3]
    
    #print minBRAM_total, minDSP_total, minFF_total, minLUT_total, minBRAM_total

    for ip in IPs:
        # TODO: currently the number of IPs is calculated as: if only this IP is instantiated, what is the number
        # An optimization is, assume the smallest IP of each category is generated once, and the number of IPs of each
        # Category. E.g., 1 smallest Pool and 1 smallest Conv have to be instantiated for functionality. So the number
        # of Pools should be (total_resource - smallest_conv_resource)/pool_resource. This should reduce the number
        # of variables  
        BRAM_budget_local = BRAM_budget - (minBRAM_total - minResourceIP[ip.type][0])
        DSP_budget_local = DSP_budget - (minDSP_total - minResourceIP[ip.type][1])
        FF_budget_local = FF_budget - (minFF_total - minResourceIP[ip.type][2])
        LUT_budget_local = LUT_budget - (minLUT_total - minResourceIP[ip.type][3])

        if ip.type not in explore_IP_types:
            IP_table[ip.type] = [ip]

        else:
            IP_resource = min(BRAM_budget_local/ip.BRAM, DSP_budget_local/ip.DSP, FF_budget_local/ip.FF, LUT_budget_local/ip.LUT)
            IP_num = 0
            for g in layerQueue:
                if ip.type not in layerQueue[g]:
                    continue
                else:
                    IP_num = max(IP_num, min(IP_resource, len(layerQueue[g][ip.type])))
        
            IP_num = min(IP_num, pipelineLength)

        IP_type = ip.type
        maxIPnum = max(maxIPnum, IP_num)
#        print ip.name, ip.type, "IP_num", IP_num
        for i in range(IP_num):
            new_ip = deepcopy(ip)
            new_ip.name += ("_"+str(i))
            if IP_type in IP_table:
                IP_table[IP_type].append(new_ip)
            else:
                IP_table[IP_type] = [new_ip]
#    if maxIPnum < pipelineLength:
#        return None
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

def resourceConstr(layer, ip):
    """
    Function to generate CHaiDNN specific constraints about the buffer size.
    The following must be satisified for correct functionality

    Args:
        layer: layer class. one layer in the application
        ip: The IP class. One IP

    Return:
        const. The list of constraints. Currently only two elements:
            The lower bound of XI_ISTGBUFFDEPTH and XI_OSTGBUFFDEPTH
    """ 
    #FIXME: This is hard-coded for one type of IP only. Should be modified
    assert(layer.type == "Convolution" or layer.type == "Convolution_g"), "Unsupported layer type"

    in_depth, in_height, in_width = map(int, layer.input_params[1:4])
    out_depth, out_height, out_width = map(int, layer.output_params[1:4])
    cout, cin, kw, kh = map(int, (layer.params[0].split("=")[1]).split("x"))
    S = int(layer.params[1].split("=")[1])

#    print layer.params[1]
    const = []

    #FIXME: This 32 may need to be changed later, should not be fixed
    if layer.firstLayer:
        const.append(((layer.rowStep-1)*S+kh)*64)
    else:
        const.append(in_width * math.ceil(float(in_depth)/64) * (kh + (2*layer.rowStep-1)*S))
    #const.append(in_width * 8)
    const.append(out_width * math.ceil(float(out_depth)/32) * layer.rowStep)

#    print "in_depth", layer.name, in_depth, in_height, in_width, kh, S, const

    return const
    
def genIPTablePerLayer(IP_table, layerQueue, hw_layers):
    """
    After generating the general IP_table, there are some IP specific constraints, 
    These are application (layer) related. 
    So for each layer, the IP candidates may be just a subset of general IP table.
    This can reduce the number of variables in the ILP solution.

    Args:
        IP_table: Dict. The general IP_table. The output of function constructIPTable
            Key: The IP type. Value: The list of IPs in that type
        layerQueue:
            the dict of layers that are in the application (NN).
            Key: The layer type.  Value: The list of layers that are in that type
        hw_layers: 
            The dict of layers that can be mapped to hardware.
            Key: The hardware supported layer type. Value: Dont'care
    Return:
        the dictionary of IP_table that is customized for each layer.
        Key: The layer class. Value: The list of IPs that can be mapped to the layer
    """
    #FIXME currently this is hard-coded, since only 1 type of IP is there
    ret = dict()
    for g in layerQueue:
        for layerType in layerQueue[g]:
            if layerType in hw_layers:
                for l in layerQueue[g][layerType]:
#                    print l.name
                    ret[l] =  []
                    IP_queue = IP_table[layerType]
                    for ip in IP_queue:
                        if layerType != "Convolution" and layerType != "Convolution_g":
                            ret[l].append(1)
                        else:
                            const = resourceConstr(l, ip)
#                            print const, ip.name, ip.paramList
                            ret[l].append(0) if (const[0] > ip.paramList[2] or const[1] > ip.paramList[3]) else ret[l].append(1)
                    if sum(ret[l]) == 0:
                        return None
    return ret

def computeIPLatencyPerLayer(IP_table, layerQueue, hw_layers, IPTablePerLayer):
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
#                    print layer_inst.name, idx, IPTablePerLayer
                    if IPTablePerLayer[layer_inst][idx] == 0:
                        continue
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
