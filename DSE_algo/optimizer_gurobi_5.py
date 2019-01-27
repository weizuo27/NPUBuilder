from resourceILPBuilder_gurobi_5 import resourceILPBuilder
from itertools import izip_longest
from graph_3 import graph
from graph_3 import pipeNode
from graph_3 import combineNode
from utils_2 import *
from copy import deepcopy
import networkx as nx
from scheduler import scheduler

class optimizer:
    def __init__(self, BRAM_budget, DSP_budget, FF_budget, LUT_budget, 
            BW_budget, latency_Budget, app_fileName, IP_fileName, pipelineLength,
            ESP, DSE, assumptionLevel, rowStep):

        self.mapping_solution = None
        self.rowStep = rowStep

        #Hard code the hardware supported layers
        self.hw_layers = {
            "Convolution": 1,
            "Convolution_g": 1,
            "Pooling" : 1
        }

        #Hard code the IP types we would like to explore
        self.explore_IP_types = {
            "Convolution": 1,
            "Convolution_g" : 1
        }

        self.g = graph(app_fileName, self.explore_IP_types, self.rowStep)
        

        IPs = generateIPs(IP_fileName)

        self.IP_table = constructIPTable(IPs, BRAM_budget, DSP_budget, LUT_budget, \
            FF_budget, BW_budget, self.g.exploreLayerQueue, self.explore_IP_types, pipelineLength)
        
        IP_table_per_layer = genIPTablePerLayer(self.IP_table, self.g.exploreLayerQueue, self.hw_layers)

        layerIPLatencyTable = computeIPLatencyPerLayer(self.IP_table, self.g.exploreLayerQueue, self.hw_layers, IP_table_per_layer)

        self.rb = resourceILPBuilder(BRAM_budget, DSP_budget, FF_budget, LUT_budget, BW_budget)

        if(not DSE):
            print "Running heuristic"
            #FIXME: fill in
            return

        self.rb = resourceILPBuilder(BRAM_budget, DSP_budget, FF_budget, LUT_budget, BW_budget)
        self.scheduler = scheduler()
        
        #1. Initalize the variables
        self.latency_lb = 0
        self.latency_ub = latency_Budget
        self.new_latency_target = latency_Budget
        self.latency_achieved = None
        self.resource_achieved = None

        #2. Loop body
        firstIter = True
        oneIter = 0
        self.latency_table = dict()
        latency_target_changed = True
        while(-self.latency_lb + self.latency_ub > ESP):
            print oneIter, "iteration\n"
            print "Latency target changed? ", latency_target_changed 
            if(latency_target_changed):
                self.rb.constraints = []
                self.rb.violation_constraints_table.clear()
                self.rb.status = "Undecided"
                status = self.rb.createVs(self.IP_table, IP_table_per_layer, self.g.exploreLayerQueue, self.hw_layers, self.new_latency_target, self.explore_IP_types)
                status = self.rb.createConstraints(self.IP_table, self.g.exploreLayerQueue, pipelineLength, assumptionLevel, self.explore_IP_types)
                #re-add in the violation constraints, if we know they already cannot be the answer
                for lat in self.latency_table:
                    if lat > self.new_latency_target:
                        for violation_path in self.latency_table[lat]:
                            self.rb.addViolationPaths(violation_path, self.g.exploreLayerQueue, self.IP_table, layerIPLatencyTable, assumptionLevel, (lat - self.new_latency_target)/len(violation_path))
                #re create the problem
                self.rb.createProblem(pipelineLength, assumptionLevel) 
                #reset the latency target change flag
                latency_target_changed = False

            self.rb.solveProblem()

            if(self.rb.status != "Optimal"):
                assert (not firstIter), "The resource budget is too tight, no feasible mapping solution."
                print "cannot find a solution under the current latency budget: ", self.new_latency_target, \
                    "lossen the target"
                self.latency_lb = self.new_latency_target
                self.new_latency_target = (self.latency_lb + self.latency_ub)/2 
                latency_target_changed = True
                print "new_ub", self.latency_ub, "new_lb", self.latency_lb, "new target,", self.new_latency_target
                firstIter = False
                oneIter += 1
                continue

            firstIter = False
            #get the resource consumption after the ILP
            self.resourceTable = self.rb.getResourceTable()
            #assign the mapping result
            self.assignMappingResult()
            self.setPipelineFlag()
            self.g.computeLatency()
            self.g.printNodesMapping(self.hw_layers)
            self.addPipelineNodes()
            self.simplifyGraph()
#            self.g.drawGraph()
            #scheduling
            status, ret = self.scheduling()
            
            if status == "Success":
                self.latency_ub = ret
                self.latency_achieved = ret
                self.resource_achieved = self.resourceTable
                self.mapping_solution = deepcopy(self.g)
                self.new_latency_target = (self.latency_ub + self.latency_lb) /2 
                latency_target_changed = True
                print "scheduling", status
                print "new_ub", self.latency_ub, "new_lb", self.latency_lb, "new target,", self.new_latency_target
            else: #Failed
                print "scheduling", status
                printViolationPath(ret[0])
                self.rb.addViolationPaths(ret[0], self.g.exploreLayerQueue, self.IP_table, layerIPLatencyTable, assumptionLevel, (ret[1]-self.new_latency_target)/len(ret[0]))
            self.g.retriveOriginalGraph()
            oneIter += 1
        if self.latency_achieved == None:
            print "The latency budget is too small, cannot find any feasible solution."
        else:
            print "Final solution"
            self.printSchedulingMappingSol()

    def printSchedulingMappingSol(self):
        self.mapping_solution.printNodesMapping(self.hw_layers)
        print "achieved latency", self.latency_achieved
        print "ahcieved resource (BRAM, LUT, FF, LUT)", self.resource_achieved
            
    def assignMappingResult(self):
        for layer_type in self.rb.mappingVariables:
            variables = self.rb.mappingVariables[layer_type]
            for layer_idx in range(len(variables)):
                for ip_idx in range(len(variables[layer_idx])):
                    if (hasattr(variables[layer_idx][ip_idx], "X") and variables[layer_idx][ip_idx].X> 0.5 ): 
                        for g in self.g.graphs:
                            if g in self.g.exploreLayerQueue:
                                if layer_idx < len(self.g.exploreLayerQueue[g][layer_type]):
                                    node = self.g.exploreLayerQueue[g][layer_type][layer_idx]
                                    node.set_IP(self.IP_table[layer_type][ip_idx])

            for n in self.g.G.nodes:
                idx = 0;
                if n.type not in self.explore_IP_types and n.type in self.hw_layers:
                    n.set_IP(deepcopy(self.IP_table[n.type][idx]))
                    idx += 1

    def setPipelineFlag(self):
        visited = dict()
        for g in self.g.graphs:
            nodes = list(nx.topological_sort(g))
            for path in nx.all_simple_paths(g, source=nodes[0], target = nodes[-1]):
                pipelineTable = dict()
                for m in path:
                    if m not in visited:
                        visited[m] = 1
                        preds = list(g.predecessors(m))
                        numPreds = len(preds)
                        numSuccs = len(list(g.successors(m)))
                        if m.type not in self.hw_layers:
#                            print m.name, m.type, "not in hw_layers"
                            m.Pipelined = False
                            pipelineTable.clear()
                        elif numPreds > 1 or numSuccs > 1:
#                            print m.name, m.type, numPreds, numSuccs, "Preds or Succs > 1"
                            m.Pipelined = False
                            pipelineTable.clear()
                            pipelineTable[m.mappedIP] = 1
                        elif preds[0].type not in self.hw_layers:
#                            print m.name, m.type, preds[0].name, "pred not in hw_layers"
                            m.Pipelined = False
                            pipelineTable.clear()
                            pipelineTable[m.mappedIP] = 1
                        elif m.mappedIP not in pipelineTable:
#                            print m.name, m.type, "Pipelined "
                            m.Pipelined = True
                            pipelineTable[m.mappedIP] = 1
                        else:
#                            print m.name, m.type, "in the pipelineTable"
                            m.Pipelined = False
                            pipelineTable.clear()
                            pipelineTable[m.mappedIP] = 1

    def addPipelineNodes(self):
        pipeNode_list = []
        for g in self.g.graphs:
            for (s_node, t_node) in g.edges():
                if not isPipelined(s_node, t_node):
                    continue
                neg_latency = 0
                s_latency = 0
                t_latency_rowStep = 0
                s_latency = s_node.latency

                if t_node.type == "Convolution"or t_node.type == "Convolution_g":
                    _, _, _, t_kh = map(int, (t_node.params[0].split("=")[1]).split("x"))
                    S = int(t_node.params[1].split("=")[1])

                elif t_node.type == "Pooling":
                    kw = t_kh = int(t_node.params[2].split("=")[1])
                    S = int(t_node.params[3].split("=")[1])

                elif t_node.type == "Eltwise":
                    t_kh = 1
                    S = 1

                t_latency_rowStep = s_node.computeNRows(t_kh)
                neg_latency = -s_latency + t_latency_rowStep
                if(neg_latency < 0):
                    node = pipeNode(neg_latency)
                    pipeNode_list.append([g, node, s_node, t_node])
#                print "s_latency, t_latency_one_row", s_latency, t_latency_one_row, t_node.name, t_node.type, t_latency_one_row, s_node.name, s_node.type, t_node.Pipelined, node.latency

        for g, node, s_node, t_node in pipeNode_list:
            g.remove_edge(s_node, t_node)
            g.add_node(node)
            g.add_edge(s_node, node)
            g.add_edge(node, t_node)

    def simplifyGraph(self):
        for g in self.g.graphs:
            end_n_table = dict()

            for n in nx.topological_sort(g):
                if n.type == "pipeNode":
                    pred_n = list(g.predecessors(n))[0]
                    succ_n = list(g.successors(n))[0]

                    # update the end_n_table
                    if pred_n in end_n_table:
                        end_n_table[pred_n] += [n, succ_n]
                        end_n_table[succ_n] = end_n_table.pop(pred_n)
                    else:
                        end_n_table[succ_n] = [pred_n, n, succ_n]

            #create the combineNode:
            for end_n in end_n_table:
                path = end_n_table[end_n]
                cb_node = combineNode(path)
                cb_node.computeLatency()
                g.add_node(cb_node)
                for pre in g.predecessors(path[0]):
                    g.add_edge(pre, cb_node)
                for succ in g.successors(path[-1]):
                    g.add_edge(cb_node, succ)
                g.remove_nodes_from(path)
            
#            for n in g.nodes:
#                print "aaa", n.name
#                assert n.type != "pipeNode", "There should be no pipeNode left"

    def scheduling(self):
        print "\nstart scheduling\n"
        def compFoo(elem):
            return 0-elem[0].latency

        cp_paths = []
        for g in self.g.graphs:
            cp_path = []
            path = self.scheduler.scheduling(g, self.explore_IP_types, self.g) 
            for p in path:
                cp_path.append((p, g))

            cp_path.sort(key = compFoo)
            cp_paths.append(cp_path)
        
#        print "in cp_path"
#        for n, g in cp_path:
#            print n.name, n.latency

        shuffled_cp_paths = [val for tup in izip_longest(*cp_paths) for val in tup if val is not None]

#        print "in shuffled_cp_paths"
#        for n, g in shuffled_cp_paths:
#            print n.name, n.latency

        acc_lat = 0
        acc_path = [] #each element (layer, graph, mappedIP)

        for n,g in shuffled_cp_paths:
            acc_lat += n.latency
            if n.type is "combineNode":
                for mm in n.node_list:
                    if mm.type not in self.explore_IP_types:
                        continue
                    acc_path.append((mm, g, mm.mappedIP))
            elif n.type in self.explore_IP_types:
                acc_path.append((n, g, n.mappedIP))

            if acc_lat not in self.latency_table:
                self.latency_table[acc_lat] = [acc_path]
            else:
                self.latency_table[acc_lat].append(acc_path)

            if acc_lat > self.new_latency_target:
                return "Failed", [acc_path, acc_lat]

        return "Success", acc_lat
