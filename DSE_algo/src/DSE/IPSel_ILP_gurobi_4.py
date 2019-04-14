import os
import filecmp
from math import ceil
import networkx as nx
import sys
from optimizer_gurobi_4 import optimizer
from graph_5 import graph
from utils_4 import *
import itertools
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path + "/../CodeGen");
from codeGenUtils import *
from codeGen import *
sys.path.append(dir_path + "/../SchedulerCodeGen");
from genSwFiles import *
sys.path.append(dir_path + "/../latency_estimation");
from infoClass import runInfo_t
from newModel import exploitK_xPCombinations

class IPSel():
    def __init__(self):
        None
    def run(self,  DSP_budget, BRAM_budget, Lat_budget, numOtherIPs, app_fileName, IP_fileName, ESP, rowStep, batchSize, \
           manualSetingConvIPbound, convIPlb, convIPUb) :
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
            "Pooling" : 1,
            "Convolution_g" : 1 ,
             "Eltwise" : 1
        }   

        numConvIPs = convIPlb-1 if manualSetingConvIPbound else 0
        lat_achieved_total = Lat_budget
        latency_solution_total = None
        mapping_solution_total = None
        pipelineTable_solution_total = dict()
        numConvIPs_total =0
        numIPs_total = 0

        while(1):
            numConvIPs += 1
            if(manualSetingConvIPbound):
                if numConvIPs > convIPUb:
                    break
            numIPs = numConvIPs + numOtherIPs
            print "\n\nNumber of Convolution IP is ", numConvIPs, "\n\n"
            gs = graph(app_fileName, explore_IP_types, hw_layers)
            
            #if the numIPs is bigger than the group size, then should exit
            legalNumIPs = False
            for g in gs.graphs:
                if g in gs.exploreLayerQueue:
                    length = 0
                    for layerType in gs.exploreLayerQueue[g]:
                        length += len(gs.exploreLayerQueue[g][layerType])
                    if length >= numIPs:
                        legalNumIPs = True
                        break
            if not legalNumIPs:
                print "The number of IPs is "+str(numIPs) + "which is bigger than the biggest group size"
                break

            IPs = generateIPs(IP_fileName, gs.containedHwType, numConvIPs)

            IP_table = constructIPTable(IPs,DSP_budget, gs.exploreLayerQueue, explore_IP_types, numIPs)

            if IP_table is None:
                print "Cannot fit in " + str(numIPs) +", exiting...\n"
                break

            #Flatten the IP_table
            IP_list = []
            for layer_type in IP_table:
                if layer_type in explore_IP_types:
                    IP_list += IP_table[layer_type]

            def comp(elem):
                return -(elem.DSP)

            IP_list.sort(key = comp)
            lat_achieved = Lat_budget
            mapping_solution = dict()
            latency_solution = dict()
            pipelineTable_solution = dict()
            self.abandonTable = dict()


            allIPs = [ip for ip in itertools.combinations(IP_list, numIPs) if (\
            (sum(item.DSP for item in ip) < DSP_budget) and \
            (sum(item.DSP for item in ip) > 0.5 * DSP_budget)) ]
            
            #pick N IPs out of the IP list
            numIters = ncr(len(IP_list), numIPs)
            print "There are", numIters, "iterations before optimization, Now there are " + \
                str(len(allIPs)) + " iterations."

            if len(allIPs) == 0:
                print "Cannot fit in " + str(numIPs) +", exiting...\n"
                break

            nums = 0


            for IPs in allIPs:
                nums += 1
                tmp = ""
                for ip in IPs:
                    tmp += ip.name + " "
                print str(nums), "iteration", " selected IPs: ", tmp
                
                numConvs = 0
                for ip in IPs:
                    numConvs += (ip.type == "Convolution" or ip.type == "Convolution_g")
                if numConvs != numConvIPs:
                    print "The number of convolution IPs is not correct"
                    continue

                #if the selected set of IPs are subset of the abandoned set, continue
                if self.isInAbandonTable(IPs):
                    print "IPs in abandonTable"
                    continue

                self.updateAbandonTable(IPs)

                IP_dict = dict()
                valid = True
                for ip in IPs:
                    if ip.type not in IP_dict:
                        IP_dict[ip.type] = [ip]
                    else:
                        IP_dict[ip.type].append(ip)

                #If some of the layers'type is not in the current IP selection, then continue
                layerQueue = []
                for g in gs.graphs:
                    if g not in gs.exploreLayerQueue:
                        continue
                    for ip_type in gs.exploreLayerQueue[g]:
                        if ip_type not in IP_dict:
                            print ip_type, "not in IP dict"
                            valid = False
                            break
                    if not valid:
                        break
                if not valid:
                    print "some of the layers type not in the current IP selection, continue"
                    continue
                acc_lat = 0
                #Generate the IP_table_per_layer and layerIPLatencyTable 

                layerIPLatencyTable = computeIPLatencyPerLayer(IP_dict, gs.exploreLayerQueue, hw_layers)

                valid = True
                lat_left = lat_achieved
                layerQueue = []
                mapping_solution_tmp = dict()
                latency_solution_tmp = dict()
                pipelineTable_tmp = dict()

                for g in gs.graphs:
                    if g not in gs.exploreLayerQueue:
                        continue
                    self.updateLayerQueue(gs.exploreLayerQueue[g], layerQueue)
                    opt = optimizer(lat_left, rowStep)
                    #If some of the graph, there is no feasible solution, then the current selection of IPs cannot work
                    lat, sol, pipelineTable = opt.run(IP_dict, gs, g, hw_layers, explore_IP_types, numIPs, layerIPLatencyTable, ESP, IP_table)
            
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
                    latency_solution_tmp[g] = lat
                    pipelineTable_tmp[g] = pipelineTable
                if not valid:
                    print "cannot find valid latency, continue"
                    continue
                lat_achieved = acc_lat
                for g in mapping_solution_tmp:
                    mapping_solution[g] = mapping_solution_tmp[g]

                for g in latency_solution_tmp:
                    latency_solution[g] = latency_solution_tmp[g]

                for g in pipelineTable_tmp:
                    pipelineTable_solution[g] = pipelineTable_tmp[g]

            if not mapping_solution:
                continue
            if lat_achieved < lat_achieved_total:
                lat_achieved_total = lat_achieved
                latency_solution_total = latency_solution
                mapping_solution_total = mapping_solution
                for g in pipelineTable_solution:
                    for (s, t) in pipelineTable_solution[g]:
                        pipelineTable_solution_total[(s.name, t.name)] = 1
                numConvIPs_total = numConvIPs
                numIPs_total = numIPs
        #post processing
        if not mapping_solution_total:
            print "No feasible solutions"
            return

        final_graph_list = reorderMapping(mapping_solution_total, hw_layers, pipelineTable_solution_total)
        roundInfoList, IPinfoList = self.genIPinfoLayerInfoList(final_graph_list, pipelineTable_solution_total)
        
        ridx = 0
        print "\n\n\nroundInfo\n"
        for r in roundInfoList:
            print "round "+ str(ridx) + "\n"
            print r
            ridx += 1

        print "\n\nipInfo\n"
        for ip in IPinfoList:
            print ip

        
        
#        self.codeGen(lat_achieved_total, latency_solution_total, mapping_solution_total, hw_layers, gs, batchSize, numConvIPs_total, numIPs_total)

        rowStep, latency = exploitK_xPCombinations(roundInfoList, IPinfoList, BRAM_budget)
        print "latency",  latency
        print "rowStep", rowStep
        
        return lat_achieved_total

    def genIPinfoLayerInfoList(self, final_graph_list, pipelineTable_solution_total):
        pipelineTargetNodes = dict()

        IPinfoDict = dict()
        IPinfoList = []
        for g in final_graph_list:
            for n in g.nodes():
                IPinfoDict[n.mappedIP.name] = n.mappedIP.IPinfo
        idx = 0
        for n in IPinfoDict:
            IPinfoDict[n].IPidx = idx
            print IPinfoDict[n].IPidx
            IPinfoList.append(IPinfoDict[n])
            idx += 1

        for (s, t) in pipelineTable_solution_total:
            pipelineTargetNodes[t] = 1
        roundInfoList = []
        for g in final_graph_list:
            roundInfoList_row = []
            for n in g.nodes():
                nextIPidx = None if n.name not in pipelineTargetNodes else 1
                n.mappedIP.IPinfo = IPinfoDict[n.mappedIP.name]
                runInfo = runInfo_t(n.layerInfo, n.mappedIP.IPinfo.IPidx, 
                        nextIPidx, None)
                roundInfoList_row.append(runInfo)
            roundInfoList.append(roundInfoList_row)
        return roundInfoList, IPinfoList

    def codeGen(self, lat_achieved, latency_solution, mapping_solution, hw_layers, gs, batchSize, numConvIPs, numIPs):
        print "\n\n #####################################################################"
        print "Final latency_achieved", lat_achieved, "number of IPs are ", numIPs, "number of convIPs are ", numConvIPs
        print "each round latency is as follows",
        def comp(item):
            for n in item.nodes:
                if n.type in hw_layers:
                    return n.ID

        latency_list = []

        for g in latency_solution:
            latency_list.append(g)
        latency_list.sort(key=comp)
        for g in latency_list:
            print "round contain"
            for n in g.nodes:
                print n.name,
            print ", total latency is ", latency_solution[g], "\n"

        #layerPipeInfo
        pipeInfoTable = genPipeInfo(mapping_solution, hw_layers)
        #After the is done, re-order the mapping
        final_graph_list = reorderMapping(mapping_solution, hw_layers) 

        for g in final_graph_list:
            print gs.printNodesMapping(hw_layers, g)

        #CodeGen process
        outHwDir = "./outputFiles/hw"
        outSwDir = "./outputFiles/sw"
        os.system("mkdir -p " + outHwDir)
        os.system("mkdir -p " + outSwDir)

        #Gen HW
        IP_g = createIPGraph(final_graph_list, hw_layers)
        expandGraph(IP_g)
        muxSelTable = assignMuxSelTable(IP_g)
        assignStreamPorts(IP_g, 2)
        genTop(IP_g, outHwDir, batchSize)
        #Gen CSV
        genCSVConfigs(final_graph_list, IP_g, muxSelTable, hw_layers, outHwDir, pipeInfoTable)

        #GenFindBestRowStep
        newPipeInfoFile = outHwDir+"/pipeInfo.csv"
        newRowStepFile = outHwDir + "/rowStep.csv"

        findBestRowStep(newPipeInfoFile, newRowStepFile)
        
        oldRowStepFile = outHwDir + "/rowSteps"

        #compare the old and new rowstep file
        cmd = "sort -o " + oldRowStepFile + " " + oldRowStepFile
        os.system(cmd)
#        print "oldRowStepFile abcd"
#        os.system("cat " + oldRowStepFile)
        cmd = "sort -o " + newRowStepFile + " " + newRowStepFile
        os.system(cmd)
#        print "newRowStepFile abcd"
#        os.system("cat " + newRowStepFile)
        if(filecmp.cmp(oldRowStepFile, newRowStepFile)):
            print "They are the same"
            converged = True
            return converged
        else:
            converged = False

        #rowStepGen
        genRowStepFile(final_graph_list, outHwDir) 

        #Gen Scheduler
        functionArgs = readFunctionArgs(outHwDir)
        genSchedulerFile(functionArgs, outSwDir)
        genXkernelH(functionArgs, outSwDir)
        genXkernelCPP(functionArgs, outSwDir)
        copyUtilsCSV(outSwDir)
        
        return converged


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
                    break
            idx_tmp = ii
            #Intersect the set of the IPs that are smaller than all layers
            geqIPSet = set([x[1] for x in layerIPLatencyTable[l][1][idx_tmp : ]]) if geqIPSet is None else \
                geqIPSet & set([x[1] for x in layerIPLatencyTable[l][1][idx_tmp : ]])

        #Update the abandonset
#        print "updateAbandonSet, before", len(self.abandonTable)
        for IPs in itertools.combinations(list(geqIPSet),  numIPs):
            self.updateAbandonTable(IPs)
#        print "updateAbandonSet, after", len(self.abandonTable)
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

def reorderMapping(mapping_solution, hw_layers, pipelineNameTable):
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
    layerInfoDict = dict()
    IPsIdx =  dict()
    firstLayerName = ""
    for g in mapping_solution:
        for n in mapping_solution[g].nodes():
            if n.type is "combineNode":
                for m in n.node_list:
                    if m.type in hw_layers:
                        if m.firstLayer:
                            firstLayerName = m.name
                        layerInfoDict[n.name] = n.layerInfo
                        IPName = m.mappedIP.name.split("_")[0]
                        if IPName not in IPs:
                            IPs[IPName] = set([m.mappedIP]) 
                        else:
                            IPs[IPName].add(m.mappedIP)
            if n.type in hw_layers:
                if n.type in hw_layers:
                    if n.firstLayer:
                        firstLayerName = n.name
                    layerInfoDict[n.name] = n.layerInfo
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
                n.layerInfo = layerInfoDict[n.name]
                if n.name == firstLayerName:
                    n.firstLayer = True
                    n.mappedIP.firstLayer = True
                IPsIdx[IPName] += 1
                IPsIdx[IPName] %= len(IPs[IPName])
            

    #If the node is not pipelined, then remove in edges
    for g in mapping_solution:
        for n in g.nodes():
            if n.type is "Eltwise":
                assert(len(list(g.predecessors(n))) == 2)
                m0 = list(g.predecessors(n))[0]
                m1 = list(g.predecessors(n))[1]
                m = m1 if m0.ID > m1.ID else m0
                g.remove_edge(m, n)

                assert(len(list(g.successors(n))) == 2)
                m0 = list(g.successors(n))[0]
                m1 = list(g.successors(n))[1]
                m = m1 if m0.ID > m1.ID else m0
                g.remove_edge(n, m)
            if n.type in hw_layers:
                for t in g.in_edges(n):
                    m = t[0]
                    if not isPipelined(m, n, pipelineNameTable):
                        g.remove_edge(m, n)
    #If there is edge,  update memin, memout
    for g in mapping_solution:
        for (s,t) in g.edges():
            print s.name, s.mappedIP.name,  "-->", t.name, t.mappedIP.name
            if(t.type == "Eltwise"):
                t.layerInfo.memInR = False 
            else:
                t.layerInfo.memIn = False
            s.layerInfo.memOut = False

    for g in mapping_solution:
        nodes_list= [x for x in list(g.nodes()) if x.type in hw_layers]
        nodes_list.sort(key =comp)
        nodes_nodes_list = list()
        nSplit(nodes_list, nodes_nodes_list)
        
        for nl in nodes_nodes_list:
            sub_g = g.subgraph(nl)
            graph_list.append(sub_g)

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

def genPipeInfo(mapping_solution, hw_layers):
    layerInfoTable = dict()
    for g in mapping_solution:
        for n in list(mapping_solution[g].nodes):
            if n.type not in hw_layers:
                continue

            lineList = [n.Pipelined]
            if n.Pipelined:
                n.memIn = False
            else:
                n.memIn = True
            succList = list(mapping_solution[g].successors(n))
            if(len(succList) >= 1):
                n.memOut = True
            elif(len(succList) == 0):
                n.memOut = True
            else:
                n.memOut = False if(succList[0].Pipelined) else True

            lineList.append(int(n.memIn))
            lineList.append(int(n.memOut))
            in_height, in_width = map(int, n.input_params[2:4])
            out_height, out_width = map(int, n.output_params[2:4])
            if(n.type == "Convolution" or n.type == "Convolution_g"):
                group = 0 if n.type == "Convolution" else 1
                cout, cin, kw, kh = map(int, (n.params[0].split("=")[1]).split("x")) 
                out_height, out_width = map(int, n.output_params[2:4])
                S = int(n.params[1].split("=")[1])
                padding = int(n.params[2].split("=")[1])
                group = int(n.params[4].split("=")[1])
                maxRowStep = n.computeMaxRowStep()
                XI_KER_PROC, XI_PIX_PROC, XI_IBUFF_DEPTH, \
                XI_OBUFF_DEPTH, XI_WEIGHTBUFF_DEPTH = n.mappedIP.paramList
                if(ceil(float(cin)/4) * ceil(float(cout)/XI_KER_PROC) * kh * kw <= XI_WEIGHTBUFF_DEPTH * 2):
                    oneTime = True
                else:
                    oneTime = False
                lineList += [in_height, in_width, out_height, out_width, cout, cin, S, kh, kw, padding, group, maxRowStep, oneTime, n.ID]
            elif(n.type == "Pooling"):
                PoolType = n.params[0].split("=")[1]
                N = int(n.params[1].split("=")[1])
                kw = kh = int(n.params[2].split("=")[1])
                S = int(n.params[3].split("=")[1])
                padding = int(n.params[4].split("=")[1])
                cout=cin = int(n.params[1].split("=")[1])
                oneTime = False
                maxRowStep = 1000
                group = 0
                lineList += [in_height, in_width, out_height, out_width, cout, cin, S, kh, kw, padding, group, maxRowStep, oneTime, n.ID]
            elif(n.type == "Eltwise"):
                cout, cin, kw, kh = map(int, (n.params[0].split("=")[1]).split("x"))
                lineList += [out_height, out_width, cout, 1000, n.ID]
            if(n.type == "Convolution" or n.type == "Convolution_g"):
                int6 = 1
                lineList += [XI_KER_PROC, XI_PIX_PROC, XI_WEIGHTBUFF_DEPTH, int6]
            layerInfoTable[n.ID] = lineList
    return layerInfoTable
