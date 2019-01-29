#import matplotlib.pyplot as plt
import networkx as nx
#import cvxpy as cvx
from gurobipy import *
from utils_4 import *

class resourceILPBuilder():
    def __init__(self):
        self.model = None
        self.status = "Undecided"
        self.mappingVariables = dict()
        self.violation_constraints_table = dict()

    def createVs(self, IP_table, IP_table_per_layer, layerQueue, hw_supported_layers, latency):
        print "create Variables", self.status
        self.model = Model("resource")
        self.model.Params.OutputFlag = 0
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

        self.model.update()

    def createConstraints(self, IP_table, layerQueue, numIPs):
        print "create Constraints", self.status
        if(self.status == "Failed"):
            return
        #1. one layer is mapped to one IP
        for layer_type in self.mappingVariables:
            queue = self.mappingVariables[layer_type]
            for row in queue:
                self.constraints.append(sum(row) == 1)

        #4. Create pipeline constraints
        num_layers = 0
        for layer_type in self.mappingVariables:
            queue = layerQueue[layer_type]
            num_layers += len(queue)
            for j in range(len(IP_table[layer_type])):
                exp = []
                for i in range(len(queue)):
                    exp.append(self.mappingVariables[layer_type][i][j])
        #would like to force them use all the resource possible
                self.constraints.append(sum(exp) <= -(-num_layers//numIPs[layer_type]))

    def addViolationPaths(self, violation_path, layerQueue, IP_table, layerIPLatencyTable):
        print "addViolationPaths"
        print "Status: ", self.status
        if(self.status == "Failed"):
            return
        
        violate_layers = dict()
        all_violate_IPs = dict()

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

            all_violate_IPs[vio_ip] = list(geqIPSet)

#            assert len(violate_layers[vio_ip]) <= 2, "may want to devided the group even finer"

        del_list = []
        for vio_ip in violate_layers:
            if len(violate_layers[vio_ip]) <= 2:
                for j_idx, smaller_ip in all_violate_IPs[vio_ip]:
                    prod = 1
                    for l in violate_layers[vio_ip]:
                        prod *= self.mappingVariables[vio_ip.type][layerQueue[vio_ip.type].index(l)][j_idx]
                    pre_exp.append(prod)
                del_list.append(vio_ip)
        for vio_ip in del_list:
            del violate_layers[vio_ip]

        self.recAddViolationPath(0, violate_layers.keys(), len(del_list) + len(violate_layers), all_violate_IPs, violate_layers, [], layerQueue, pre_exp)

    def recAddViolationPath(self, idx, keys_list, violation_path_length, all_violate_IPs, violate_layers, exp_list, layerQueue, pre_exp):
        if idx == len(keys_list):
            exp_list_org = exp_list[:] + pre_exp[:]
            def comp(elem):
                return str(elem)
            exp_list_org.sort(key = comp)
            if str(exp_list_org) not in self.violation_constraints_table:
                self.violation_constraints_table[str(exp_list_org)] = 1 
                self.model.addConstr(sum(exp_list_org) <= violation_path_length -1) 
        else:
            for j_idx, ip in all_violate_IPs[keys_list[idx]]:
                for l in violate_layers[keys_list[idx]]:
                    i_idx = layerQueue[l.type].index(l)
                    exp_list.append(self.mappingVariables[l.type][i_idx][j_idx])
                    self.recAddViolationPath(idx+1, keys_list, violation_path_length, all_violate_IPs, violate_layers, exp_list, layerQueue, pre_exp)
                for l in violate_layers[keys_list[idx]]:
                    exp_list.pop()

    def createProblem(self):
        print("Create Problem")
        print "Status: ", self.status

        if(self.status == "Failed"):
            return

        self.model.setObjective(1, GRB.MAXIMIZE)

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
        self.model.write("out.lp")
        self.model.optimize()
#        self.model.printStats()
        if(self.model.status == GRB.Status.OPTIMAL or self.model.status == GRB.Status.USER_OBJ_LIMIT):
            if(self.model.ConstrVio > 0.5):
                self.status = "Failed"
                print "ConstrVio", self.model.ConstrVio, self.model.ConstrVio > 0.5, self.status
                return False

        if(self.model.status == GRB.Status.OPTIMAL or self.model.status == GRB.Status.USER_OBJ_LIMIT):
            self.status = "Optimal"
        else:
            self.status = "Failed"
