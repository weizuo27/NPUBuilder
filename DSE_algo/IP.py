#The class of IP
import os
import sys
from math import ceil
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path + "/../latency_estimation");
#from lat_estimate import computeLatency
#from lat_estimate import computeLatency_pooling
#from lat_estimate import computeLatency_eltwise

from latencyEstimation_new import computeLatency
from latencyEstimation_new import computeLatency_pooling
from latencyEstimation_new import computeLatency_eltwise

class IP():
    """
    The class that describes the IP 
    Attrs:
        type: The type of the IP
        BRAM, DSP, FF, LUT: The number of resources consumed by this IP
        orig_name: String. The original name of the IP. Since IP later can
        be renamed, we would like to record the original name also
    """
    def __init__(self, name, type, resource_list, 
            #The following are chaiDNN conv specific configs
            paramList):
        self.name = str(name)
        self.type = str(type)
        self.orig_name = str(name)
        if resource_list != None:
            self.BRAM, self.DSP, self.FF, self.LUT = map(int, resource_list)
        if paramList != None:
            self.paramList =map(int, paramList)

    #This actually needs to be overide by different IP types
    #This function should give latency of the using the IP with a 
    #sepcified application dimensions
    def computeLatency(self, paramList, 
            in_height, in_width, 
            out_height, out_width, rowStep,
            isFirstLayer, layerBandWidth = None, totalBandWidth=None
            ):
        """
        Based on the passed-in list, can compute the latency
        Args:
            paramList: The list of parameters representing the dimension of one layer
                if type is Convolution, the list is [cout, cin, kw, kh, S, padding, group]
                if type is Pool: list is [N, kh, S, P]
            in_height: The input height
            in_width : The input width
            out_height: The output height
            out_width: The output width
        Return:
            The latency
        """
#        totalBandWidth = None
        if self.type == "Convolution" or self.type == "Convolution_g":
            cout, cin, kw, kh, S, padding, group = paramList

            XI_KER_PROC, XI_PIX_PROC, XI_IBUFF_DEPTH, \
            XI_OBUFF_DEPTH, XI_WEIGHTBUFF_DEPTH = self.paramList

            layerID = 0 if isFirstLayer else 1

            AXILatency = None if totalBandWidth == None else int(float(totalBandWidth)/layerBandWidth)

            if(ceil(float(cin)/4) * ceil(float(cout)/XI_KER_PROC) * kh * kw <= XI_WEIGHTBUFF_DEPTH * 2):
                oneTime = True
            else:
                oneTime = False

            lat = computeLatency(
                    int(in_height),
                    int(in_width), 
                    int(out_height), 
                    int(out_width),
#                    int(cout/group),
                    int(cout),
                    int(cin), 
                    int(S), int(kh), int(kw), int(padding),
                    int(int(group) > 1),  #group
                    rowStep,
                    int(XI_KER_PROC),
                    int(XI_PIX_PROC),
                    int(XI_WEIGHTBUFF_DEPTH),
                    True,
                    layerID, 
                    AXILatency, 
                    oneTime
                    )
            return lat
        elif self.type == "Pooling":
            
            odepth = int(paramList[0])
            kw = kh = int(paramList[1])

            return computeLatency_pooling(out_width, kw, kh, odepth, True)

        elif self.type == "Eltwise":
            cout, cin, kw, kh, S, padding, group = paramList
            return computeLatency_eltwise(out_width, cout)

    def __str__(self):
        return "name: "+str(self.name)\
#        +" Type: "+str(self.type)+" BRAM: "+str(self.BRAM)+" DSP: "+ \
#        str(self.DSP)+" FF: "+str(self.FF)+" LUT: "+str(self.LUT)

class softwareIP:
    def __init__(self, name):
        self.type = "Software"
        self.name = name
