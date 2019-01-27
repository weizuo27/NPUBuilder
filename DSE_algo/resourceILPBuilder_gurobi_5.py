#import matplotlib.pyplot as plt
import networkx as nx
#import cvxpy as cvx
from gurobipy import *
from utils import *

class resourceILPBuilder():
    def __init__(self, BRAM_budget, DSP_budget, FF_budget, LUT_budget, BW_budget):
        #The set of resource budgets
        self.BRAM_budget = BRAM_budget
        self.DSP_budget = DSP_budget
        self.LUT_budget = LUT_budget
        self.FF_budget = FF_budget
        self.BW_budget = BW_budget
        self.status = "Undecided"

        #the set of variables
        self.mappingVariables = dict() 
        self.constraints = []
        self.violation_constraints_table = dict()
        self.resourceVariables = dict()

    def createVs(self, IP_table, IP_table_per_layer, layerQueues, hw_supported_layers, latency, explore_IP_types):
        #1. create the mapping B_ij: i-th layer maps to j-th IP
        print "Create Variables"
        print "Status: ", self.status
        self.model = Model("resource")
        layerQueue = layerQueues[layerQueues.keys()[0]]
        print "gurobi version", gurobi.version()
        self.mappingVariables = dict()
        for layer_type in layerQueue:
            if layer_type in hw_supported_layers:
                queue = layerQueue[layer_type]
                IP_queue = IP_table[layer_type]
                mapping_vars = []
                for i in queue:
                    IPs = IP_table_per_layer[i]
                    row = []
                    containVs = False
                    for j in range(len(IPs)):
                        if IPs[j] == 1:
                            lat_est = i.computeLatencyIfMappedToOneIP(IP_table[i.type][j])
                            if lat_est < latency:
                                row.append(self.model.addVar(name=i.name + "_" + IP_queue[j].name, vtype = GRB.BINARY))
                                containVs = True
                            else:
                                row.append(0.0)
                        else:
                            row.append(0.0)
                    if not containVs:
                        self.status = "Failed"
                        return
                    mapping_vars.append(row)
                self.mappingVariables[layer_type] = mapping_vars

        #2. create resource varible R_j: j-th IP is used in the implementation
        for layer_type in IP_table:
            if layer_type not in explore_IP_types:
                continue
            self.resourceVariables[layer_type]=[]
            IP_queue = IP_table[layer_type]
            for j in range(len(IP_queue)):
                self.resourceVariables[layer_type].append(self.model.addVar(name=IP_queue[j].name, vtype = GRB.BINARY))
        self.model.update()

    def createConstraints(self, IP_table, layerQueues, pipelineLength, assumptionLevel, explore_IP_types):
        print ("Add Constraints")
        print "Status: ", self.status
        #If we know the problem is failed, then there is no point to continue
        if(self.status == "Failed"):
            return
        #1. one layer is mapped to one IP
        layerQueue = layerQueues[layerQueues.keys()[0]]
        for layer_type in self.mappingVariables:
            queue = self.mappingVariables[layer_type]
            for row in queue:
                self.constraints.append(sum(row)==1)

        #2. resource constraints, resourceVariable[j]: how many times
        for layer_type in IP_table:
            if layer_type not in explore_IP_types:
                continue
            IP_queue= IP_table[layer_type]
            for j in range(len(IP_queue)):
                exp = 0
                queue = layerQueue[layer_type]
                for i in range(len(queue)):
                    exp += self.mappingVariables[layer_type][i][j]
                    self.constraints.append(self.resourceVariables[layer_type][j] >= self.mappingVariables[layer_type][i][j])
                self.constraints.append(self.resourceVariables[layer_type][j] <= exp)

        #3. The sum of all resource variables should not exceed the resource budget
        exp_BRAM, exp_DSP, exp_FF, exp_LUT, exp_BW = 0,0,0,0,0
        for layer_type in IP_table:
            if layer_type not in explore_IP_types:
                continue
            IP_queue = IP_table[layer_type]
            for j in range(len(IP_queue)):
                exp_BRAM += IP_queue[j].BRAM * self.resourceVariables[layer_type][j] 
                exp_DSP += IP_queue[j].DSP* self.resourceVariables[layer_type][j]
                exp_FF += IP_queue[j].FF* self.resourceVariables[layer_type][j]
                exp_LUT += IP_queue[j].LUT* self.resourceVariables[layer_type][j]
                exp_BW += IP_queue[j].BW * self.resourceVariables[layer_type][j]

        #We want to record the following four expressions since they gives the result of the resouce consumption
        self.exp_BRAM = exp_BRAM
        self.exp_DSP = exp_DSP
        self.exp_FF = exp_FF
        self.exp_LUT = exp_LUT

        self.constraints.append(exp_BRAM <= self.BRAM_budget)
        self.constraints.append(exp_BRAM >= self.BRAM_budget/2)
        self.constraints.append(exp_DSP <= self.DSP_budget)
        self.constraints.append(exp_DSP >= self.DSP_budget*0.9)
        self.constraints.append(exp_FF <= self.FF_budget)
        self.constraints.append(exp_LUT <= self.LUT_budget)
        self.constraints.append(exp_BW <= self.BW_budget)

        #4. Create pipeline constraints
        #assumptionLevel == 1:
        if assumptionLevel >= 1:
            num_layers = 0
            for layer_type in self.mappingVariables:
                queue = layerQueue[layer_type]
                num_layers += len(queue)
                for j in range(len(IP_table[layer_type])):
                    exp = []
                    for i in range(len(queue)):
                        exp.append(self.mappingVariables[layer_type][i][j])
            #would like to force them use all the resource possible
                    self.constraints.append(sum(exp) <= -(-num_layers//pipelineLength))

    def addViolationPaths(self, violation_path, layerQueue, IP_table, layerIPLatencyTable, assumptionLevel, lat_diff):
        """
        After scheduling, given a violation path, add the corresponding constraints back to the problem
        violation_path: The list, which represents the path that total latency violates the latency budget
            Each item is a tuple: (layer, mappedIP)
        layerQueue: The dictionary of layers in the application. Key: layer type. Value: A list of layers fall 
            into that type
        IP_table: The dictionary of IP table. Key: IP type. Value: A list of IP that fall into that type

        The rule is as following:
            1. The violation path is broken into a dictionary called "violate_layers". Where the key are the IPs that are used
               in the violation path. And the value are the layers used the IP.
            2. For each violated IP, we collect the IPs that are smaller than this IP, store them in the dictionary "all_violate_IPs"
            3. The violation_path that mapped to the smaller IPs definitely cannot meet the latency, so we can add them all in.

            E.g. the violation path is (conv1, IP1)-->(conv2, IP1)-->(conv3, IP2). Assume IP0 is smaller than IP1, IP2 is bigger 
                then IP1. Therefore, 

                The violate_layers is {IP1: [conv1, conv1], IP3: [conv3]}.
                The invalid combination is:  
                    (conv1, IP0)-->(conv2, IP0) -->(conv3, IP0)
                    (conv1, IP0)-->(conv2, IP0) -->(conv3, IP1)
                    (conv1, IP0)-->(conv2, IP0) -->(conv3, IP2)

                    (conv1, IP1)-->(conv2, IP1) -->(conv3, IP0)
                    (conv1, IP1)-->(conv2, IP1) -->(conv3, IP1)
                    (conv1, IP1)-->(conv2, IP1) -->(conv3, IP2)
            4. We use recursion to add all the violations back to the constraints.
        """
        print "addViolationPaths", lat_diff
        print "Status: ", self.status
        if(self.status == "Failed"):
            return

        violate_layers = dict()
        all_violate_IPs = dict()

        for l, g, mappedIP in violation_path:
            if l not in violate_layers:
                violate_layers[mappedIP] = [(l, g)]
                all_violate_IPs[mappedIP] = []
            else:
                violate_layers[mappedIP].append((l, g))

        #for each violated IP, collecte the IPs that are smaller than this IP
        pre_exp = []
        for vio_ip in all_violate_IPs:
            vio_idx = IP_table[vio_ip.type].index(vio_ip)
            geqIPSet = None
            for l, g in violate_layers[vio_ip]:
                idx_tmp =layerIPLatencyTable[l][1].index((vio_idx, vio_ip))
                lat_tmp = layerIPLatencyTable[l][0][idx_tmp][1]
                for ii in range(idx_tmp, -1, -1):
                    lat_tmp_ii = layerIPLatencyTable[l][0][ii][1]
                    if lat_tmp_ii < lat_tmp:
                        ii = ii + 1
                        break
                geqIPSet = set(layerIPLatencyTable[l][1][idx_tmp : ]) if geqIPSet is None else \
                           geqIPSet & set(layerIPLatencyTable[l][1][idx_tmp : ])

            all_violate_IPs[vio_ip] = list(geqIPSet)
            assert len(violate_layers[vio_ip]) <= 2, "may want to devided the group even finer"

            #Fold the violation to the mapping of one graph
            for j_idx, smaller_ip in all_violate_IPs[vio_ip]:
                prod = 1
                varIdxSet = set()
                for l,g in violate_layers[vio_ip]:
                    varIdxSet.add(layerQueue[g][vio_ip.type].index(l))
                for idx in varIdxSet:
                    prod *= self.mappingVariables[vio_ip.type][idx][j_idx]
                pre_exp.append(prod)

        def comp(elem):
            return str(elem)
        pre_exp.sort(key = comp)

        if str(pre_exp) not in self.violation_constraints_table:
            self.violation_constraints_table[str(pre_exp)] = 1 
            self.model.addConstr(sum(pre_exp) <= len(violate_layers.keys()) -1) 

    def createProblem(self, pipelineLength, assumptionLevel):
        """
        Formulate the problem, only check the feasibility
        The objective is maximize the sum of resource variables.  
        The reason is that, only by setting the objective to be maximum, 
        the resource vairables constraints is complete.
        However, this discourages the resource reuse, since the solution will
        always maximize the resource maximization variables. 
        #FIXME: Is there are better way to formulate this problem?
        """
        print("Create Problem")
        print "Status: ", self.status
        if(self.status == "Failed"):
            return
        obj_vars = []
        for layer_type in self.resourceVariables:
            obj_vars += self.resourceVariables[layer_type] 

        if assumptionLevel > 0:
            self.model.addConstr(sum(obj_vars) == pipelineLength)
        self.model.setObjective(self.exp_BRAM+self.exp_DSP, GRB.MINIMIZE) #Only check the feasibility
        for i in self.constraints:
            self.model.addConstr(i)

        self.model.write("out.lp")

    def solveProblem(self):
        """
            return: True if the optimal solution can be found. False otherwise
        """
        print ("Solve Problem")
        if(self.status == "Failed"):
            return
        #self.model.params.MIPFocus = 3
        self.model.optimize()
        self.model.printStats()
        if(self.model.status == GRB.Status.OPTIMAL or self.model.status == GRB.Status.USER_OBJ_LIMIT):
            #if there is violation of constraint, turn presolve off
            # and re solve it
            print "ConstrVio", self.model.ConstrVio, self.model.ConstrVio >= 1
            if(self.model.ConstrVio >= 1):
                self.status = "Failed"
                return False
        if(self.model.status == GRB.Status.OPTIMAL or self.model.status == GRB.Status.USER_OBJ_LIMIT):
            self.status = "Optimal"
        else:
            self.status = "Failed"

    def printSolution(self, iteration, level = 1):
        """
            Level of the detail level of the solution
        """
        print "Print solution"
        print "Status: ", self.status
        print "Solver status:", self.model.status
        print "BRAM consumption:", self.exp_BRAM.getValue()
        print "DSP consumption:", self.exp_DSP.getValue()
        print "FF consumption:", self.exp_FF.getValue()
        print "LUT consumption:", self.exp_LUT.getValue()
        print "constraints"
        if(level > 1):
            for g in self.mappingVariables:
                for layer_type in self.mappingVariables[g]:
                    print layer_type, ":"
                    for i, row in enumerate(self.mappingVariables[layer_type]):
                        for j, elem in enumerate(row):
                            if elem is not 0.0:
                                print "mapping", i, j, elem.VarName, elem.X
                        print "\n"
                    for j, res in enumerate(self.resourceVariables[layer_type]):
                        print "resource", res.VarName, res.X
#        self.model.write("out"+str(iteration)+".lp")

    def getResourceTable(self):
        """
        Return the resource consumption AFTER the problem is solved, variables are assigned value
        """
        return self.exp_BRAM.getValue(), self.exp_DSP.getValue(), self.exp_FF.getValue(), self.exp_LUT.getValue()
