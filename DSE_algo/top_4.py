import os
import sys
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path + "/src/DSE");

import argparse
from IPSel_ILP_gurobi_4 import IPSel

parser = argparse.ArgumentParser()
parser.add_argument('BRAM_budget', type=int, help= "Interger for description of BRAM budget")
parser.add_argument('DSP_budget', type=int, help= "Interger for description of DSP budget")
parser.add_argument('LUT_budget', type=int, help= "Interger for description of LUT budget")
parser.add_argument('FF_budget', type=int, help= "Interger for description of Flip-flop budget")
parser.add_argument('BW_budget', type=int, help= "Interger for description of bandwidth budget")
parser.add_argument('latency_budget', type=int, help= "Interger for description of latency budget")
parser.add_argument("app_fileName", type=str, help= "The file name of the graph dumpped from ChaiDNN")
parser.add_argument("IP_fileName", type=str, help= "The file name of the graph dumpped from ChaiDNN")
parser.add_argument("numOtherIPs", type=int, help= "The total number of IPs other than Conv or convG IPs, integer")
#parser.add_argument("numConvIPs", type=int, help= "The total number of conv IPs, integer")
parser.add_argument("batchSize", type=int, help= "number of batch, integer")
parser.add_argument("fixedRowStep", type=int, help = "0: No (then the algorithm picks the biggest rowstep). 1: Yes, then user specify rowStep")
parser.add_argument("RowStep", type=int, help="If fixedRowStep is 1, then user specify rowstep here. Otherwise, this option will be ignored")
parser.add_argument("manualSetingConvIPbound", type=int, help="0: let the DSE tool explore all possbile number of conv IPs, 1: use the \"convIPUb\" and \"convIPlb\" arguments to set the lower\
         and upper bounds, this is to reduce the runtime")
parser.add_argument("convIPlb", type=int, help="The min number of convIP that is exploring")
parser.add_argument("convIPUb", type=int, help="The max number of convIP that is exploring")

#parser.add_argument("DSE", type=int, help= "Whether run DSE or just heuristic for unconstraint case")


args = parser.parse_args()

BRAM_budget = args.BRAM_budget
DSP_budget = args.DSP_budget
LUT_budget = args.LUT_budget
FF_budget = args.FF_budget
BW_budget = args.BW_budget
latency_budget = args.latency_budget
app_fileName = args.app_fileName
IP_fileName = args.IP_fileName
numOtherIPs= args.numOtherIPs
#numConvIPs = args.numConvIPs
batchSize = args.batchSize
fixedRowStep = args.fixedRowStep
manualSetingConvIPbound = args.manualSetingConvIPbound
convIPUb = args.convIPUb
convIPlb = args.convIPlb

if(not fixedRowStep):
    RowStep = 2
else:
    RowStep = args.RowStep

assert args.fixedRowStep < 2, "fixedRowStep can only be 0 (False) or 1 (True)"
#assert (args.DSE < 2), "herusitic can only be 0 (False) or 1 (True)"
#DSE = args.DSE == 1
#assert(args.assumptionLevel < 3), "assumptionLevel can only be 0, 1, 2"
#assumptionLevel = args.assumptionLevel


#opt = optimizer(BRAM_budget, DSP_budget, FF_budget, LUT_budget, BW_budget, latency_budget, app_fileName, IP_fileName, pipelineLength, 5000, DSE, assumptionLevel)
ipsel = IPSel()

opt = False
updateRowStep = False
f = open("./outputFiles/hw/rowSteps", "w")
f.close()
lat_achieved_total_old = latency_budget
while(not opt):
    lat_achieved_total = ipsel.run(BRAM_budget, DSP_budget, FF_budget, LUT_budget, BW_budget, latency_budget, numOtherIPs,\
    app_fileName, IP_fileName, 2000, RowStep, batchSize, fixedRowStep, updateRowStep, manualSetingConvIPbound, convIPlb, convIPUb, lat_achieved_total_old)
    break	
    updateRowStep = True
    print "Old is ", lat_achieved_total_old, "new is ", lat_achieved_total
    if lat_achieved_total > lat_achieved_total_old - 2000:
        print "new one is slower. "
        break
    lat_achieved_total_old = lat_achieved_total

