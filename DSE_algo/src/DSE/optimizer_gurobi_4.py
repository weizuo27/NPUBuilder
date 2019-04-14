from resourceILPBuilder_gurobi_4 import resourceILPBuilder
from vertex import layer
from graph_5 import graph
from graph_5 import pipeNode
from utils_4 import *
from copy import deepcopy
import networkx as nx
from scheduler_4 import scheduler

class optimizer:
    def __init__(self, latency_Budget, rowStep):
        self.rb = resourceILPBuilder()
        self.scheduler = scheduler()
        
        self.latency_lb = 0
        self.latency_ub = latency_Budget
        self.new_latency_target = latency_Budget
        self.latency_achieved = None
        self.mapping_solution = None
        self.pipelineTable_ret = None

        self.latency_table = dict()
        self.numIPs=dict()
        self.pipelineTable = dict()

    def run(self,IP_table, graphs, g,  hw_layers, explore_IP_types, numIPs, layerIPLatencyTable, ESP, IP_table_org, verbose = False):
        for ip_type in IP_table:
            self.numIPs[ip_type] = len(IP_table[ip_type])
        firstIter = True
        oneIter = 0
        latency_target_changed = True
        while(-self.latency_lb + self.latency_ub > ESP):
            assert(oneIter < 30000), "Should not iterate more than 30000 times, Something is wrong"
            if(verbose):
                print oneIter, "iteration\n"
                print "Latency target changed? ", latency_target_changed 
            if(latency_target_changed):
                #reset the latency target change flag
                latency_target_changed = False
                self.rb.constraints = []
                self.rb.violation_constraints_table.clear()
                self.rb.status = "Undecided"
                status = self.rb.createVs(IP_table,  graphs.exploreLayerQueue[g], hw_layers, self.new_latency_target, verbose)
                status = self.rb.createConstraints(IP_table, graphs.exploreLayerQueue[g], self.numIPs, verbose)
                if(verbose):
                    print self.rb.status, self.rb.status != "Failed"
                if self.rb.status != "Failed":
                    #re-add in the violation constraints, if we know they already cannot be the answer
                    for lat in self.latency_table:
                        if lat > self.new_latency_target:
                            for violation_path in self.latency_table[lat]:
                                if(verbose):
                                    printViolationPath(violation_path)
                                self.rb.addViolationPaths(violation_path, graphs.exploreLayerQueue[g], IP_table, layerIPLatencyTable, verbose)
                    #re create the problem
                    self.rb.createProblem(verbose) 
            self.rb.solveProblem(verbose)
            if(self.rb.status != "Optimal"):
                if firstIter:
                    if(verbose):
                        print "The resource budget is too tight, no feasible mapping solution."
                    return self.latency_achieved, self.mapping_solution, self.pipelineTable_ret
                if(verbose):
                    print "cannot find a solution under the current latency budget: ", self.new_latency_target, \
                    "lossen the target"

                self.latency_lb = self.new_latency_target
                self.new_latency_target = (self.latency_lb + self.latency_ub)/2 
                latency_target_changed = True
                if(verbose):
                    print "new_ub", self.latency_ub, "new_lb", self.latency_lb, "new target,", self.new_latency_target
                firstIter = False
                oneIter += 1
                continue

            firstIter = False
            #assign the mapping result
            self.assignMappingResult(graphs.exploreLayerQueue[g], explore_IP_types, hw_layers, IP_table, g, IP_table_org)
            self.pipelineTable.clear()
            self.setPipelineFlag(hw_layers, g)
            graphs.computeLatency(g)
            self.addPipelineNodes(g)
            status, ret = self.scheduling(g, explore_IP_types)
            if status == "Success":
                self.latency_ub = ret
                self.latency_achieved = ret
                self.mapping_solution = deepcopy(g)
                print "pipelineTable", self.pipelineTable
                self.pipelineTable_ret = deepcopy(self.pipelineTable)
                self.new_latency_target = (self.latency_ub + self.latency_lb) /2 
                latency_target_changed = True
                if(verbose):
                    print "scheduling", status
                    print "new_ub", self.latency_ub, "new_lb", self.latency_lb, "new target,", self.new_latency_target
            else: #Failed
                if verbose:
                    print "scheduling", status
                    printViolationPath(ret[0])
                self.rb.addViolationPaths(ret[0], graphs.exploreLayerQueue[g], IP_table, layerIPLatencyTable, verbose)

            graphs.retriveOriginalGraph(g)
            oneIter += 1
        if self.latency_achieved == None:
            if(verbose):
                print "The latency budget is too small, cannot find any feasible solution."
            return self.latency_achieved, self.mapping_solution, self.pipelineTable_ret
        else:
            if(verbose):
                print "Final solution"
                self.printSchedulingMappingSol(graphs, hw_layers)
#            for n in self.mapping_solution.node():
#                print n.layerInfo
            return self.latency_achieved, self.mapping_solution, self.pipelineTable

    def assignMappingResult(self, exploreLayerQueue, explore_IP_types, hw_layers, IP_table, g, IP_table_org):
        for layer_type in self.rb.mappingVariables:
            variables = self.rb.mappingVariables[layer_type]
            for layer_idx in range(len(variables)):
                node = exploreLayerQueue[layer_type][layer_idx]
                for ip_idx in range(len(variables[layer_idx])):
                    if (hasattr(variables[layer_idx][ip_idx], "X") and variables[layer_idx][ip_idx].X> 0.5 ): 
                        node.set_IP(IP_table[layer_type][ip_idx])
        idx = 0
        for n in g.nodes():
            if n.type not in explore_IP_types and n.type in hw_layers:
                n.set_IP(deepcopy(IP_table_org[n.type][0]))
                n.mappedIP.name = n.mappedIP.name+"_" + str(idx)
                idx += 1

    def setPipelineFlag(self, hw_layers, g):
        visited = dict()
        nodes = list(nx.topological_sort(g))
        for path in nx.all_simple_paths(g, source=nodes[0], target = nodes[-1]):
            pipelineTable = dict()
            idx = 1
            if(path[0].type in hw_layers):
                pipelineTable[path[0].mappedIP.name] = 1
            for t in path[idx:]:
                s = path[idx-1]
                idx += 1
                if (s, t) not in visited:
                    visited[(s,t)] = 1
                    if t.type not in hw_layers:
                        pipelineTable.clear()
                    elif s.type not in hw_layers:
                        pipelineTable.clear()
                        pipelineTable[t.mappedIP.name] = 1
                    elif t.mappedIP not in pipelineTable:
                        self.pipelineTable[(s,t)] = 1
                        pipelineTable[t.mappedIP.name] = 1
                    else:
                        pipelineTable.clear()
                        pipelineTable[t.mappedIP.name] = 1

    def addPipelineNodes(self, g):
#        print "self.pipelineTable"
#        for (s, t) in self.pipelineTable:
#            print s.name, s.ID, "+", t.name, t.ID
        for s_node, t_node in self.pipelineTable:
            s_node.layerInfo.memOut = False
            if(t_node.type == "Eltwise"):
                t_node.layerInfo.memInR == False
            else:
                t_node.layerInfo.memIn = False
            n = pipeNode(-s_node.latency)
            g.remove_edge(s_node, t_node)
            g.add_node(n)
            g.add_edge(s_node, n)
            g.add_edge(n, t_node);

    def scheduling(self, g, explore_IP_types):
        def compFoo(elem):
            return 0-elem[0].latency

        cp_path = []
        accLat = 0
        path = self.scheduler.scheduling(g, explore_IP_types)
        for p in path:
            accLat += p.latency
            if p.type == "combineNode":
                for mm in p.node_list:
                    if mm.type in explore_IP_types:
                        cp_path.append((mm, mm.mappedIP))

            elif p.type not in explore_IP_types:
                None
            else:
                cp_path.append((p, p.mappedIP))

            if accLat >= self.new_latency_target:
                if accLat in self.latency_table: 
                    self.latency_table[accLat].append(cp_path)
                else:
                    self.latency_table[accLat] = [cp_path]
#                print self.latency_table
                return "Failed", [cp_path, accLat]

        if accLat in self.latency_table: 
            self.latency_table[accLat].append(cp_path)
        else:
            self.latency_table[accLat] = [cp_path]

        return "Success", accLat
    
    def printSchedulingMappingSol(self, graphs, hw_layers):
        graphs.printNodesMapping(hw_layers, self.mapping_solution)
        print "achieved latency", self.latency_achieved

    def updateGraph(self, g, hw_layers ):
        def comp12(n):
            return int(n.ID)

        IPMappingTable = dict()

        for n in g.nodes():
            if not isinstance(n, layer):
                continue
#            print "abcddd", n.name, n.mappedIP
            if n.mappedIP.type not in hw_layers:
                continue
#            print "abcdd", n.name, n.mappedIP
            if n.mappedIP not in IPMappingTable:
                IPMappingTable[n.mappedIP] = [n]
            else:
                IPMappingTable[n.mappedIP].append(n)

        for ip in IPMappingTable:
            IPMappingTable[ip].sort(key = comp12)

        for ip in IPMappingTable:
            for idx in range(len(IPMappingTable[ip])-1):
                g.add_edge(IPMappingTable[ip][idx], IPMappingTable[ip][idx+1])

    def setRowStep(self, exploreLayerQueue, rowStepTable=None):
        for ntype in exploreLayerQueue:
            for n in exploreLayerQueue[ntype]:
                n.setRowStep(rowStepTable)

    def addBackRemovedEdges(self, edges, g):
        for u,v in edges:
            if(g.has_node(u) and g.has_node(v)):
                g.add_edge(u,v)
