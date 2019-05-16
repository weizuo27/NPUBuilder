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

import RawILP
import TestCase
import validateILP2

def genMappingTotal( solutionChoice, mapping_solution,depositIPlist ):
    print mapping_solution
    print solutionChoice
    for i in depositIPlist:
        print i.IPinfo
    return None

def generateILPInput(
    g,
    layerIpLatencyTable_ILP,
    IP_dict,
    noStreamEdgeSet,
    loneLayerSet):

    tempDictGroup={}
    h=g.copy();
    schedulingIndex=0;
    loneLayerArray=[]

    loneLayerLatency=[]

    layerArray=[]
    layerTypeArray=[]
    latencyPerIPTable=[]
    nodeListDict={}
    schedulingLoneIndex=0;

    for nd in list(h.node()):
        if nd.name == "end" or nd.name == "begin":
            h.remove_node(nd);
        elif  nd.name in loneLayerSet:
            nodeListDict[nd.name]=nd;
            loneLayerArray.append(nd);
            tempDictGroup[nd]=schedulingLoneIndex;
            loneLayerLatency.append(  layerIpLatencyTable_ILP[nd] )
            schedulingLoneIndex+=1;
        else:
            nodeListDict[nd.name]=nd;
            tempDictGroup[nd]=schedulingIndex;
            layerArray.append(nd);
            layerTypeArray.append(nd.layerInfo.layerType);
            latencyPerIPTable.append(  layerIpLatencyTable_ILP[nd] )
            schedulingIndex+=1;

    depsTable=[]
    loneLayerDepsTable=[]
    for edge in h.edges():
        s,t=edge
        if s.name in loneLayerSet:
            loneLayerDepsTable.append( (tempDictGroup[s],tempDictGroup[t]) );
        else:
            depsTable.append( (tempDictGroup[s],tempDictGroup[t]) );
    
    noStreamTable=[]
    for pair in noStreamEdgeSet :
        sName,tName = pair
        if sName in nodeListDict and tName in nodeListDict:
            s=nodeListDict[sName];
            t=nodeListDict[tName];
            noStreamTable.append( (tempDictGroup[s],tempDictGroup[t]));
            depsTable.append( (tempDictGroup[s],tempDictGroup[t]) );
         
    convNums=len(IP_dict["Convolution"])
    if "Pooling" in  IP_dict:
        PoolNums=len(IP_dict["Pooling"])
    else:
        PoolNums=0;
    if "Eltwise" in  IP_dict:
        EleNums=len(IP_dict["Eltwise"]) 
    else:
        EleNums=0;
    return  depsTable,loneLayerDepsTable, loneLayerArray,loneLayerLatency, noStreamTable,layerTypeArray,layerArray,latencyPerIPTable,convNums,PoolNums,EleNums
def genipIdxDict_IP(IPlist,ipIdxDict_IP):
    for ipIdx,IP in enumerate(IPlist):
        print "IP",IP
        ipIdxDict_IP[IP]=ipIdx;
    return ipIdxDict_IP;

def genIPInfoList(IPlist,IPinfoLIst):
    for ipIdx,IP in enumerate(IPlist):
        IPinfo= IP.IPinfo
        IPinfoLIst.append(IPinfo)

def genRoundInfo(roundMapping, ipIdxDict_IP, gs ):

    roundNodeList=[] 

    ipIdxDict_Layer={}



    for ipMapping in roundMapping:
        dummy,layerVertex,IPinst= ipMapping
        roundNodeList.append(layerVertex); 
        ipIdxDict_Layer[layerVertex]= ipIdxDict_IP[IPinst];


    del roundMapping[:]

    roundSubGraph= gs.subgraph(roundNodeList)
    roundSubGraph=roundSubGraph.copy()

    roundSubGraphList=list(roundSubGraph.nodes())

    roundInfoList=[]


    while roundSubGraphList:
        idx=0
        while list(roundSubGraph.predecessors(roundSubGraphList[idx])):  
            idx+=1 # find one node without predecessor
        currentNode=roundSubGraphList[idx];
        nextList=list(roundSubGraph.successors(currentNode) );
        prevIdx=None;
        currentIdx=None;
        nextIdx=None;

        while  nextList:
            assert( len( nextList)==1);

            nextNode=nextList[0];
            currentIdx=ipIdxDict_Layer[currentNode];
            nextIdx=ipIdxDict_Layer[nextNode]
            
            runInfo = runInfo_t(currentNode.layerInfo, currentIdx, nextIdx, prevIdx)
            runInfo.layerInfo.clearUnCertainItems()
            roundMapping.append( (currentNode,currentIdx)  )


            if runInfo.layerInfo.layerType == "Convolution" or runInfo.layerType == "Pooling":
                runInfo.layerInfo.memIn=False if prevIdx!=None else 1;
            elif runInfo.layerInfo.layerType == "Eltwise":
                runInfo.layerInfo.memInR=False if prevIdx!=None else 1;
            runInfo.layerInfo.memOut=False

                
            roundInfoList.append(runInfo);
            roundSubGraph.remove_node(currentNode);
            

            prevIdx=currentIdx;
            currentNode=nextNode;
            nextList=list(roundSubGraph.successors(currentNode) );
        
        currentIdx=ipIdxDict_Layer[currentNode];
        nextIdx=None
        runInfo=runInfo_t(currentNode.layerInfo, currentIdx, nextIdx, prevIdx);
        roundInfoList.append(runInfo);
        roundSubGraph.remove_node(currentNode);
        roundMapping.append((currentNode,currentIdx) )
        roundSubGraphList=list(roundSubGraph.nodes())
    return roundInfoList

def genRowILPInput(groupMappingSolution, IPlist, groupRunInfoList, IPinfoLIst, graph):
    
    ipIdxDict_IP={}
    genipIdxDict_IP(IPlist,ipIdxDict_IP)
    for g,solutionPool in groupMappingSolution.items():
        solutionList=[]
        for s,solution in enumerate(solutionPool):
            roundList=[]
            for Round in solution:
                roudRunInfoList=genRoundInfo( Round,ipIdxDict_IP,graph);
                roundList.append(roudRunInfoList)
            solutionList.append(roundList);
        groupRunInfoList.append(solutionList)
    genIPInfoList(IPlist,IPinfoLIst)
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

        IPList_total=[]
        firstFlag=1
        while(1):
            numConvIPs += 1
            if(manualSetingConvIPbound):
                if numConvIPs > convIPUb:
                    break
            numIPs = numConvIPs + numOtherIPs
            print "\n\nNumber of Convolution IP is ", numConvIPs, "\n\n"
            
            if( firstFlag):
                gs = graph(app_fileName, explore_IP_types, hw_layers)
                firstFlag=0
            
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
            final_graph_list=[]

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

            depositIPlist=[]
            for IPs in allIPs:
                nums += 1
                tmp = ""
                for ip in IPs:
                    tmp += ip.name + " "
                # print str(nums), "iteration", " selected IPs: ", tmp
                
                numConvs = 0
                for ip in IPs:
                    numConvs += (ip.type == "Convolution" or ip.type == "Convolution_g")
                if numConvs != numConvIPs:
                    # print "The number of convolution IPs is not correct"
                    continue

                #if the selected set of IPs are subset of the abandoned set, continue
                if self.isInAbandonTable(IPs):
                    # print "IPs in abandonTable"
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

                layerIPLatencyTable,layerIpLatencyTable_ILP = computeIPLatencyPerLayer(IP_dict, gs.exploreLayerQueue, hw_layers)

                valid = True
                lat_left = lat_achieved
                layerQueue = []
                mapping_solution_tmp = dict()
                latency_solution_tmp = dict()
                pipelineTable_tmp = dict()
                depositPipelineTable_solution = dict()
      
                for gIdx,g in enumerate(gs.graphs):
                    # print "Generating ILP input"

                    [depsTable,
                    loneLayerDepsTable, 
                    loneLayerArray,
                    loneLayerLatency, 
                    noStreamTable,
                    layerTypeArray,
                    layerArray,
                    latencyPerIPTable,
                    convNums,
                    PoolNums,
                    EleNums]=generateILPInput(g,layerIpLatencyTable_ILP,IP_dict,gs.noStreamEdge,gs.loneLayer)

                    roundMappingCandidates2,roundDictCandidates2,latCandidates2=RawILP.roundScheduling(
                    depsTable, 
                    noStreamTable,
                    loneLayerDepsTable,
                    loneLayerArray,
                    loneLayerLatency, 
                    layerTypeArray,
                    layerArray,
                    latencyPerIPTable, 
                    convNums,
                    PoolNums,
                    EleNums,
                    len(layerTypeArray));

                    if loneLayerLatency:
                        loneLayerLatency=loneLayerLatency[0][0][1];
                        loneLayerLatencyDeps=loneLayerDepsTable[0][1];
                    else:
                        loneLayerLatency=0;
                        loneLayerLatencyDeps=0;
                        
                    
                    roundMappingCandidates,roundDictCandidates,latCandidates=TestCase.computeOptimalLatencyDSP(
                        depsTable, 
                        noStreamTable,
                        loneLayerLatency,
                        loneLayerLatencyDeps,
                        layerTypeArray,
                        layerArray,
                        latencyPerIPTable, 
                        convNums,
                        PoolNums,
                        EleNums,
                        len(layerTypeArray)
                    );
                    print "Brutal FOrce",latCandidates2,lat_achieved

                    for i in roundMappingCandidates2:
                        for j in i:
                            print j;
                        print ""
                    
                    print "ILP",latCandidates,lat_achieved

                    for i in roundMappingCandidates:
                        for j in i:
                            print j;
                        print ""
 

                    # pipelineCandidates=[]
                    # for roundDict in roundDictCandidates:
                    #     pipelineTable2={}
                    #     for i in depsTable:
                    #         s,t = i;
                    #         if( roundDict[s]==roundDict[t] ):
                    #             pipelineTable2[(layerArray[s],layerArray[t])]=1;
                    #     pipelineCandidates.append(pipelineTable2)
                            
                    print "latCandidates",latCandidates
                    if not latCandidates :
                        valid = False
                        break                 
                    acc_lat += min(latCandidates)

                    
                    #If the current latency is worse than the achieved latency, then the current selection of IPs won't work
                    
                    if acc_lat > lat_achieved:
                        valid = False
                        break
                    lat_left = lat_achieved - acc_lat
                    mapping_solution_tmp[gIdx] = roundMappingCandidates
                    latency_solution_tmp[gIdx] = latCandidates
                   
                if not valid:
                    print "cannot find valid latency, continue"
                    continue
                lat_achieved = acc_lat
                depositIPlist=list(IPs);
                for k,v in mapping_solution_tmp.items():
                    mapping_solution[k] = v;

                for k,v in latency_solution_tmp.items():
                    latency_solution[k] = v

                for k,v in pipelineTable_tmp.items():
                    pipelineTable_solution[k] = v

            if not mapping_solution:
                continue
  
            groupRunInfoList=[]; IPinfoList=[];

           
            genRowILPInput(mapping_solution,depositIPlist,groupRunInfoList,IPinfoList,gs.G);

            # print "mapping_solution"

            # for k,v in mapping_solution.items():
            #     print "Group IDX", k
            #     print ""
               
            #     for i in v:
            #         print "solution"
            #         for j in i:
            #             print j;
            #         print ""
            
            solutionChoice,lat_rowStepILP=validateILP2.exploitK_xPCombinationsValidation(groupRunInfoList,IPinfoList,BRAM_budget)
            print "lat_rowStepILP",lat_rowStepILP

            # 1. deposit mapping_total= genMappingTotal( solutionChoice, MappingChoice )
            # 2. deposit 

            if lat_rowStepILP !=None and lat_rowStepILP < lat_achieved_total:
                lat_achieved_total = lat_rowStepILP
                solutionChoice_total = solutionChoice
                mapping_solution_total=mapping_solution
                groupRunInfoList_total=groupRunInfoList
                IPList_total = depositIPlist
                numConvIPs_total = numConvIPs
                numIPs_total = numIPs
            


        if not mapping_solution_total:
            print "No feasible solutions"
            return


        #gen final_graph
        # print groupRunInfoList_total
        # for k,v in mapping_solution_total.items():
        #     print v

        for groupIdx,choice in enumerate(solutionChoice_total):
            chosenIdx,rowStepList=choice
            solution=mapping_solution_total[groupIdx][chosenIdx]
            mapping_solution_total[groupIdx]=solution
            for RoundIdx,Round in enumerate(solution): 
                rowStep=rowStepList[RoundIdx]

                for layeridx,layer in enumerate(Round):
                    layerVertex=layer[0]
                    layerIPidx=layer[1]
                    layerVertex.mappedIP=IPList_total[layerIPidx];
                    layerVertex.layerInfo=groupRunInfoList_total[groupIdx][chosenIdx][RoundIdx][layeridx]
                    layerVertex.layerInfo.rowStep=rowStep;
                


    
        
        
        final_graph_list = []

        for gIdx,g in enumerate(gs.graphs):
            for r in mapping_solution_total[gIdx]:
                nodes=[]
                print "ROund:",
                for layer in r:
                    nodes.append(layer[0]) 
                    print layer[0],
                print ""
                subg =  gs.G.subgraph(nodes) 
                final_graph_list.append(subg)
        
        self.codeGen(final_graph_list, lat_achieved_total, hw_layers, numConvIPs_total, numIPs_total, int(batchSize))
        
        return lat_achieved_total

    # def genRoundInfo(self, graph, roundMappingList, IPInfoList):
    #     roundSubGraph=[]
    #     for node in r

 

    


        

    def genIPinfoLayerInfoList(self, final_graph_list, pipelineTable_solution_total):
        IPinfoDict = dict() #key: The IP name, value: IP info
        IPinfoList = [] #the list of IP info
        layerIPDict = dict() #Key: layer name, value: mapped IP info
        #Generate IPinfoList

        print "roundLayerInfo"
        for g in final_graph_list:
            for n in g.nodes():
                IPinfoDict[n.mappedIP.name] = n.mappedIP.IPinfo
                print n.name, n.mappedIP.name,
            print ""
        idx = 0
        for n in IPinfoDict:
            IPinfoDict[n].IPidx = idx
            IPinfoList.append(IPinfoDict[n])
            idx += 1

        for g in final_graph_list:
            for n in g.nodes():
                n.mappedIP.IPinfo = IPinfoDict[n.mappedIP.name]
                layerIPDict[n.name] = n.mappedIP.IPinfo.IPidx

        #generate roundInfoList
        pipelineTargetNodes = dict()
        pipelineSourceNodes = dict()
        for (s, t) in pipelineTable_solution_total:
            pipelineSourceNodes[t] = s
            pipelineTargetNodes[s] = t
        roundInfoList = []
     
        for g in final_graph_list:
            roundInfoList_row = []
            for n in g.nodes():
                if n.name in pipelineTargetNodes: #Then it is starting of a pipeline
                    nextIPidx = layerIPDict[pipelineTargetNodes[n.name]]
                else:
                    nextIPidx = None
                if n.name in pipelineSourceNodes:
                    prevIPidx = layerIPDict[pipelineSourceNodes[n.name]]
                else:
                    prevIPidx = None
                    
                n.mappedIP.IPinfo = IPinfoDict[n.mappedIP.name]
                runInfo = runInfo_t(n.layerInfo, n.mappedIP.IPinfo.IPidx, 
                        nextIPidx, prevIPidx)
                roundInfoList_row.append(runInfo)
            roundInfoList.append(roundInfoList_row)
        return roundInfoList, IPinfoList

#    def codeGen(self, lat_achieved, latency_solution, mapping_solution, hw_layers, gs, batchSize, numConvIPs, numIPs):
    def codeGen(self,final_graph_list, lat_achieved, hw_layers,  numConvIPs, numIPs, batchSize):
        print "\n\n #####################################################################"
        print "Final latency_achieved", lat_achieved, "number of IPs are ", numIPs, "number of convIPs are ", numConvIPs


        outHwDir = "./outputFiles/hw"
        outSwDir = "./outputFiles/sw"
        os.system("mkdir -p " + outHwDir)
        os.system("mkdir -p " + outSwDir)


        IP_g = createIPGraph(final_graph_list, hw_layers)
        expandGraph(IP_g)
        muxSelTable = assignMuxSelTable(IP_g)
        assignStreamPorts(IP_g, 2)
        genTop(IP_g, outHwDir, batchSize)
        #Gen CSV
        genCSVConfigs(final_graph_list, IP_g, muxSelTable, hw_layers, outHwDir)

        #GenFindBestRowStep
        newPipeInfoFile = outHwDir+"/pipeInfo.csv"
        newRowStepFile = outHwDir + "/rowStep.csv"

        #rowStepGen
        genRowStepFile(final_graph_list, outHwDir) 

        #Gen Scheduler
        functionArgs = readFunctionArgs(outHwDir)
        genSchedulerFile(functionArgs, outSwDir)
        genXkernelH(functionArgs, outSwDir)
        genXkernelCPP(functionArgs, outSwDir)
        copyUtilsCSV(outSwDir)
        
#return converged


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
    graph_list = []
    for g in mapping_solution:
        for n in list(g.nodes):
            if n.type not in hw_layers:
                g.remove_node(n)

    assignOriginalNodeMapping(mapping_solution, hw_layers)
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
