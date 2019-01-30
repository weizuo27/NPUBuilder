from utils import *
import matplotlib.pyplot as plt
from copy import deepcopy
import networkx as nx
#import cvxpy as cvx
from IP import softwareIP

class pipeNode:
    """
    The node inserted to account for the pipeline structure
    """
    idx = 0
    def __init__(self, neg_latency):
        self.name = "pipeNode" + str(pipeNode.idx)
        self.type = "pipeNode"
        pipeNode.idx+=1
        self.latency = neg_latency

class layer:
    """ 
        The class to discribe attributes relate to layers
        Attrs:
            name: The name of the layer
            type: The type of the layer
            params: The parameter list of the layers, according to different type, the list
            has different interpretation.
                Conv:   [Filter(cout x cin x fh x fw), Stride, Padding, DilationFactor, 
                Group number, ReLU, HasBias]
                Pool:  
            input_params: The input dimension of the layer [batch, channel, height, width]
            output_params: The output dimension of the layer[batch, channel, height, width]
            mappedIP: The mapped ip of this layer
            lat_one_row: The latency to compute one output row
            latency: The total latency to compute this layer
                start_time: The time stamp that the layer start execution
            Pipelined: Bool. Whether the current layer is pipelined with previous layer
        Methods:
            set_input_params: Set input dimentions
            set_output_params: set output related parameters, e.g., dimensions
            set_IP: set the mapped IP for this layer
"""
    def __init__(self, line):
        """
        Constructor
        Args: 
            line: the str that contains information of each layer
        """
        n_t = line.split(":")[0]
        self.name, self.type = n_t.split("-")
        self.lat_one_row = None
        #FIXME: The following are currently left blank, whether this is the best?
        self.mappedIP = None
        self.firstLayer = False
        self.Pipelined = False

        if(self.type == "XPack Layer"):
            self.params = line.split(":")[2]
        else:
            self.params = line.split(":")[1].split(";")

    def set_IP(self, IP):
        """
        set the mapped IP for this layer
        Args:
            IP: The object IP. The IP this layer is mapped to.
        """
        self.mappedIP = IP

    def set_input_params(self, line):
        """
        The function sets the input parameters
        """
        self.input_params = map(int,line.split("x")) #[batch, channel, height, width]

    def set_output_params(self, line):
        """
        The function sets the output parameters
        """
        self.output_params = map(int,line.split("x")) #[batch, channel, height, width]

    def computeLatencyIfMappedToOneIP(self, ip):
        """
        Compute the latency if the layer is mapped to one IP.
        Args:
            ip: The ip that the layer is mapped to.
            ret: Int, the latency cycle to compute this layer
        """
        assert(ip.type == self.type), "The type of IP and the layer do not match."

        in_height, in_width = map(int, self.input_params[2:4])
        out_height, out_width = map(int, self.output_params[2:4])

        if self.type == "Convolution"or self.type == "Convolution_g":
            cout, cin, kw, kh = map(int, (self.params[0].split("=")[1]).split("x"))
            S = int(self.params[1].split("=")[1])
            padding = int(self.params[2].split("=")[1])
            group = int(self.params[4].split("=")[1])
            #FIXME: what is the best way to pass in the parameters

            #TODO: Assumption: Now here we do not consider the warm-up phase of computation.
            #E.g., a convolution. Stride =4, kh =11. For the first output row, it needs
            #to compute 11 input rows, but for the remaining rows,  it only need 4. 
            #We neglect the first row, and assume that one output row requires 4 input row.
            latency_one_row = ip.computeLatency(
                    [cout, cin, kw, kh, S, padding, group],
                    in_height, 
                    in_width, 
                    out_height, 
                    out_width) 

        elif self.type == "Pooling":
            PoolType = self.params[0].split("=")[1]
            N = int(self.params[1].split("=")[1])
            kw = kh = int(self.params[2].split("=")[1])
            S = int(self.params[3].split("=")[1])
            P = int(self.params[4].split("=")[1])

            latency_one_row = ip.computeLatency(
                    [N,kh,S,P], 
                    in_height, 
                    in_width, 
                    out_height, 
                    out_width)
        else: 
            assert(0), "Unsupported layer type"

        return latency_one_row * out_height

    def computeLatencyOneRow(self, prevLayers, g):
        """
        The latency to compute one row
        Args:
            prevLayers: the list of previous layers
            g: The graph that this layer belongs to.  This is to update the graph attribute "maxPipelineLayer"
        """
        assert (self.mappedIP is not None), self.name + " mapped IP is not decided,\
            so no way to compute the latency"

        if self.mappedIP == "Software":
            return

        in_height, in_width = map(int, self.input_params[2:4])
        out_height, out_width = map(int, self.output_params[2:4])

        #Assumption: S < W, which is the case of most NN
        if self.type == "Convolution"or self.type == "Convolution_g":
            cout, cin, kw, kh = map(int, (self.params[0].split("=")[1]).split("x"))
            S = int(self.params[1].split("=")[1])
            padding = int(self.params[2].split("=")[1])
            group = int(self.params[4].split("=")[1])
            #FIXME: what is the best way to pass in the parameters

            #TODO: Assumption: Now here we do not consider the warm-up phase of computation.
            #E.g., a convolution. Stride =4, kh =11. For the first output row, it needs
            #to compute 11 input rows, but for the remaining rows,  it only need 4. 
            #We neglect the first row, and assume that one output row requires 4 input row.
            self.IP_latency= self.mappedIP.computeLatency(
                    [cout, cin, kw, kh, S, padding, group],
                    in_height, 
                    in_width, 
                    out_height, 
                    out_width) 

        elif self.type == "Pooling":
            PoolType = self.params[0].split("=")[1]
            N = int(self.params[1].split("=")[1])
            kw = kh = int(self.params[2].split("=")[1])
            S = int(self.params[3].split("=")[1])
            P = int(self.params[4].split("=")[1])
            self.IP_latency = self.mappedIP.computeLatency(
                    [N,kh,S,P], 
                    in_height, 
                    in_width, 
                    out_height, 
                    out_width)
        else:
            assert 0, "This layer has unsupported type"

        #Now start computing the latency for computing one row

        #If the current layer is the starting of a pipeline chain, the maxPipeilneLayer for this
        #chain is itself. Otherwise, if one layer's latency is bigger than the previous latency, 
        #it becomes the new maxPipelineLayer
        if(len(prevLayers) == 0):
            self.lat_one_row = self.IP_latency
            g.maxPipelineLayer.append(self)
        else:
            for prevLayer in prevLayers:
                if not isPipelined(prevLayer, self):
                    self.lat_one_row = self.IP_latency
                    g.maxPipelineLayer.append(self)
                elif self.lat_one_row == None:
#                    print "self.IP_latency, prevLayer.computeNRows(S)", self.IP_latency, prevLayer.computeNRows(S)
                    if self.IP_latency > prevLayer.computeNRows(S):
                        g.maxPipelineLayer[-1] = self
                    self.lat_one_row = max(self.IP_latency, prevLayer.computeNRows(S))
                else:
#                    print "self.lat_one_row, prevLayer.computeNRows(S)", self.lat_one_row, prevLayer.computeNRows(S)
                    if self.lat_one_row > prevLayer.computeNRows(S):
                        g.maxPipelineLayer[-1] = self
                    self.lat_one_row = max(self.lat_one_row, prevLayer.computeNRows(S))
#        print "maxPipeline", g.maxPipelineLayer

    def computeNRows(self, n):
        """
        return the latency of the compute n rows
        Args:
            n: int. The number of rows to compute
        return:
            the latency to compute n rows
        """
        assert (self.mappedIP is not None), self.name + " mapped IP is not decided,\
            so no way to compute the latency of n rows"
        assert(self.mappedIP.type is not "Software"), self.name + "mapped IP is software, \
            cannot seperately compute N rows"

        assert (self.lat_one_row != None), "layer " + self.name + "'s lat_one_row is not computed, cannot compute N rows"
        return self.lat_one_row * n

    def computeLatency(self):
        """
        Compute the full latency of this layer using one IP
        """
        assert (self.mappedIP is not None), self.name + " mapped IP is not decided, \
        so no way to compute the latency"

        #The software latency is directly computed from the log file
        if self.mappedIP.type == "Software":
            return

        out_height, out_width = map(int, self.output_params[2:4])

        self.latency = self.computeNRows(out_height)
        
    def set_start_time(self, timeStamp):
        """
        Set the start time of this layer
        Args:
            timeStamp: FP data. The starting time
        """
        self.start_time = timeStamp

class graph:
    """
    The class that contains graph
    Attributes:
        G: The graph
        mapping: A dictionary between the nodes in the graph and a name. This is for drawing the pictures.
        SWMapping: If a layer is mapped to software: A dictionary between the node name and the latency
        exploreLayerQueue: The dictionary. key: The layer type. Value: The list of layers that fall into that category
        original_edges, the list of edges that originally exist (before adding reuse edge)
        original_nodes, the list of nodes that originally exist (before adding pipeline nodes)
        maxPipelineLayer: The list of layers. each element is a layer that is the pipeline bottleneck of its pipeline chain
    """

    def __init__(self, fileName, explore_IP_types):
        """
        Args:
            fileName: Str. The name of the input, contain NN description
        """
        self.G = nx.DiGraph()
        self.mapping = dict()
        self.SWMapping = dict()
        self.exploreLayerQueue = dict()
        self.construct(fileName, explore_IP_types)
        self.original_edges = list(self.G.edges)
        self.original_nodes = list(self.G.nodes)
        self.maxPipelineLayer = []

        self.root = list(self.topological_sort())[0]

    def construct(self, filename, explore_IP_types):
        """
        The function to construct the graph from a file that is dumped from CHaiDNN
        Args:
            filename: the name of the file
        """
        bottom_table = dict()
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
                    bot_str = bot_str[1:-1].split(":")[0]
                    top_str = top_str[1:-1].split(":")[0]

                    layer_str = layer_str[1:-1]
                    layer_tmp = layer(layer_str)

                    if bot_str in bottom_table:
                        bottom_table[bot_str].append(layer_tmp)
                    else:
                        bottom_table[bot_str] = [layer_tmp]
                    if bot_str == "data":
                        layer_tmp.firstLayer = True

                    if top_str in top_table:
                        top_table[top_str].append(layer_tmp)
                    else:
                        top_table[top_str] = [layer_tmp]

                    self.G.add_node(layer_tmp)
                    if layer_tmp.type in explore_IP_types:
                        self.exploreLayerQueue[layer_tmp.type] = [layer_tmp] if layer_tmp.type not in self.exploreLayerQueue else self.exploreLayerQueue[layer_tmp.type] + [layer_tmp]
                    self.mapping[layer_tmp] = layer_tmp.name
            if l.find("--Blobs--") >= 0:
                for l in f:
                    l = l.replace(" ", "")
                    if l == "\n":
                        break
                    blobname, dims =l.split(":")
                    if blobname in bottom_table:
                        for ll in bottom_table[blobname]:
                            ll.set_input_params(dims)
                    if blobname in top_table:
                        for ll in top_table[blobname]:
                            ll.set_output_params(dims)

            if l.find("--Softwarelayerlatency--") >= 0:
                for l in f:
                    if l == "\n":
                        break
                    l = l.replace(" ", "")[0:-1]
                    layer_name, layer_lat = l.split(":")
                    #FIXME: should it be int??
                    self.SWMapping[layer_name] = int(layer_lat)
        f.close()

        #Build Edges
        for bb in bottom_table:
            if bb in top_table:
                for bbb in bottom_table[bb]:
                    for ttt in top_table[bb]:
                        self.G.add_edge(ttt, bbb) 

    def __str__(self):
        """
        The print function of this class
        """
        retStr = " "
        for layer_type in self.exploreLayerQueue:
            Str = layer_type + ": "
            for layer_inst in self.exploreLayerQueue[layer_type]:
                Str += (layer_inst.name+" assigned IP: "+ layer_inst.mappedIP.name + " ")
                Str += ("pipelined? "+ str(layer_inst.Pipelined)+"\n")
            retStr += (Str+"\n")
        return retStr

    def computeLatency(self):
        """
        For each node in the graph, compute the latency and pipelined latency
        """
        node_list = self.topological_sort()
        for n in node_list:
            #If a layer is mapped to software
            if n.name in self.SWMapping: 
                n.set_IP(softwareIP(n.name))
                n.latency = int(self.SWMapping[n.name])
                #FIXME: Software does not have lat_one_row
                #n.lat_one_row = int(self.SWMapping[n.name]) 
            else:
                prevLayers = list(self.G.predecessors(n))
                n.computeLatencyOneRow(prevLayers, self)
                n.computeLatency()

    def printNodeLatency(self):
        for n in self.G.nodes:
            if n.type != "pipeNode":
                print n.name, " ", n.latency, " ", n.lat_one_row
    def printNodeParameters(self, hw_layers):
        for n in self.G.nodes:
            if n.type in hw_layers:
                print n.name, " ", n.params, n.input_params, n.output_params

    def add_node(self, node):
        self.G.add_node(node)
        self.mapping[node] = node.name

    def topological_sort(self):
        """
        Return the list of the node with topological sorting
        """
        return nx.topological_sort(self.G)

    def retriveOriginalGraph(self):
        """
        To resume the original graph which is constructed from the ChaiDNN output graph
        """
        self.G.clear()
        self.G.add_edges_from(self.original_edges)
        self.G.add_nodes_from(self.original_nodes)
        self.maxPipelineLayer = []
        for n in self.G.nodes:
            n.lat_one_row = None
            n.Pipelined = False
            n.start_time = None

    def drawGraph(self):
        h = nx.relabel_nodes(self.G, self.mapping)
        nx.draw(h, with_labels=True, font_weight = 'bold')
        plt.show()

