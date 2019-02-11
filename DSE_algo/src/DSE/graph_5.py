from utils_4 import *
import matplotlib.pyplot as plt
import networkx as nx
from math import ceil
from IP import softwareIP
from vertex import *

class graph:
    def __init__(self, fileName, explore_IP_types, hw_layers, rowStep):
        self.rowStep = rowStep
        self.G = nx.DiGraph()
        self.mapping = dict()
        self.NameMapping = dict()
        self.SWMapping = dict()
        self.exploreLayerQueue = dict()
        self.original_edges = dict()
        self.original_nodes = dict()
        self.root_nodes = dict()

        self.graphs = []
        self.groups = []
        self.layerIdxTable = dict()
        self.readLayerId("./inputFiles/layerIDMapping")
        self.construct(fileName, explore_IP_types, hw_layers)


    def readLayerId(self,fileName):
        f = open(fileName)
        for l in f:
            layer, idx = l.replace(" ", "").strip().split(":")
            self.layerIdxTable[layer] = idx
        f.close()

    def construct(self, fileName, explore_IP_types, hw_layers):
        bottom_table = dict()
        pipeEndTable = dict()
        top_table = dict()

        f = open(fileName)

        for l in f:
            l = l.replace(" ", "")
            #Collect the groups of layers
            if l.find("--LayerGroups--") >= 0:
                for l in f:
                    if l== "\n":
                        break
                    self.groups.append(l.strip().split(','))

            if l.find("--Layers--") >= 0:
                for l in f:
                    l = l.replace(" ", "")
                    if l == "Xilinx\n":
                        continue
                    if l == "\n":
                        break
                    bot_str, layer_str, top_str = l.split("-->")
                    layer_str = layer_str[1:-1]
                    layer_tmp = layer(layer_str, self.rowStep, self.layerIdxTable)
                    if layer_str in pipeEndTable:
                        pipeEndTable[layer_str] = layer_tmp

                    for tmp_str in bot_str[1:-1].split(","):
                        bot_str = tmp_str.split(":")[0]
                        if bot_str in bottom_table:
                            bottom_table[bot_str].append(layer_tmp)
                        else:
                            bottom_table[bot_str] = [layer_tmp]
                        if bot_str == "data":
                            layer_tmp.firstLayer = True
                    for tmp_str in top_str[1:-1].split(","):
                        top_str = tmp_str.split(":")[0]
                        if top_str in top_table:
                            top_table[top_str].append(layer_tmp)
                        else:
                            top_table[top_str] = [layer_tmp]
                    self.add_node(layer_tmp)
            if l.find("--Blobs--") >= 0:
                for l in f:
                    l = l.replace(" ", "")
                    if l == "\n":
                        break
                    list_tmp = l.split(":")
                    blobname, dims =list_tmp[0:2]
                    if blobname in bottom_table:
                        for ll in bottom_table[blobname]:
                            ll.set_input_params(dims)
                    if blobname in top_table:
                        for ll in top_table[blobname]:
                            ll.set_output_params(dims)
            
        f.close()

        #build Edges
        for bb in bottom_table:
            if bb in top_table:
                for bbb in bottom_table[bb]:
                    for ttt in top_table[bb]:
                        self.G.add_edge(ttt, bbb)

        for bb in top_table:
            if bb not in bottom_table:
                for n in top_table[bb]:
                    self.G.add_edge(n, bb)

        for groupNames in self.groups:
            groupNodes = [self.NameMapping[n] for n in groupNames]
            subGraph = nx.DiGraph(self.G.subgraph(groupNodes))
            blob_begin = blob("begin")
            blob_end = blob("end")
            nodes_list = list(subGraph.nodes)
            for n in nodes_list:
                inD = outD = 0
                if n.type == "Eltwise":
                    inD = outD = 1
                if subGraph.in_degree(n) == inD:
                    subGraph.add_edge(blob_begin,  n)
                if subGraph.out_degree(n) == outD:
                    subGraph.add_edge(n, blob_end)
            self.graphs.append(subGraph)

        for g in self.graphs:
            #Add the exploreLayerQueue
            self.exploreLayerQueue[g] = dict()
#            def comp(elem):
#                return elem.ID
            explore_node_list = []
            for n in g.nodes:
                if n.type in explore_IP_types:
                    explore_node_list.append(n)

#            explore_node_list.sort(key = comp)

            for layer_tmp in explore_node_list:
                if layer_tmp.type in explore_IP_types:
                    if layer_tmp.type in self.exploreLayerQueue[g]:
                        self.exploreLayerQueue[g][layer_tmp.type].append(layer_tmp)
                    else:
                        self.exploreLayerQueue[g][layer_tmp.type] = [layer_tmp] 
            if not self.exploreLayerQueue[g] :
                del self.exploreLayerQueue[g]

            #Collect the original nodes and edges
            self.original_nodes[g] = list(g.nodes)
            self.original_edges[g] = list(g.edges)

    def __str__(self):
        #FIXME: Need to fill in
        None

    def computeLatency(self, g):
        """
        For each node in the graph, compute the latency and pipelined latency
        """
#        maxPipelineLayer = []
        node_list = list(nx.topological_sort(g))
        # First, compute latency
        total_bandWidth = 0
        for n in node_list:
#            print "nn", n.name
            total_bandWidth += n.bandWidth

        for n in node_list:
            if n.name in self.SWMapping:
                n.set_IP(softwareIP(n.name))
                n.latency = int(self.SWMapping[n.name])
            else:
                prevLayers = list(g.predecessors(n))
#                n.computeLatencyRowStep(prevLayers, maxPipelineLayer, total_bandWidth)
                n.computeLatencyRowStep(prevLayers, total_bandWidth)
                n.computeLatency()

#    def computeResource(self, node):
#        BRAMs, DSPs, LUTs, FFs = 0, 0, 0, 0
#        for ip in self.IP_table:
#            BRAMs += ip.BRAM
#            DSPs += ip.DSP
#            FFs += ip.FF
#            LUTs += ip.LUT
#        return BRAMs, DSPs, FFs, LUTs

    def retriveOriginalGraph(self, g):
#        self.IP_table.clear()
        g.clear()
        g.add_edges_from(self.original_edges[g])
        g.add_nodes_from(self.original_nodes[g])
#            self.maxPipelineLayer[g] = []
        #Node level clear
        for n in g.nodes:
            n.mappedIP = None
            n.IP_latency_rowStep = None
            n.lat_rowStep = None
            n.Pipelined = False
            n.start_time = None
            n.isMaxPipeLayer = False
            n.bandWidth = 0

    def drawGraph(self, g):
        h = nx.relabel_nodes(g, self.mapping)
        nx.draw(h, with_labels=True)#, font_weight = 'bold')
        plt.show()

    def printNodesMapping(self, hw_types, g):
        print "\n print nodes mapping\n"
#        nodes_list = list(nx.topological_sort(g))
#        nodes_list = list(g.nodes)
        def comp(elem):
            return elem.name
#        nodes_list.sort(key = comp)
        nodes_list = []
        for n in g.nodes:
            if n.type is "combineNode":
                for m in n.node_list:
                    if m.type in hw_types:
                        nodes_list.append(m)
            if n.type in hw_types:
                nodes_list.append(n)
        nodes_list.sort(key = comp)
        for n in nodes_list:
            print "IP", n.name, "type", n.type, "mappedIP", n.mappedIP, "is pipeined ?", n.Pipelined, n.lat_rowStep, n.latency

    def add_node(self, node):
        print "node", node.name
        self.G.add_node(node)
        self.mapping[node] = node.name
        self.NameMapping[node.name] = node
