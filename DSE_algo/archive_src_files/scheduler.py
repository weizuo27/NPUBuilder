import itertools
import networkx as nx
from gurobipy import *

class scheduler:
    def __init__(self):
        None

    def scheduling(self, g, explore_IP_types, G):
        self.model = Model(g.name)
        schedulingVariables = []
        resourceSharingVariables = dict()
        resourceTable = dict()
        bigConstant = 10000000000
        #1 create variable and resource table
        #Sort it so that I only need to whether there is a path between from n1 to n2
        node_list = list(nx.topological_sort(g))
        #Only combineNode and layerNodes have scheduing varibles
        for n in node_list:
            if n.type is "combineNode":
                for m in n.node_list:
#                    print m.name, m.type
                    resourceTable[m.mappedIP] = [n] if m.mappedIP not in resourceTable else resourceTable[m.mappedIP] + [n]

            elif n.type in explore_IP_types:
                resourceTable[n.mappedIP] = [n] if n.mappedIP not in resourceTable else resourceTable[n.mappedIP] + [n]
            schedulingVariables.append(self.model.addVar(name = n.name, vtype = GRB.INTEGER))

        #2 set constraints
        #A. Resource sharing constraints. 
        self.model.update()
        for ip in resourceTable:
            if len(resourceTable[ip]) == 1:
                continue
            for n1, n2 in list(itertools.combinations(resourceTable[ip], 2)):
                if nx.has_path(g, n1, n2):
                    continue
                var_n1 = self.model.getVarByName(n1.name)
                var_n2 = self.model.getVarByName(n2.name)
                resourceSharingV = self.model.addVar(name = n1.name + "_" + n2.name, vtype = GRB.BINARY)
                resourceSharingVariables[(n1, n2)] = resourceSharingV
                #s1 > s2, s2 - s1 > l1
                self.model.addConstr(var_n2 - var_n1 + bigConstant * resourceSharingV >= n1.latency)
                #s2 > s1, s1 - s2 > l2
                self.model.addConstr(var_n1 - var_n2 + bigConstant * (1-resourceSharingV) >= n2.latency)

        #B: The dependence constraints:
        for n1, n2 in g.edges:
            var_n1 = self.model.getVarByName(n1.name)
            var_n2 = self.model.getVarByName(n2.name)
            self.model.addConstr(var_n2 - var_n1 >= n1.latency)

        #C: All the scheduling variables should be >= 0
        for var in schedulingVariables:
            self.model.addConstr(var >= 0)
        
        #3 set the objective
#        print node_list[-1].name
        self.model.setObjective(self.model.getVarByName(node_list[-1].name), GRB.MINIMIZE)
        #4 solve the problem
        self.model.optimize()
        assert(self.model.status == GRB.Status.OPTIMAL) #There should be a optimial solution

        # rebuildGraph:
        #make connections of the reused resource
        for ip in resourceTable:
            for n1, n2 in list(itertools.combinations(resourceTable[ip], 2)):
                if (n1, n2) in resourceSharingVariables:
                    if resourceSharingVariables[(n1, n2)].X < 0.5:
                        g.add_edge(n1, n2)
                    else:
                        g.add_edge(n2, n1)

        #assign weights to the edge
        for s1, s2 in g.edges:
            g[s1][s2]['weight'] = 0-s1.latency

        #findCriticalPath:
        path_tmp = nx.bellman_ford_path(g, node_list[0], node_list[-1])
#        print "path_tmp"
#        for nn in path_tmp:
#            if nn.type is "combineNode":
#                for mm in nn.node_list:
#                    print mm.name, "latency ", mm.latency 
#                    if mm.type in explore_IP_types:
#                        print mm.mappedIP.name
#            else:
#                    print nn.name, "latency ", nn.latency
#                    if nn.type in explore_IP_types:
#                        print nn.mappedIP.name
#        for idx, nn in enumerate(path_tmp):
#            if idx < len(path_tmp)-1:
#                print "edge", nn.name, "-->", path_tmp[idx+1].name, g[nn][path_tmp[idx+1]]['weight']
#        max_latency = 0 - nx.bellman_ford_path_length(g, node_list[0], node_list[-1])
#        print "max_latency", max_latency
#        return path, max_latency
        return path_tmp
