from resourceILPBuilder_gurobi_4 import resourceILPBuilder
from vertex import layer
from graph_5 import graph
from graph_5 import pipeNode
from graph_5 import combineNode
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

        self.latency_table = dict()
        self.numIPs=dict()

    def run(self,IP_table, graphs, g, IP_table_per_layer, hw_layers, explore_IP_types, numIPs, layerIPLatencyTable, ESP, IP_table_org, verbose = False):
        for ip_type in IP_table:
            self.numIPs[ip_type] = len(IP_table[ip_type])

        firstIter = True
        oneIter = 0
        latency_target_changed = True
        while(-self.latency_lb + self.latency_ub > ESP):
            assert(oneIter < 300), "Something is wrong"
                
            if(verbose):
                print oneIter, "iteration\n"
                print "Latency target changed? ", latency_target_changed 
            if(latency_target_changed):
                #reset the latency target change flag
                latency_target_changed = False
                self.rb.constraints = []
                self.rb.violation_constraints_table.clear()
                self.rb.status = "Undecided"
                status = self.rb.createVs(IP_table, IP_table_per_layer, graphs.exploreLayerQueue[g], hw_layers, self.new_latency_target, verbose)
                status = self.rb.createConstraints(IP_table, graphs.exploreLayerQueue[g], self.numIPs, verbose)
                if(verbose):
                    print self.rb.status, self.rb.status != "Failed"
                if self.rb.status != "Failed":
                    #re-add in the violation constraints, if we know they already cannot be the answer
                    for lat in self.latency_table:
                        if lat > self.new_latency_target:
                            for violation_path in self.latency_table[lat]:
#                                printViolationPath(violation_path)
                                self.rb.addViolationPaths(violation_path, graphs.exploreLayerQueue[g], IP_table, layerIPLatencyTable, verbose)
                    #re create the problem
                    self.rb.createProblem(verbose) 
            self.rb.solveProblem(verbose)
            if(self.rb.status != "Optimal"):
                if firstIter:
                    if(verbose):
                        print "The resource budget is too tight, no feasible mapping solution."
                    return self.latency_achieved, self.mapping_solution
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
#            self.updateGraph(g, hw_layers)
#            graphs.drawGraph(g)
            self.setPipelineFlag(hw_layers, g)
            self.setRowStep(graphs.exploreLayerQueue[g])
            graphs.computeLatency(g)
            self.addPipelineNodes(g)
#            self.simplifyGraph(g)

            status, ret = self.scheduling(g, explore_IP_types)

            if status == "Success":
                self.latency_ub = ret
                self.latency_achieved = ret
                self.mapping_solution = deepcopy(g)
                self.new_latency_target = (self.latency_ub + self.latency_lb) /2 
                latency_target_changed = True
                if(verbose):
                    print "scheduling", status
                    print "new_ub", self.latency_ub, "new_lb", self.latency_lb, "new target,", self.new_latency_target
            else: #Failed
#                print "scheduling", status
#                printViolationPath(ret[0])
                self.rb.addViolationPaths(ret[0], graphs.exploreLayerQueue[g], IP_table, layerIPLatencyTable, verbose)

            graphs.retriveOriginalGraph(g)
            oneIter += 1
        if self.latency_achieved == None:
            if(verbose):
                print "The latency budget is too small, cannot find any feasible solution."
            return self.latency_achieved, self.mapping_solution
        else:
            if(verbose):
                print "Final solution"
                self.printSchedulingMappingSol(graphs, hw_layers)
            return self.latency_achieved, self.mapping_solution

    def assignMappingResult(self, exploreLayerQueue, explore_IP_types, hw_layers, IP_table, g, IP_table_org):
        for layer_type in self.rb.mappingVariables:
            variables = self.rb.mappingVariables[layer_type]
            for layer_idx in range(len(variables)):
                node = exploreLayerQueue[layer_type][layer_idx]
                for ip_idx in range(len(variables[layer_idx])):
                    if (hasattr(variables[layer_idx][ip_idx], "X") and variables[layer_idx][ip_idx].X> 0.5 ): 
                        node.set_IP(IP_table[layer_type][ip_idx])
        idx = 0
        for n in g.nodes:
            if n.type not in explore_IP_types and n.type in hw_layers:
                n.set_IP(deepcopy(IP_table_org[n.type][0]))
                n.mappedIP.name = n.mappedIP.name+"_" + str(idx)
                idx += 1

    def setPipelineFlag(self, hw_layers, g):
        visited = dict()
        nodes = list(nx.topological_sort(g))
        for path in nx.all_simple_paths(g, source=nodes[0], target = nodes[-1]):
            pipelineTable = dict()
            for m in path:
                if m not in visited:
                    visited[m] = 1
                    preds = list(g.predecessors(m))
                    numPreds = len(preds)
                    numSuccs = len(list(g.successors(m)))
                    if m.type not in hw_layers:
#                            print m.name, m.type, "not in hw_layers"
                        m.Pipelined = False
                        pipelineTable.clear()
                    elif numPreds > 1 or numSuccs > 1:
#                            print m.name, m.type, numPreds, numSuccs, "Preds or Succs > 1"
                        m.Pipelined = False
                        pipelineTable.clear()
                        pipelineTable[m.mappedIP] = 1
                    elif preds[0].type not in hw_layers:
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

    def addPipelineNodes(self, g):
        pipeNode_list = []
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
#            print "s_node ", s_node.name, ", t_node ", t_node.name, ", neg_latency", neg_latency
            if(neg_latency < 0):
                node = pipeNode(neg_latency)
                pipeNode_list.append([node, s_node, t_node])

        for node, s_node, t_node in pipeNode_list:
            g.remove_edge(s_node, t_node)
            g.add_node(node)
            g.add_edge(s_node, node)
            g.add_edge(node, t_node)

    def simplifyGraph(self, g):
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

#        print "cp_path"
#        for l, ip in cp_path:
#            print l.name, ip.name
        if accLat in self.latency_table: 
            self.latency_table[accLat].append(cp_path)
        else:
            self.latency_table[accLat] = [cp_path]

        return "Success", accLat
    
    def printSchedulingMappingSol(self, graphs, hw_layers):
#        graphs.printNodesMapping(hw_layers, self.mapping_solution)
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

    def setRowStep(exploreLayerQueue):
        for ntype in exploreLayerQueue:
            for n in exploreLayerQueue[ntype]:
                n.setRowStep()
