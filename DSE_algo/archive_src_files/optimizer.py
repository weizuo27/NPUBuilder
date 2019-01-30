from resourceILPBuilder import resourceILPBuilder
from graph import graph
from graph import pipeNode
from utils import *
from copy import deepcopy
import itertools

class optimizer:
    def __init__(self, BRAM_budget, DSP_budget, FF_budget, LUT_budget, BW_budget, latency_Budget,
            app_fileName, IP_fileName, EPS):
        """
        The top function of the optimizer
        Args:
            BRAM_budget: The budget of BRAM given
            DSP_budget: The budget of DSP
            LUT_budget: The budget of LUT
            FF_budget: The budget of FF
            BW_budget: The budget of Bandwidth
            latency_Budget: the latency budget
            EPS: The margin of scheduling, the difference bound between upper and lower bound
            hw_layers:. The dictionary of the layers that are supported by hardware
            app_fileName: The graph description file from CHaiDNN
            IP_fileName: the file contains the IP candidates and charicterization data
            IP_table: The dictionary that stores the list of candidate IPs
                key: layer_type; value: The list of IPs of that type
            IPReuseTable: The dictionary to describe that for each IP, which layer(s) are using it
                key: IP; Value: The list of layers that use it, in the topological sorted order
            latency_table: Dictionary. Key: the latency, value: the list of violation paths that achieves the latency
        """
        #Hard code the hardware supported layers
        self.hw_layers = {
            "Convolution": 1,
            "Convolution_g": 1,
            "Pooling" : 1
        }
        self.g = graph(app_fileName) #generate the graph from CHaiDNN output
        IPs = generateIPs(IP_fileName)
        self.IP_table = constructIPTable(IPs, BRAM_budget, DSP_budget, LUT_budget, FF_budget, BW_budget)
        #IP_table_per_layer: The dictionary to record the IP can be used per layer.
        #   Key: The layer. Value: list of length IP_table[layer.type]. Each element is either 0 or 1.
        #   0 means that IP is not used for this layer, 1 otherwise.
        IP_table_per_layer = genIPTablePerLayer(self.IP_table, self.g.layerQueue, self.hw_layers)
        self.rb = resourceILPBuilder(BRAM_budget, DSP_budget, FF_budget, LUT_budget, BW_budget) #Builder resource solver


        # Now starting the loop
        #1. Initalize the variables
        self.latency_lb = 0
        self.latency_ub = latency_Budget
        self.new_latency_target = latency_Budget
        self.latency_achieved = None

        #solve the problem

        #2. Loop body
        firstIter = True
        oneIter = 0
        self.latency_table = dict()

        latency_target_changed = True
        #while(oneIter < 1): #For debugging purpose
        while(-self.latency_lb+self.latency_ub> EPS):
            print oneIter, "iteration\n"
            print "Latency target changed? ", latency_target_changed
            if(latency_target_changed):
                self.rb.constraints = []
                self.rb.violation_constraints = []
                self.rb.violation_constraints_table.clear()
                self.rb.status = "Undecided"
                status = self.rb.createVs(self.IP_table, IP_table_per_layer, self.g.layerQueue, self.hw_layers, self.new_latency_target)
                status = self.rb.createConstraints(self.IP_table, self.g.layerQueue)
                #re-add in the violation constraints
                #print "Re add the violation paths"
                for lat in self.latency_table:
                    if lat > self.new_latency_target:
                        for violation_path in self.latency_table[lat]:
                            self.rb.addViolationPaths(violation_path, self.g.layerQueue, self.IP_table)
                latency_target_changed = False
                    
            self.rb.createProblem()
            optimal = self.rb.solveProblem()
            if(not optimal):
                assert (not firstIter), "The resource budget is too tight, no feasible mapping solution."
                print "cannot find a solution under the current latency budget: ", self.new_latency_target, \
                    "lossen the target"
                self.latency_lb = self.new_latency_target
                #FIXME: The latency should be integer or floating point?
                self.new_latency_target = (self.latency_lb + self.latency_ub)/2 
                latency_target_changed = True
                print "new_ub", self.latency_ub, "new_lb", self.latency_lb, "new target,", self.new_latency_target
                firstIter = False
                oneIter += 1
                continue
            firstIter = False
            self.rb.printSolution()
            #assign the mapping result
            self.assignMappingResult()
            #Now update the latency since the IPs are assigned
            self.g.computeLatency()
            #add nodes to factor in pipeline
            self.addPipelineNodes()
            #self.g.drawGraph()
            self.g.printNodeLatency()
            #fill-in the IPReuseTable:
            #print(self.g)
            self.IPReuseTable = dict()
            self.constructIPReuseTable()
            #add the the edges to factor in the IP reuse
            self.addReuseEdges()
            #now update the violation path related ILP, resolve the ILP
            status, ret = self.scheduling(self.new_latency_target)
            if(status == "success"):
                self.latency_ub = ret
                self.latency_achieved = ret
                self.mapping_solution = deepcopy(self.g)
                self.new_latency_target = (self.latency_ub + self.latency_lb)/2
                latency_target_changed = True
                print "scheduling", status
                print "new_ub", self.latency_ub, "new_lb", self.latency_lb, "new target,", self.new_latency_target
            else: #Failed
                print "scheduling", status
                endTime, vioPath, vioLat = ret
                printViolationPath(vioPath)
                #update the latency_table
                if vioLat in self.latency_table:
                    self.latency_table[vioLat].append(vioPath)
                else:
                    self.latency_table[vioLat] = [vioPath]
                #However, if the new solution is better than the achieved solution, we still can 
                # update the ub and the achieved solution
                if endTime < self.latency_achieved:
                    self.latency_ub = endTime
                    self.latency_achieved = endTime
                    self.mapping_solution = deepcopy(self.g)
                self.updateResourceILPBuilder(vioPath)
            self.g.retriveOriginalGraph()
            oneIter += 1
        if self.latency_achieved == None:
            print "The latency budget is too small, cannot find any feasible solution"
        else:
            print "The achieved latency is ", self.latency_achieved
            print "mapping"
            print(self.mapping_solution)
        
    def constructIPReuseTable(self):
        """
        build the table(dictionary)
            key: The IP
            value: The number of layers that mapped to the IP
        """
        nodes_list = self.g.topological_sort()
        for node in nodes_list:
            if node.__class__.__name__ != "layer":
                 continue
            if node.mappedIP not in self.IPReuseTable:
               self.IPReuseTable[node.mappedIP] = []
            self.IPReuseTable[node.mappedIP].append(node)
        
    def addReuseEdges(self):
        """
        The function to add edges between two nodes if they map to the same IP
        """
        #Iterate through each pair that reuse one IP, then add edge
        #FIXME: Actually this may add redundant edges
        for IP in self.IPReuseTable:
            for (s, t) in itertools.combinations(self.IPReuseTable[IP], 2):
                self.g.G.add_edge(s,t)

    def addPipelineNodes(self):
        """
        The function to add pipelined node, if two layers can be pipelined.
        The idea is to insert a node with negative latency, so when do scheduling, 
        The pipelined effect can be factored in.
        """
        #cannot directly iterate on original edges, since need to modify the graph
        pipeNode_list = []
        for (s_node, t_node) in self.g.G.edges():
            if isPipelined(s_node, t_node):
            #if s_node.mappedIP != t_node.mappedIP and \
            #(s_node.mappedIP != "Software" and t_node.mappedIP != "Software"): #Two layers are pipelinable
                #The neg_latency is the difference between the source node finishes the whole layer
                #and when it generates enough data to compute one layer output of the target node 
                #,(which is the pipeline starting point of the target node)
                #print s_node.name, s_node.latency, s_node.pipelinedLatency

                #If it is the join node, the way to calculate the pipeline latency is different
                neg_latency = 0
                s_latency = 0
                t_latency_one_row = 0

#                if(s_node.type == "joinNode"): 
#                    for n in self.g.G.predecessors(s_node):
#                        s_latency = max(s_latency, n.latency)
#                else:
#print "s_node", s_node.name, s_node.latency
#                print "t_node", t_node.name, t_node.lat_one_row
                s_latency = s_node.latency

#                if(t_node.type == "sepNode"):
#                    for n in self.g.G.successors(t_node):
#                        t_latency_one_row = max(t_latency_one_row, n.lat_one_row)
#                else:
                t_latency_one_row = t_node.lat_one_row

                neg_latency = -s_latency + t_latency_one_row

                if(neg_latency < 0):
                    node = pipeNode(neg_latency)
                    pipeNode_list.append([node, s_node, t_node])

        for node, s_node, t_node in pipeNode_list:
            self.g.G.remove_edge(s_node, t_node)
            self.g.add_node(node)
            self.g.G.add_edge(s_node, node)
            self.g.G.add_edge(node, t_node)

    def assignMappingResult(self):
        """
        After resource mapping result come out, annotate them to the graph
        """
        for layer_type in self.rb.mappingVariables:
            variables = self.rb.mappingVariables[layer_type]
            for layer_idx in range(len(variables)):
                node = self.g.layerQueue[layer_type][layer_idx]
                for ip_idx in range(len(variables[layer_idx])):
                    #print layer_type, layer_idx, ip_idx, variables[layer_idx][ip_idx].value  #If the mapping result is True, then we set the mapping
                    if (hasattr(variables[layer_idx][ip_idx], 'value') and variables[layer_idx][ip_idx].value > 0.5 ): #If the mapping result is True, then we set the mapping
                        node.set_IP(self.IP_table[layer_type][ip_idx]) 

    def scheduling(self, latency_Budget):
        """
        ASAP scheduling for the graph. 
        First it applies topological sorting. Then started assigning
        the starting time according to the order. Along the way recording 
        the path.

        If at one node the overall latency exceeds the latency_Budget, then stop.
        Reverse chasing to find the shortest path that violates the constraints

        Args:
            latency_Budget: FP data, the latency budget 
        Return:
            1. status: The string to indicate a legal schedule can be found or not
            2.
            if fail, return the shortest violation path 
            if succeed, return the shortest latency
        """
        startingTime = dict() # The dictionary. Key: node. Value: Starting time stamp
        path = dict() # The dictionary, to record critical path to the node. Key: node. Value: list of nodes to represent the path
        noteList = list(self.g.topological_sort())
        status = "undecided"
        endtime = 0
        for n in noteList:
            max_starting = 0
            max_pred = None
            preds = list(self.g.G.predecessors(n))
            if len(preds) == 0:
                startingTime[n] = 0.0
                path[n] = [n]
            else:
                for pred in preds:
                    if max_starting < startingTime[pred] + pred.latency:
                        max_starting = startingTime[pred] + pred.latency
                        max_pred = pred
                startingTime[n] = max_starting
                path[n] = path[max_pred] + [n]
            #if at one node the overall latency exceeds the budget:
            #need to reverse the path to get the shortest path that 
            #violates the constraints
            # TODO: Currently just using linear, later can use binary search
            # TODO: Currently, once we detect a violation, we terminate, but 
            # a maybe better idea is to let it finish the scheduling and if it is
            # better than lower-bound, update the lower-bound and the achieved solution
            # such that this solution does not need to be travelled again (like DP).
            endtime = max(startingTime[n] + n.latency, endtime)
            #print "\nendtime", endtime, len(noteList), self.latency_achieved, "\n"
            if status == "undecided":
                if endtime > latency_Budget:
                    violation_path = [n]
                    if n.latency > latency_Budget:
                        status = "failed"
                        violate_latency = n.latency
                    else:
                        for m in path[n][-2::-1]:
                            if m.type == "pipeNode":
                                continue
                            violation_path += [m]
                            if endtime - startingTime[m] > latency_Budget:
                                status = "failed"
                                violate_latency = endtime-startingTime[m]
                                break
                        if endtime >= self.latency_achieved:
                            break
        #if succeed, return the optimal latency
        if status == "undecided":
            return "success", endtime
        else:
            return status, [endtime, violation_path, violate_latency]

    def updateResourceILPBuilder(self, violation_path):
        """
        After the scheduling, if there is violation_path, 
        we need to update the constraints and resolve the ILP
        Args:
            violation_path: The list, contains the list of nodes that compose the violation
        """
        self.rb.addViolationPaths(violation_path, self.g.layerQueue, self.IP_table)
