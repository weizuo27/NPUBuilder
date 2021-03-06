from utils import *
import matplotlib.pyplot as plt
from copy import deepcopy
import networkx as nx
#import cvxpy as cvx
from IP import softwareIP
from math import ceil
from vertex import *

class graph:
    def __init__(self, fileName, explore_IP_types, rowStep):
        self.rowStep = rowStep
        self.G = nx.DiGraph()
        self.mapping = dict()
        self.SWMapping = dict()
        self.exploreLayerQueue = dict()
        self.original_edges = dict()
        self.original_nodes = dict()
        self.root_nodes = dict()
#        maxPipelineLayer = dict()
        self.graphs = []
        self.construct(fileName, explore_IP_types)

    def construct(self, filename, explore_IP_types):
        """
        The function to construct the graph from a file that is dumped from CHaiDNN
        Args:
            filename: the name of the file
        """
        bottom_table = dict()
        pipeStartTable = dict()
        top_table = dict()
        f = open(filename)
        for l in f:
            l = l.replace(" ", "")
            if l.find("--Layers--") >= 0:
                for l in f:
                    l = l.replace(" ", "")
                    if l == "Xilinx\n":
                        continue
                    if l == "\n":
                        break
                    bot_str, layer_str, top_str = l.split("-->")

                    layer_str = layer_str[1:-1]
                    layer_tmp = layer(layer_str, self.rowStep)

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
                    pipeStart = len(list_tmp) == 3
                    blobname, dims =list_tmp[0:2]
                    if blobname in bottom_table:
                        for ll in bottom_table[blobname]:
                            ll.set_input_params(dims)
                        if pipeStart:
                            pipeStartTable[blobname] = 1
                    if blobname in top_table:
                        for ll in top_table[blobname]:
                            ll.set_output_params(dims)

            if l.find("--Softwarelayerlatency--") >= 0:
                for l in f:
                    if l == "\n":
                        break
                    l = l.replace(" ", "")[0:-1]
                    layer_name, layer_lat = l.split(":")
                    self.SWMapping[layer_name] = int(layer_lat)
        f.close()

        #Build Edges
        idx = 0

        for bb in bottom_table:
            if bb in pipeStartTable:
                blob_tmp = blob(bb)
                self.add_node(blob_tmp)
                for n in bottom_table[bb]:
                    self.G.add_edge(blob_tmp, n)

                if bb in top_table:
                    blob_tmp_end = blob(bb+"_end")
                    self.add_node(blob_tmp_end)
                    for n in top_table[bb]:
                        self.G.add_edge(n, blob_tmp_end)

            elif bb in top_table:
                for bbb in bottom_table[bb]:
                    for ttt in top_table[bb]:
                        self.G.add_edge(ttt, bbb) 

        for bb in top_table:
            if bb not in bottom_table:
                blob_tmp_end = blob(bb+"_end")
                self.add_node(blob_tmp_end)
                for n in top_table[bb]:
                    self.G.add_edge(n, blob_tmp_end)
        
        connectd_sets = nx.weakly_connected_components(self.G)
    
        for s in connectd_sets:
            g = nx.DiGraph(self.G.subgraph(list(s)))
            self.graphs.append(g)
#        self.drawGraph()
        
        for g in self.graphs:
            #Add the exploreLayerQueue
            self.exploreLayerQueue[g] = dict()
            def comp(elem):
                return elem.ID
            explore_node_list = []
            for n in g.nodes:
                if n.type in explore_IP_types:
                    explore_node_list.append(n)

            explore_node_list.sort(key = comp)

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
            print "\n"

    def __str__(self):
        #FIXME: Need to fill in
        None

    def computeLatency(self):
        """
        For each node in the graph, compute the latency and pipelined latency
        """
        maxPipelineLayer = []
        for g in self.graphs:
            node_list = list(nx.topological_sort(g))
            total_bandWidth = 0
            for n in node_list:
#                print "nn", n.name, n.bandWidth
                total_bandWidth += n.bandWidth
#            print "total ", total_bandWidth

            for n in node_list:
                if n.name in self.SWMapping:
                    n.set_IP(softwareIP(n.name))
                    n.latency = int(self.SWMapping[n.name])
                else:
                    prevLayers = list(g.predecessors(n))
#                    n.computeLatencyRowStep(prevLayers, self.maxPipelineLayer[g])
                    print "total ", total_bandWidth, n.name, n.type
                    n.computeLatencyRowStep(prevLayers, maxPipelineLayer, total_bandWidth)
                    n.computeLatency()
        for n in maxPipelineLayer:
            n.isMaxPipeLayer = True

    def add_node(self, node):
        self.G.add_node(node)
        self.mapping[node] = node.name

    def retriveOriginalGraph(self):
        for g in self.graphs:
            g.clear()
            g.add_edges_from(self.original_edges[g])
            g.add_nodes_from(self.original_nodes[g])
#            self.maxPipelineLayer[g] = []
            #Node level clear
            for n in self.G.nodes:
                n.mappedIP = None
                n.IP_latency_rowStep = None
                n.lat_rowStep = None
                n.Pipelined = False
                n.start_time = None
                n.isMaxPipeLayer = False

    def drawGraph(self):
        for g in self.graphs:
            h = nx.relabel_nodes(g, self.mapping)
            nx.draw(h, with_labels=True)#, font_weight = 'bold')
            plt.show()

    def printNodesMapping(self, hw_types):
        print "\n print nodes mapping\n"
        for g in self.graphs:
            if g in self.exploreLayerQueue:
                for ip_type in self.exploreLayerQueue[g]:
                    for n in self.exploreLayerQueue[g][ip_type]:
                        print "IP", n.name, "type", n.type, "mappedIP", n.mappedIP, "is pipeined ?", n.Pipelined, "is maxPipelineLayer?", n.isMaxPipeLayer, n.lat_rowStep, n.latency
