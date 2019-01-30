#import matplotlib.pyplot as plt
import networkx as nx
#import cvxpy as cvx
from gurobipy import *
from utils import *


class resourceILPBuilder():
    """
    Attributes:
        BRAM_budget: The budget of BRAM given
        DSP_budget: The budget of DSP
        LUT_budget: The budget of LUT
        FF_budget: The budget of FF
        BW_budget: The budget of Bandwidth
        mappingVariables: Dictionary. Key: layer type. Values: 2-dim array B_ij: i-th layer mapps to j-th IP
        constraints: The list of constraints that should satisfy
        #violation_constraints, the list of constraints that only represent the path violating a latency
        resourceVariables: Dictionary. key: layer type. Value: 1-dim array R_j: j-th IP is used 
        status: The status of the problem.
            *Undecided: The problem has not be solved, the status is unknown
            *Failed: The problem has not optimial solution
            *Optimal: The problem is solved and obtained optimal solution
        self.exp_BRAM : The BRAM consumption of the current ILP solution
        self.exp_DSP : The DSP consumption of the current ILP solution
        self.exp_FF : The FF consumption of the current ILP solution
        self.exp_LUT : The LUT consumption of the current ILP solution
    """

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

    def createVs(self, IP_table, IP_table_per_layer, layerQueue, hw_supported_layers, latency, explore_IP_types):
        """
        create all variables of the problem.
        Args:
            layerQueue: The dicionary. Key: the layer type. Value: The list of layers in the NN, that is that type
            IP_table: The dictionary. Key: The layer type. Value: The candidate IPs fall into that category
            IP_table_per_layer: The dictionary to record the IP can be used per layer.
                Key: The layer. Value: list of length IP_table[layer.type]. Each element is either 0 or 1.
                    0 means that IP is not used for this layer, 1 otherwise.
            hw_supported_layers: The dictionary. key: the layers have hardware IPs.
            latency: The target latency. If the latency for one layer mapped to an IP is already bigger than then latency
                target, then we do not need to assign a variable. 
        """
        #1. create the mapping B_ij: i-th layer maps to j-th IP
        print "Create Variables"
        print "Status: ", self.status
        self.model = Model("resource")
#        self.model.setParam(GRB.Param.Heuristics, 1)
#        self.model.setParam(GRB.Param.BestObjStop, 20000000)
#        self.model.setParam(GRB.Param.Presolve, 0)
#        self.model.setParam(GRB.Param.MIPFocus, 1)
#        self.model.setParam(GRB.Param.ImproveStartNodes, 10)
#        self.model.setParam(GRB.Param.SolutionNumber, 1)
        print "gurobi version", gurobi.version()
        
        for g in layerQueue:
            self.mappingVariables[g] = dict()
            for layer_type in layerQueue[g]:
                if layer_type in hw_supported_layers:
                    queue = layerQueue[g][layer_type]
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
                    self.mappingVariables[g][layer_type] = mapping_vars

        #2. create resource varible R_j: j-th IP is used in the implementation
        for layer_type in IP_table:
            if layer_type not in explore_IP_types:
                continue
            self.resourceVariables[layer_type]=[]
            IP_queue = IP_table[layer_type]
            for j in range(len(IP_queue)):
                self.resourceVariables[layer_type].append(self.model.addVar(name=IP_queue[j].name, vtype = GRB.BINARY))
        self.model.update()

    def createConstraints(self, IP_table, layerQueue, pipelineLength, assumptionLevel, explore_IP_types):
        """
        Create constraints:
        Args:
            IP_table: The dictionary. Key: The layer type. Value: The candidate IPs fall into that category
            layerQueue: The dicionary. Key: the layer type. Value: The list of layers in the NN, that is that type
            assumptionLevel: The level of pre-defined assumptions.
                1.  
                2.
        """
        print ("Add Constraints")
        print "Status: ", self.status
        #If we know the problem is failed, then there is no point to continue
        if(self.status == "Failed"):
            return
        #1. one layer is mapped to one IP
        for g in self.mappingVariables:
            for layer_type in self.mappingVariables[g]:
                queue = self.mappingVariables[g][layer_type]
                for row in queue:
                    self.constraints.append(sum(row)==1)

        #2. resource constraints, resourceVariable[j]: how many times
        for layer_type in IP_table:
            if layer_type not in explore_IP_types:
                continue
            IP_queue= IP_table[layer_type]
            for j in range(len(IP_queue)):
                exp = 0
                for g in self.mappingVariables:
                    queue = layerQueue[g][layer_type]
                    for i in range(len(queue)):
                        exp += self.mappingVariables[g][layer_type][i][j]
                        self.constraints.append(self.resourceVariables[layer_type][j] >= self.mappingVariables[g][layer_type][i][j])
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
        self.constraints.append(exp_DSP >= self.DSP_budget/2)
        self.constraints.append(exp_FF <= self.FF_budget)
        self.constraints.append(exp_LUT <= self.LUT_budget)
        self.constraints.append(exp_BW <= self.BW_budget)

        #4. Create pipeline constraints
        #assumptionLevel == 1:
        if assumptionLevel >= 1:
            for g in self.mappingVariables:
                num_layers = 0
                for layer_type in self.mappingVariables[g]:
                    queue = layerQueue[g][layer_type]
                    num_layers += len(queue)
                    for j in range(len(IP_table[layer_type])):
                        exp = []
                        for i in range(len(queue)):
                            exp.append(self.mappingVariables[g][layer_type][i][j])
                #would like to force them use all the resource possible
                        self.constraints.append(sum(exp) <= -(-num_layers//pipelineLength))
            #FIXME: Assumption level 3: The sub graph needs to be isomorphic, the node at the same position maps to the same IP
        if assumptionLevel == 2:
            g_list = self.mappingVariables.keys()
            layer_type_list = self.mappingVariables[g_list[0]].keys()
            i_idx = len(self.mappingVariables[g_list[0]][layer_type_list[0]])
            j_idx = len(self.mappingVariables[g_list[0]][layer_type_list[0]][0])

            for layer_type in layer_type_list:
                for j in range(j_idx):
                    for i in range(i_idx):
                        for g_idx in range(len(g_list)-1):
                            if(i >= len(self.mappingVariables[g_list[g_idx+1]][layer_type])) or \
                                    (i >= len(self.mappingVariables[g_list[g_idx]][layer_type])):
                                continue
                            self.constraints.append(self.mappingVariables[g_list[g_idx]][layer_type][i][j]
                                    == self.mappingVariables[g_list[g_idx+1]][layer_type][i][j])

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
            if mappedIP not in violate_layers:
                violate_layers[mappedIP] = [(l, g)]
                all_violate_IPs[mappedIP] = []
            else: 
                violate_layers[mappedIP].append((l, g))

        #for each violated IP, collect the IPs that are smaller than this IP
        pre_exp = []
        for vio_ip in all_violate_IPs:
            vio_idx = IP_table[vio_ip.type].index(vio_ip)
            geqIPSet = None
            for l,g in violate_layers[vio_ip]:
                idx_tmp =layerIPLatencyTable[l][1].index((vio_idx, vio_ip))
                lat_tmp = layerIPLatencyTable[l][0][idx_tmp][1]
                for ii in range(idx_tmp, -1, -1):
                    lat_tmp_ii = layerIPLatencyTable[l][0][ii][1]
                    if lat_tmp_ii < lat_tmp:
                        ii = ii + 1
                        break
                idx_tmp = ii
                geqIPSet = set(layerIPLatencyTable[l][1][idx_tmp : ]) if geqIPSet is None else \
                           geqIPSet & set(layerIPLatencyTable[l][1][idx_tmp : ])

            all_violate_IPs[vio_ip] = geqIPSet if not all_violate_IPs[vio_ip] else all_violate_IPs[vio_ip] & geqIPSet

        del_list = []
        for vio_ip in violate_layers:
#            print "violate_layers", vio_ip.name, len(violate_layers[vio_ip])
            if len(violate_layers[vio_ip]) < 3:
                for j_idx, smaller_ip in all_violate_IPs[vio_ip]:
                    prod = 1
                    for l, g in violate_layers[vio_ip]:
                        prod *= self.mappingVariables[g][vio_ip.type][layerQueue[g][vio_ip.type].index(l)][j_idx]
                    pre_exp.append(prod)
#                print pre_exp
                del_list.append(vio_ip)
        print "pre_exp", pre_exp
        for vio_ip in del_list:
            del violate_layers[vio_ip]

        self.recAddViolationPath(0, violate_layers.keys(), len(del_list)+len(violate_layers), all_violate_IPs, violate_layers, [], layerQueue, pre_exp)

#            print "vio_ip", vio_ip.name, "all smaller IPs"
#            for mm in all_violate_IPs[(g, vio_ip)]:
#                print mm[1].name

    def recAddViolationPath(self, idx, keys_list, violation_path_length, all_violate_IPs, violate_layers, exp_list, layerQueue, pre_exp):
        if idx == len(keys_list):
            exp_list_org = exp_list[:] + pre_exp[:]
            def comp(elem):
                return str(elem)
            exp_list_org.sort(key = comp)

            print "exp_list_org"
            print exp_list_org, str(exp_list_org) in self.violation_constraints_table

            if str(exp_list_org) not in self.violation_constraints_table:
#                print "exp_list_org not in voliation table"
                #self.violation_constraints.append(sum(exp_list) <= violation_path_length-1)
                self.violation_constraints_table[str(exp_list_org)] = 1 
                self.model.addConstr( sum(exp_list_org) <= violation_path_length -1)
#                self.model.update()
#                self.model.write("out11.lp")
#                assert 0, "fake"
        else:
            for j_idx, ip in all_violate_IPs[keys_list[idx]]:
                for l,g in violate_layers[keys_list[idx]]:
                    i_idx = layerQueue[g][l.type].index(l)
                    exp_list.append(self.mappingVariables[g][l.type][i_idx][j_idx])
                    self.recAddViolationPath(idx+1, keys_list, violation_path_length, all_violate_IPs, violate_layers, exp_list, layerQueue, pre_exp)
                for l,g in violate_layers[keys_list[idx]]:
                    exp_list.pop()

        #recursively add the constraints
#        assert(len(violate_layers.keys()) == 0), ">????>"

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
#        print "pipelineLength", pipelineLength
        if assumptionLevel > 0:
            self.model.addConstr(sum(obj_vars) == pipelineLength)
#        print "sum(obj_vars)", sum(obj_vars)
#        self.model.setObjective(sum(obj_vars)-self.exp_BRAM/3648-self.exp_DSP/5040, GRB.MAXIMIZE) #Only check the feasibility
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
            print "ConstrVio", self.model.ConstrVio, self.model.ConstrVio > 0.5
            if(self.model.ConstrVio > 0.5):
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

#rb = resourceILPBuilder(BRAM_budget, DSP_budget, FF_budget, LUT_budget, BW_budget)
#rb.createVs(IP_table, conv_queue)
#rb.createConstraints()
#rb.createProblem()
#rb.solveProblem()
