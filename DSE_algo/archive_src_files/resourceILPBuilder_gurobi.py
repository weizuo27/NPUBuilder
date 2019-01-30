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
        #self.violation_constraints = []
        self.violation_constraints_table = dict()
        self.resourceVariables = dict()

    def createVs(self, IP_table, IP_table_per_layer, layerQueue, hw_supported_layers, latency):
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
#        self.model.setParam(GRB.Param.BestObjStop, 1)
#        self.model.setParam(GRB.Param.Presolve, 0)
#        self.model.setParam(GRB.Param.MIPFocus, 1)
#        self.model.setParam(GRB.Param.ImproveStartNodes, 10)
#        self.model.setParam(GRB.Param.SolutionNumber, 1)
        print "gurobi version", gurobi.version()
        for layer_type in layerQueue:
            if layer_type in hw_supported_layers:
                queue = layerQueue[layer_type] #The queue of the layer_type
                IP_queue = IP_table[layer_type]
                self.mappingVariables[layer_type] = dict()
                mapping_vars = [] 

                #Traverse the queue to add the varible
                for i in queue: 
                    IPs = IP_table_per_layer[i] #The IPs available for the layer type
                    row = []
                    containVs = False
#print layerIPLatencyTable[i]
#                    print len(layerIPLatencyTable[i]), len(IPs), len(IP_table[i.type])
#                    assert (len(layerIPLatencyTable[i]) == len(IPs) == len(IP_table[i.type])), \
                    "The length of layerIPLatencyTable, IPs and IP_table does not match"
#                    for ip, lat_est, j in layerIPLatencyTable[i]:
                    for j in range(len(IPs)):
                        if IPs[j] == 1:
                            lat_est = i.computeLatencyIfMappedToOneIP(IP_table[i.type][j])
                            #Only if the single layer latency is smaller than the latency estimate, we create variable
                            if lat_est < latency: 
                                row.append(self.model.addVar(name=i.name + "_" + IP_queue[j].name, vtype = GRB.BINARY))
                                containVs = True
                            else:
                                row.append(0.0)
                        else:
                            row.append(0.0)
                    #If for one layer there is no possbile IP, then the ILP will not be feasible, we can directly return.
                    if not containVs: 
                        self.status ="Failed"
                        return
                    mapping_vars.append(row)
                self.mappingVariables[layer_type] = mapping_vars



        #2. create resource varible R_j: j-th IP is used in the implementation
        for layer_type in IP_table:
            if layer_type == "Pooling":
                continue
            self.resourceVariables[layer_type]=[]
            IP_queue = IP_table[layer_type]
            for j in range(len(IP_queue)):
                self.resourceVariables[layer_type].append(self.model.addVar(name=IP_queue[j].name, vtype = GRB.BINARY))
        self.model.update()
        #print "num of variables",  self.model.NumVars

    def createConstraints(self, IP_table, layerQueue, pipelineLength, assumptionLevel):
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
        for layer_type in self.mappingVariables:
            queue = self.mappingVariables[layer_type]
            for row in queue:
                self.constraints.append(sum(row)==1)

        #2. resource constraints, resourceVariable[j]: how many times
        for layer_type in self.mappingVariables:
            IP_queue= IP_table[layer_type]
            queue = layerQueue[layer_type]
            for j in range(len(IP_queue)):
                exp = self.mappingVariables[layer_type][0][j]
                self.constraints.append(self.resourceVariables[layer_type][j]>= self.mappingVariables[layer_type][0][j])
                for i in range(1, len(queue)):
                    exp += self.mappingVariables[layer_type][i][j] 
                    self.constraints.append(self.resourceVariables[layer_type][j]>= self.mappingVariables[layer_type][i][j])

                #FIXME: Currently only has reousrceVariable[layer_type][j] <= sum(mappVariable[layer_type][i][j];
                #but the correct formulation is resourceVariables[layer_type][j] = 0 if sum(mappVariable[layer_type][i][j] == 0 else 1
                #since it is to indicate whether that is used. 
                #How to formulate it in a better way?

                #The reason I can formulate it in this way is because in the problem solving, 
                #The objective function is maximize the sum of resource variables
                self.constraints.append(self.resourceVariables[layer_type][j]<=exp) 
                #if(layer_type == "Pooling"):
                    #print exp

        #3. The sum of all resource variables should not exceed the resource budget
        exp_BRAM, exp_DSP, exp_FF, exp_LUT, exp_BW = 0,0,0,0,0
        for layer_type in IP_table:
            if layer_type == "Pooling":
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
#        self.constraints.append(exp_DSP >= 1878)
#        self.constraints.append(exp_BRAM >= 1300)
        self.constraints.append(exp_BRAM <= self.BRAM_budget)
        self.constraints.append(exp_DSP <= self.DSP_budget)
        self.constraints.append(exp_FF <= self.FF_budget)
        self.constraints.append(exp_LUT <= self.LUT_budget)
        self.constraints.append(exp_BW <= self.BW_budget)

        #4. Create pipeline constraints
        if(assumptionLevel>0):
            for layer_type in self.mappingVariables:
                IP_queue = IP_table[layer_type]
                queue = layerQueue[layer_type]
#            print len(queue), pipelineLength

                if(assumptionLevel > 1):
                    for i in range(0, len(queue)-pipelineLength, pipelineLength):
                        for j in range(len(IP_queue)):
                            #exp = []
                            for ii in range(pipelineLength):
                                #print "ii, i+ii, j ", ii, i+ii, j, self.mappingVariables[layer_type][i+ii][j]
#                        exp.append(self.mappingVariables[layer_type][i+ii][j])
#                            print "exp", self.mappingVariables[layer_type][i+ii][j], self.mappingVariables[layer_type][i+ii+pipelineLength][j]
                                self.constraints.append(self.mappingVariables[layer_type][i+ii][j] == self.mappingVariables[layer_type][i+ii+pipelineLength][j])
                                if len(queue) - (i+ii+pipelineLength) == 1:
                                    break
                else:
                    for i in range(0, len(queue), pipelineLength):
                        for j in range(len(IP_queue)):
                            exp = []
                            for ii in range(pipelineLength):
                                #print "ii, i+ii, j ", ii, i+ii, j, self.mappingVariables[layer_type][i+ii][j]
                                exp.append(self.mappingVariables[layer_type][i+ii][j])
#                            print "exp", self.mappingVariables[layer_type][i+ii][j], self.mappingVariables[layer_type][i+ii+pipelineLength][j]
#                            self.constraints.append(self.mappingVariables[layer_type][i+ii][j] == self.mappingVariables[layer_type][i+ii+pipelineLength][j])
                                if len(queue) - (i+ii) == 1:
                                    break
                            #print "exp", exp 
                            self.constraints.append(sum(exp) <= 1)

    def addViolationPaths(self, violation_path, layerQueue, IP_table, layerIPLatencyTable, lat_diff, assumptionLevel):
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
        print "addViolationPaths"
        print "Status: ", self.status, lat_diff
        if(self.status == "Failed"):
            return
        violate_layers = dict()
        all_violate_IPs = dict()
        
        #1. construct the "violate_layers" table
        for l, mappedIP in violation_path:
            if mappedIP not in violate_layers:
                violate_layers[mappedIP] = [l]
                all_violate_IPs[mappedIP] = []
            else:
                violate_layers[mappedIP].append(l)

        #for each violated IP, collect the IPs that are smaller than this IP
        pre_exp = []
        for vio_ip in all_violate_IPs:
            vio_idx = IP_table[vio_ip.type].index(vio_ip)
            geqIPSet = None
            for l in violate_layers[vio_ip]:
#                print vio_idx, vio_ip.name, (vio_idx, vio_ip) in layerIPLatencyTable[l], layerIPLatencyTable[l].index((vio_idx, vio_ip))
                idx_tmp =layerIPLatencyTable[l][1].index((vio_idx, vio_ip))
                lat_tmp = layerIPLatencyTable[l][0][idx_tmp][1]
                for ii in range(idx_tmp, -1, -1):
                    lat_tmp_ii = layerIPLatencyTable[l][0][ii][1]
                    if lat_tmp_ii < lat_tmp:# - lat_diff: # - lat_tmp/10:
                        ii = ii + 1
                        break
#                print "lat_tmp_ii, idx_tmp, ii", lat_tmp_ii, idx_tmp, ii
                idx_tmp = ii
                geqIPSet = set(layerIPLatencyTable[l][1][idx_tmp : ]) if geqIPSet is None else \
                           geqIPSet & set(layerIPLatencyTable[l][1][idx_tmp : ])

            all_violate_IPs[vio_ip] = list(geqIPSet)

#            for idx, ip in enumerate(IP_table[vio_ip.type]):
#                if all(ip.paramList[i] <= vio_ip.paramList[i] for i in range(len(ip.paramList))):
#                    all_violate_IPs[vio_ip].append((idx,ip))
            if assumptionLevel == 0:
                if len(violate_layers[vio_ip]) == 1:
                    l = violate_layers[vio_ip][0]
                    for j_idx, smaller_ip in all_violate_IPs[vio_ip]:
                        pre_exp.append(self.mappingVariables[vio_ip.type][layerQueue[vio_ip.type].index(l)][j_idx])
                    del violate_layers[vio_ip]
            else:
                for l in violate_layers[vio_ip]:
                    print vio_ip.name
                    for j_idx, smaller_ip in all_violate_IPs[vio_ip]:
                        pre_exp.append(self.mappingVariables[vio_ip.type][layerQueue[vio_ip.type].index(l)][j_idx])
                del violate_layers[vio_ip]

#            print "all_violate_IPs for ", vio_ip.name
#            for idx, ip in all_violate_IPs[vio_ip]:
#                print idx, ip
#            else:
#                print "violate layers for", vio_ip.name
#                for l in violate_layers[vio_ip]:
#                    print l.name


        #Recursively add the constraints
        self.recAddViolationPath(0, violate_layers.keys(), len(violation_path), all_violate_IPs, violate_layers, [], layerQueue, pre_exp)


    def recAddViolationPath(self, idx, keys_list, violation_path_length, all_violate_IPs, violate_layers, exp_list, layerQueue, pre_exp):
        """
            Recursive function to add the violation paths to the constraints
            Args:
                key_list: The list of all the IPs we want to traverse
                idx: The index of the key_list
                violation_path_length: The RHS of the cosntarint. the sum of all the layers in the violation path need to be smaller than 
                    violation_path_length
                all_violate_IPs: 
                violate_layers:
                exp_list:
                layerQueue: The dictionary of layers in the application. Key: layer type. Value: A list of layers fall 
        """
        if idx == len(keys_list):
            exp_list_org = exp_list[:] + pre_exp[:]
            exp_list_org.sort()
            print "exp_list"
            print sum(exp_list_org)
#            self.model.update()
            if tuple(exp_list_org) not in self.violation_constraints_table:
#                print "exp_list_org not in voliation table"
                    #self.violation_constraints.append(sum(exp_list) <= violation_path_length-1)
                self.violation_constraints_table[tuple(exp_list_org)] = 1
                self.model.addConstr( sum(exp_list_org) <= violation_path_length -1)
#                print sum(exp_list_org), violation_path_length-1

        else:
            for j_idx, ip in all_violate_IPs[keys_list[idx]]:
                for l in violate_layers[keys_list[idx]]:
                    i_idx = layerQueue[l.type].index(l)
                    exp_list.append(self.mappingVariables[l.type][i_idx][j_idx])
#                    print "exp_list", exp_list
                self.recAddViolationPath(idx+1, keys_list, violation_path_length, all_violate_IPs, violate_layers, exp_list, layerQueue, pre_exp)
                for l in violate_layers[keys_list[idx]]:
                    exp_list.pop()

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
#        print "sum(obj_vars)", sum(obj_vars)
#        self.model.setObjective(sum(obj_vars)-self.exp_BRAM/3648-self.exp_DSP/5040, GRB.MAXIMIZE) #Only check the feasibility
        self.model.setObjective(self.exp_BRAM+self.exp_DSP, GRB.MINIMIZE) #Only check the feasibility
        for i in self.constraints:
            self.model.addConstr(i)

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
                print "re optimize the model"
#                self.model.setParam(GRB.Param.Presolve, 1)
#                self.model.optimize()
#                self.model.printStats()
#                self.model.setParam(GRB.Param.Presolve, -1) 
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
            for layer_type in self.mappingVariables:
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
