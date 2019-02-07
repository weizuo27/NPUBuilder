import os
import networkx as nx
import sys
from optimizer_gurobi_4 import optimizer
from graph_4 import graph
from utils_4 import *
import itertools
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path + "/../CodeGen");
from codeGenUtils import *
from codeGen import *

DEBUG = False
class IPSel():
    def __init__(self, BRAM_budget, DSP_budget, FF_budget, LUT_budget, BW_budget, Lat_budget, numIPs,
            app_fileName, IP_fileName, ESP, rowStep):
        status = "Undecided" 

        #Hard code the hardware supported layers
        hw_layers = { 
            "Convolution": 1,
            "Convolution_g": 1,
            "Pooling" : 1,
            "Eltwise" : 1
        }   

        #Hard code the IP types we would like to explore
        explore_IP_types = { 
            "Convolution": 1,
#            "Pooling" : 1,
            "Convolution_g" : 1 
        }   

        gs = graph(app_fileName, explore_IP_types, hw_layers, rowStep)
        IPs = generateIPs(IP_fileName)

        IP_table = constructIPTable(IPs, BRAM_budget, DSP_budget, LUT_budget, \
                FF_budget, gs.exploreLayerQueue, explore_IP_types, numIPs)
        if IP_table is None:
            print "Cannot fit in " + str(numIPs) +", exiting...\n"
            return

        IP_table_per_layer_org = genIPTablePerLayer(IP_table, gs.exploreLayerQueue, hw_layers)

        layerIPLatencyTable_org = computeIPLatencyPerLayer(IP_table, gs.exploreLayerQueue, hw_layers, IP_table_per_layer_org)

        #Flatten the IP_table
        IP_list = []
        for layer_type in IP_table:
            if layer_type in explore_IP_types:
                IP_list += IP_table[layer_type]

        def comp(elem):
            return -(elem.BRAM + elem.DSP)
        IP_list.sort(key = comp)
        lat_achieved = Lat_budget
        mapping_solution = dict()
        self.abandonTable = dict()
        #pick 3 IPs out of the IP list
        for i in IP_list:
            print i.name
        numIters = ncr(len(IP_list), numIPs)
        print "There are", numIters, "iterations"
        nums = 0
        for IPs in itertools.combinations(IP_list,  numIPs):
            nums += 1
            tmp = ""
            for ip in IPs:
                tmp += ip.name + " "
            print str(nums), "iteration", " selected IPs: ", tmp
            #if the selected set of IPs are subset of the abandoned set, continue
            if self.isInAbandonTable(IPs):
                print "IPs in abandonTable"
                continue
            self.updateAbandonTable(IPs)

            BRAMs, LUTs, FFs, DSPs  = 0, 0, 0, 0
            IP_dict = dict()
            valid = True
            for ip in IPs:
                BRAMs += ip.BRAM
                LUTs += ip.LUT
                FFs += ip.FF
                DSPs += ip.DSP
                if BRAM_budget < BRAMs or LUT_budget < LUTs or FF_budget < FFs or DSP_budget < DSPs:
                    valid = False
                    break
                if ip.type not in IP_dict:
                    IP_dict[ip.type] = [ip]
                else:
                    IP_dict[ip.type].append(ip)
            #If the resource summation exceeds the budget, continue
            if not valid:
                print "resource violation, continue"
#                print self.abandonTable
                continue
            if BRAM_budget/2 >= BRAMs or DSP_budget*0.8>= DSPs:
                print "resource too small, continue"
                continue
            #If some of the layers'type is not in the current IP selection, then continue
            layerQueue = []
            for g in gs.graphs:
                if g not in gs.exploreLayerQueue:
                    continue
                for ip_type in gs.exploreLayerQueue[g]:
                    if ip_type not in IP_dict:
                        valid = False
                        break
                if not valid:
                    break
            if not valid:
                print "some of the layers type not in the current IP selection, continue"
                continue
            acc_lat = 0
            #Generate the IP_table_per_layer and layerIPLatencyTable 
            IP_table_per_layer = genIPTablePerLayer(IP_dict, gs.exploreLayerQueue, hw_layers)
            if IP_table_per_layer is None:
                print "cannot find valid IP table per layer, continue"
                continue

            layerIPLatencyTable = computeIPLatencyPerLayer(IP_dict, gs.exploreLayerQueue, hw_layers, IP_table_per_layer)

            valid = True
            lat_left = lat_achieved
            layerQueue = []
            mapping_solution_tmp = dict()
            for g in gs.graphs:
                if g not in gs.exploreLayerQueue:
                    continue
                self.updateLayerQueue(gs.exploreLayerQueue[g], layerQueue)
                opt = optimizer(lat_left+1, rowStep)
                #If some of the graph, there is no feasible solution, then the current selection of IPs cannot work
                lat, sol = opt.run(IP_dict, gs, g, IP_table_per_layer, hw_layers, explore_IP_types, numIPs, layerIPLatencyTable, ESP, IP_table)
                if lat == None:
                    valid = False
                    break
                acc_lat += lat
                #If the current latency is worse than the achieved latency, then the current selection of IPs won't work
                if acc_lat > lat_achieved:
                    valid = False
                    break
                lat_left = lat_achieved - acc_lat
                mapping_solution_tmp[g] = sol
#            print "update!", "lat_achieved_old = ", lat_achieved, "acc_lat = ", acc_lat, "lat = ", lat
            self.updateAbandonSet(IPs, layerQueue, IP_table, IP_table_per_layer_org, layerIPLatencyTable_org, numIPs)
            if not valid:
                print "cannot find valid latency, continue"
                continue
            lat_achieved = acc_lat
            for g in mapping_solution_tmp:
                mapping_solution[g] = mapping_solution_tmp[g]

        print "Final latency_achieved", lat_achieved

        #After the is done, re-order the mapping
        final_graph_list = reorderMapping(mapping_solution, hw_layers) 

        for g in final_graph_list:
            print gs.printNodesMapping(hw_layers, g)

        #CodeGen process
        IP_g = createIPGraph(final_graph_list, hw_layers)
#        nx.draw(IP_g, with_labels=True, font_weight = 'bold')
#        plt.show()
        expandGraph(IP_g)
        muxSelTable = assignMuxSelTable(IP_g)
        assignStreamPorts(IP_g, 2)
        genTop(IP_g)
        #Gen CSV
        genCSVConfigs(final_graph_list, IP_g, muxSelTable, hw_layers)

    def updateAbandonTable(self, IPs):
        ipNames = []
        for ip in IPs:
            ip_original_name = ip.name.split("_")[0]
            ipNames.append(ip_original_name)
        ipNames.sort()
        #assert(tuple(ipNames) not in self.abandonTable), "ip name should not be in abandon table"
        if tuple(ipNames) not in self.abandonTable:
            self.abandonTable[tuple(ipNames)] = 1
    
    def updateAbandonSet(self, IPs, layerQueue, IP_table, IPTablePerLayer, layerIPLatencyTable, numIPs):
        geqIPSet = None
        #Traverse the layers in the layer queue, for all the IPs that they are exploring, 
        #Find the one with the biggest latency, and the idx
        for l in layerQueue:
            idx = 0
            lat = 1
            for ip in IPs:
                if ip.type != l.type:
                    continue
                vio_idx = IP_table[ip.type].index(ip)
                if IPTablePerLayer[l][vio_idx] == 0:
                    return
                idx_tmp = layerIPLatencyTable[l][1].index((vio_idx, ip))
#                print "idx_tmp for IP", ip.name, "is", idx_tmp, "latency is ", layerIPLatencyTable[l][0][idx_tmp][1]
                if lat < layerIPLatencyTable[l][0][idx_tmp][1]:
                    lat = layerIPLatencyTable[l][0][idx_tmp][1]
                    idx = idx_tmp

            #Find all the IPs that are bigger to the current one, 
            for ii in range(idx, -1, -1):
                lat_tmp_ii = layerIPLatencyTable[l][0][ii][1]
                if lat_tmp_ii > lat:
#                    ii = ii + 1
                    break
            idx_tmp = ii
#            print "idx_tmp =", idx_tmp
            #Intersect the set of the IPs that are smaller than all layers
#            print "layerIPLatencyTable[l][1][idx_tmp :]\n"
#            for ip in layerIPLatencyTable[l][1][idx_tmp :]:
#                print ip[1].name
            geqIPSet = set([x[1] for x in layerIPLatencyTable[l][1][idx_tmp : ]]) if geqIPSet is None else \
                geqIPSet & set([x[1] for x in layerIPLatencyTable[l][1][idx_tmp : ]])

#            print "geqIPSet", "layer", l.name
#            for ip in geqIPSet:
#                print ip.name
        #Update the abandonset
        print "updateAbandonSet, before", len(self.abandonTable)
        for IPs in itertools.combinations(list(geqIPSet),  numIPs):
            self.updateAbandonTable(IPs)
        print "updateAbandonSet, after", len(self.abandonTable)
    def isInAbandonTable(self, IPs):
        ipNames = []
        for ip in IPs:
            ip_original_name = ip.name.split("_")[0]
            ipNames.append(ip_original_name)
        ipNames.sort()
        return tuple(ipNames) in self.abandonTable


    def updateLayerQueue(self, layerQueueIn, layerQueueOut):
        for layer_type in layerQueueIn:
            layerQueueOut += layerQueueIn[layer_type]


def reorderMapping(mapping_solution, hw_layers):
    #For the solution, for each IP collect the mapping, 
    #reassign using the best order

    #This function is so messy !!! :( 
    graph_list = []
    for g in mapping_solution:
        for n in list(g.nodes):
            if n.type not in hw_layers:
                g.remove_node(n)

    assignOriginalNodeMapping(mapping_solution, hw_layers)

    #Collect the set of IPs for each IP ID
    IPs = dict()
    pipelinedDict = dict()
    IPsIdx =  dict()
    firstLayerName = ""
    for g in mapping_solution:
        for n in mapping_solution[g].nodes():
            if n.type is "combineNode":
                for m in n.node_list:
                    if m.type in hw_layers:
                        if m.firstLayer:
                            firstLayerName = m.name
                        pipelinedDict[m.name] = m.Pipelined
                        IPName = m.mappedIP.name.split("_")[0]
                        if IPName not in IPs:
                            IPs[IPName] = set([m.mappedIP]) 
                        else:
                            IPs[IPName].add(m.mappedIP)
            if n.type in hw_layers:
                if n.type in hw_layers:
                    if n.firstLayer:
                        firstLayerName = n.name
                    pipelinedDict[n.name] = n.Pipelined
                    IPName = n.mappedIP.name.split("_")[0]
                    if IPName not in IPs:
                        IPs[IPName] = set([n.mappedIP]) 
                    else:
                        IPs[IPName].add(n.mappedIP)

    for IPName in IPs:
        IPs[IPName] = list(IPs[IPName])

    #initialize idx
    for IPName in IPs:
        IPsIdx[IPName] = 0

    #Reassign IP
    for g in mapping_solution:
        #clear idx
        for IPName in IPsIdx:
            IPsIdx[IPName] = 0

        def comp(n):
            return n.ID

        nodes_list = list(g.nodes())
        nodes_list.sort(key = comp)

        for n in nodes_list:
            if n.type in hw_layers:
                IPName = n.mappedIP.name.split("_")[0]
                n.mappedIP = IPs[IPName][IPsIdx[IPName]]
                n.Pipelined = pipelinedDict[n.name]
                if n.name == firstLayerName:
                    n.firstLayer = True
                    n.mappedIP.firstLayer = True
                IPsIdx[IPName] += 1
                IPsIdx[IPName] %= len(IPs[IPName])
            

    #If the node is not pipelined, then remove in edges
    #FIXME:::: FINISH THIS: Chop the un-pipeilned nodes

    for g in mapping_solution:
        for n in g.nodes():
            if n.type in hw_layers:
                if not n.Pipelined:
                    g.remove_edges_from(list(g.in_edges(n)))

    for g in mapping_solution:
        nodes_list= [x for x in list(g.nodes()) if x.type in hw_layers]
        nodes_nodes_list = list()
        nSplit(nodes_list, nodes_nodes_list)
        
        for nl in nodes_nodes_list:
            sub_g = g.subgraph(nl)
#            nx.draw(sub_g)
#            plt.show()
            graph_list.append(sub_g)

    print "abcdef", len(graph_list)
    return graph_list

def nSplit(inList, outLists):
    hasElem = dict()
    subList = []
    for idx, n in enumerate(inList):
        if n.mappedIP.name not in hasElem:
            subList.append(n)
            hasElem[n.mappedIP.name] = 1 
        else:
            outLists.append(subList)
            nSplit(inList[idx:], outLists)
            return
    outLists.append(subList)

