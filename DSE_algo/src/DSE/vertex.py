from utils_4 import *
from copy import deepcopy
import networkx as nx
#import cvxpy as cvx
from IP import softwareIP
from math import ceil
import os
import sys
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path + "/../latency_estimation");
from infoClass import layerInfo_t

class vertex:
    def __init__(self):
        self.name = None
        self.type = None
        self.pipeLatency = None
	self.orgLatency = None
        self.ID = None
    def computeLatency(self):
        None

class pipeNode(vertex):
    """
    The node inserted to account for the pipeline structure
    """
    idx = 0
    def __init__(self, neg_latency):
        vertex.__init__(self)
        self.name = "pipeNode" + str(pipeNode.idx)
        self.type = "pipeNode"
        pipeNode.idx+=1
	assert(neg_latency < 0), "pipeline node should have neg latency"
        self.pipeLatency = self.orgLatency = neg_latency

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
    def __init__(self, line, layerIdxTable):
        #All attributes are first initialized here
        vertex.__init__(self)
        n_t = line.split(":")[0]
        self.name, self.type = n_t.split("-")
        self.layerInfo = layerInfo_t()
        self.layerInfo.type = self.type
        self.mappedIP = None
        self.firstLayer = False
        self.output_params = None
        self.layerInfo.ID = int(layerIdxTable[self.name])
        params = line.split(":")[1].split(";")
        if self.type == "Convolution" or self.type == "Convolution_g":
            self.layerInfo.out_planes, self.layerInfo.inp_planes, self.layerInfo.filter_width, self.layerInfo.filter_height =\
            map(int, (params[0].split("=")[1]).split("x")) 
            self.layerInfo.stride = int(params[1].split("=")[1])
            self.layerInfo.pad = int(params[2].split("=")[1])
            self.layerInfo.groupFlag = (int(params[4].split("=")[1]) > 1)

        elif self.type == "Pooling":
            self.layerInfo.out_planes= self.layerInfo.inp_planes = int(params[1].split("=")[1])
            self.layerInfo.stride = int(params[3].split("=")[1])
            self.layerInfo.pad = int(params[4].split("=")[1])

        elif self.type == "Eltwise":
            self.layerInfo.out_planes, self.layerInfo.inp_planes, \
            self.layerInfo.filter_width, self.layerInfo.filter_height = map(int, (params[0].split("=")[1]).split("x"))
            self.layerInfo.stride = int(params[1].split("=")[1])
            self.layerInfo.pad = int(params[2].split("=")[1])
            self.layerInfo.groupFlag = (int(params[4].split("=")[1]) > 1)
        else: 
            assert(0), "Unsupported layer type"

    def set_IP(self, IP):
        self.mappedIP = IP

    def set_input_params(self, line):
        assert( self.layerInfo.inp_height is None and
               self.layerInfo.inp_width is None), "layerInfo of inputs is already set"
        input_params = map(int,line.split("x")) #[batch, channel, height, width]
        assert(len(input_params) == 4), "The input params length is not 4"
        self.layerInfo.inp_height, self.layerInfo.inp_width = input_params[2:]

    def set_output_params(self, line):
        assert(self.layerInfo.out_height is None and self.layerInfo.out_width is None), "layerInfo of output is already set"
        output_params = map(int,line.split("x")) #[batch, channel, height, width]
        assert(len(output_params) == 4), "The output params length is not 4"
        self.layerInfo.out_height, self.layerInfo.out_width = output_params[2:]

    def computeLatencyIfMappedToOneIP(self, ip, totalBandwidth = None):
        """
        Compute the latency if the layer is mapped to one IP.
        """
        assert(ip.type == self.type), "The type of IP and layer do not match."
        #This part need to hard code for different layer type
        latency = ip.computeLatencyDSP(self.layerInfo)
        return latency

    def computeLatency(self):
        """
        Compute the full latency of this layer using one IP
        """
        assert (self.mappedIP is not None), self.name+" mapped IP is not decided, so no way to compute the latency"
        self.latency = self.computeLatencyIfMappedToOneIP(self.mappedIP)
