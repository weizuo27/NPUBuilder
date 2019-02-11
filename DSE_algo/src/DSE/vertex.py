from utils_4 import *
import matplotlib.pyplot as plt
from copy import deepcopy
import networkx as nx
#import cvxpy as cvx
from IP import softwareIP
from math import ceil

class vertex:
    """
        Base class for vertex class
        Attrs:
            name:
            type:
            latency:
            lat_one_row:
    """
    def __init__(self):
        self.name = None
        self.type = None
        self.latency = None
        self.lat_rowStep = None 
        self.Pipelined = False
        self.bandWidth = 0

    def computeLatency(self):
        None

    def computeLatencyRowStep(self, g, totalBandwidth):
        None

    def computeNRows(self,n):
        None

class combineNode(vertex):
    def __init__(self, node_list):
        vertex.__init__(self)
        self.type = "combineNode"
        self.name = ""
        self.node_list = node_list
        for n in node_list:
            self.name += n.name + "_"
    def computeLatency(self):
        tmp = 0
        for n in self.node_list:
            tmp += n.latency
        self.latency = tmp

        self.removePipeNode()
    def removePipeNode(self):
        path_tmp = [ x for x in self.node_list if x.type !="pipeNode"]
        self.node_list = path_tmp



class pipeNode(vertex):
    """
    The node inserted to account for the pipeline structure
    """
    idx = 0
    def __init__(self, neg_latency):
        self.name = "pipeNode" + str(pipeNode.idx)
        self.type = "pipeNode"
        pipeNode.idx+=1
        self.latency = neg_latency

class blob(vertex):
    """
        The blob type vertex, which is the input/output of one layer
    """
    def __init__(self, name):
        vertex.__init__(self)
        self.type = "blobNode"
        self.name = name

    def computeLatency(self):
        self.latency = 0

class layer(vertex):
    def __init__(self, line, rowStep, layerIdxTable):
        """
        The class to describe one layer
        Attrs:
            name: The name of the layer
            type: The type of the layer
            params: The parameter list of the layers, according to different type, the list
            has different interpretation.

        """
        #All attributes are first initialized here
        self.bandWidth = 0
        n_t = line.split(":")[0]
        self.name, self.type = n_t.split("-")
        self.mappedIP = None
        self.firstLayer = False
        self.Pipelined = False
        self.IP_latency_rowStep = None
        self.lat_rowStep = None
        self.start_time = None
        self.input_params = None
        self.output_params = None
        self.isMaxPipeLayer = False
        self.ID = int(layerIdxTable[self.name])
        #FIXME: Hardcoded???
        if self.type == "Convolution" or self.type == "Convolution_g":
            self.rowStep = rowStep
        else:
            self.rowStep = 1

        if(self.type == "XPack Layer"):
            self.params = line.split(":")[2]
        else:
            self.params = line.split(":")[1].split(";")
#            self.ID = int(self.params.pop().split("=")[1])
            
    def set_IP(self, IP):
        """
        set the mapped IP for this layer
        Args:
            IP: The object IP. The IP this layer is mapped to.
        """
        self.mappedIP = IP
        if self.type == "Convolution"or self.type == "Convolution_g":

            cout, cin, kw, kh = map(int, (self.params[0].split("=")[1]).split("x")) 
            out_height, out_width = map(int, self.output_params[2:4])

            XI_KER_PROC, XI_PIX_PROC, XI_IBUFF_DEPTH, \
                XI_OBUFF_DEPTH, XI_WEIGHTBUFF_DEPTH = IP.paramList

            if(ceil(float(cin)/4) * ceil(float(cout)/XI_KER_PROC) * kh * kw <= XI_WEIGHTBUFF_DEPTH * 2):
                self.bandWidth = cin * cout * kh * kw
            else:
                self.bandWidth = cin * cout * kh * kw * (float(out_height)/self.rowStep)

    def set_input_params(self, line):
        """
        The function sets the input parameters
        """
        if self.type == "Convolution" or self.type == "Convolution_g":
            cout, cin, kw, kh = map(int, (self.params[0].split("=")[1]).split("x")) 
        elif self.type == "Pooling":
            cout=cin = int(self.params[1].split("=")[1])
        elif self.type == "Eltwise":
            cout, cin, kw, kh = map(int, (self.params[0].split("=")[1]).split("x"))

        self.input_params = map(int,line.split("x")) #[batch, channel, height, width]
        self.input_params[1] = int(cin)

    def set_output_params(self, line):
        """
        The function sets the output parameters
        """
        if self.type == "Convolution" or self.type == "Convolution_g":
            cout, cin, kw, kh = map(int, (self.params[0].split("=")[1]).split("x")) 
        elif self.type == "Pooling":
            cout=cin = int(self.params[1].split("=")[1])
        elif self.type == "Eltwise":
            cout, cin, kw, kh = map(int, (self.params[0].split("=")[1]).split("x"))

        self.output_params = map(int,line.split("x")) #[batch, channel, height, width]
        self.output_params[1]=int(cout)

    def computeLatencyIfMappedToOneIP(self, ip, totalBandwidth = None):
        """
        Compute the latency if the layer is mapped to one IP.
        Args:
            ip: The ip that the layer is mapped to.
            ret: Int, the latency cycle to compute this layer
        """
        assert(ip.type == self.type), "The type of IP and layer do not match."
        in_height, in_width = map(int, self.input_params[2:4])
        out_height, out_width = map(int, self.output_params[2:4])

        #This part need to hard code for different layer type
        if self.type == "Convolution"or self.type == "Convolution_g":
            cout, cin, kw, kh = map(int, (self.params[0].split("=")[1]).split("x"))
            S = int(self.params[1].split("=")[1])
            padding = int(self.params[2].split("=")[1])
            group = int(self.params[4].split("=")[1])

            #Assumption: Now here we do not consider the warm-up phase of computation.
            #E.g., a convolution. Stride =4, kh =11. For the first output row, it needs
            #to compute 11 input rows, but for the remaining rows,  it only need 4.  #We neglect the first row, and assume that one output row requires 4 input row.

#            if totalBandwidth:
#                print "total111 ", totalBandwidth, self.name, self.type, self.bandWidth
#            print "total222 ", totalBandwidth, self.name, self.type, self.bandWidth

            print self.name
            latency_rowStep = ip.computeLatency(
                    [cout, cin, kw, kh, S, padding, group],
                    in_height, 
                    in_width, 
                    out_height, 
                    out_width,
                    self.rowStep,
                    self.firstLayer, 
                    self.bandWidth,
                    totalBandwidth 
                    )

        elif self.type == "Pooling":
            PoolType = self.params[0].split("=")[1]
            N = int(self.params[1].split("=")[1])
            kw = kh = int(self.params[2].split("=")[1])
            S = int(self.params[3].split("=")[1])
            P = int(self.params[4].split("=")[1])

            latency_rowStep = ip.computeLatency(
                    [N,kh,S,P], 
                    in_height, 
                    in_width, 
                    out_height, 
                    out_width, 
                    self.rowStep,
                    self.firstLayer)
        elif self.type == "Eltwise":
            cout, cin, kw, kh = map(int, (self.params[0].split("=")[1]).split("x"))
            S = int(self.params[1].split("=")[1])
            padding = int(self.params[2].split("=")[1])
            group = int(self.params[4].split("=")[1])

            latency_rowStep = ip.computeLatency(
                    [cout, cin, kw, kh, S, padding, group],
                    in_height, 
                    in_width, 
                    out_height, 
                    out_width,
                    self.rowStep,
                    self.firstLayer)

        else: 
            assert(0), "Unsupported layer type"

        return latency_rowStep * (float(out_height)/self.rowStep)

    def computeLatencyRowStep(self, prevLayers, totalBandwidth):
        """
        The latency to compute one row
        Args:
            prevLayers: the list of previous layers
        """
        assert (self.mappedIP is not None), self.name + " mapped IP is not decided,\
            so no way to compute the latency"

        if self.mappedIP == "Software":
            return

        out_height, out_width = map(int, self.output_params[2:4])
        self.IP_latency_rowStep = self.computeLatencyIfMappedToOneIP(self.mappedIP, totalBandwidth)/(float(out_height)/self.rowStep)

        #This part need to hard code for different layer type
        if self.type == "Convolution"or self.type == "Convolution_g":
            cout, cin, kw, kh = map(int, (self.params[0].split("=")[1]).split("x"))
            S = int(self.params[1].split("=")[1])
            padding = int(self.params[2].split("=")[1])
            group = int(self.params[4].split("=")[1])

        elif self.type == "Pooling":
            PoolType = self.params[0].split("=")[1]
            N = int(self.params[1].split("=")[1])
            kw = kh = int(self.params[2].split("=")[1])
            S = int(self.params[3].split("=")[1])
            P = int(self.params[4].split("=")[1])

        elif self.type == "Eltwise":
            S = 1

        #Now start computing the latency for computing one row

        #If the current layer is the starting of a pipeline chain, the maxPipeilneLayer for this
        #chain is itself. Otherwise, if one layer's latency is bigger than the previous latency, 
        #it becomes the new maxPipelineLayer

        if(len(prevLayers) == 0):
            self.lat_rowStep = self.IP_latency_rowStep
#            self.isMaxPipeLayer = True
#            maxPipelineLayer.append(self)

        else:
            for prevLayer in prevLayers:
                if not isPipelined(prevLayers, self):
                    self.lat_rowStep = self.IP_latency_rowStep
#                    self.isMaxPipeLayer = True
#                    maxPipelineLayer.append(self)
                elif self.lat_rowStep == None:
#                    if self.IP_latency_rowStep > prevLayer.computeNRows(S):
#                        self.isMaxPipeLayer = True
#                        maxPipelineLayer[-1] = self
                    self.lat_rowStep = max(self.IP_latency_rowStep, prevLayer.computeNRows(S*self.rowStep))
                        
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

        assert (self.lat_rowStep != None), "layer " + self.name + "'s lat_one_row is not computed, cannot compute N rows"
        return self.lat_rowStep * (float(n)/self.rowStep)

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

