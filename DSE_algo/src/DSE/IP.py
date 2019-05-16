#The class of IP
import os
import sys
from math import ceil
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path + "/../latency_estimation");
from latencyEstimation_new import computeLatencyDSP
from infoClass import IPinfo_t

class IP():
    """
    The class that describes the IP 
    Attrs:
        type: The type of the IP
        BRAM, DSP, FF, LUT: The number of resources consumed by this IP
        orig_name: String. The original name of the IP. Since IP later can
        be renamed, we would like to record the original name also
    """
    def __repr__(self):   
        return "IP-"+self.name

    def __init__(self, name, type, resource_list, 
            #The following are chaiDNN conv specific configs
            paramList, numIPs, firstLayer = False):
        self.idle = 1
        self.name = str(name)
        self.type = str(type)

        self.IPinfo = IPinfo_t()

        self.orig_name = str(name)
        self.csvUneceNums = 0
        self.firstLayer = firstLayer
        self.numIPs = numIPs
        self.DSP = 0
        self.layerID = None
        #Init IPinfo
        self.IPinfo.IPtype = self.type
        #The followings are used to generate csv
        self.ip_l = None
        if self.type == "Convolution":
            self.csvUneceNums = 4
        elif self.type == "Convolution_g":
            self.csvUneceNums = 4
        elif "MUX" in self.type:
            self.csvUneceNums = 5
        elif self.type == "Pooling":
            self.csvUneceNums = 6
        elif self.type == "Eltwise":
            self.csvUneceNums = 5
        if 1:
            self.CSVparameterListUnNece = self.csvUneceNums * [0]
            if(self.csvUneceNums > 0):
                self.CSVparameterListUnNece[0] = 1
        self.CSVparameterListNecessary = []
        self.memInFlag = False
        self.memOutFlag = False
        self.necessaryHasSet = False
        ################
        if resource_list != None:
            self.IPinfo.K_x_P, self.DSP, _, _= map(int, resource_list)
        if paramList != None:
            self.paramList =map(int, paramList)

    def resetForCSVUnNece(self):
        if 1:
            self.CSVparameterListUnNece = self.csvUneceNums * [0]
            self.idle = 1
            self.layerID = None
            if(self.csvUneceNums > 0):
                self.CSVparameterListUnNece[0] = 1

    #This actually needs to be overide by different IP types
    #This function should give latency of the using the IP with a 
    #sepcified application dimensions
    def computeLatencyDSP(self, layerInfo):
        return computeLatencyDSP(layerInfo, self.IPinfo)
	
    def __str__(self):
        return "name: "+str(self.name)\
#        +" Type: "+str(self.type)+" BRAM: "+str(self.BRAM)+" DSP: "+ \
#        str(self.DSP)+" FF: "+str(self.FF)+" LUT: "+str(self.LUT)

class softwareIP:
    def __init__(self, name):
        self.type = "Software"
        self.name = name
