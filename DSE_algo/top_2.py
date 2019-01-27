import argparse
#from optimizer import optimizer
from optimizer_gurobi_3 import optimizer

parser = argparse.ArgumentParser()
parser.add_argument('BRAM_budget', type=int, help= "Interger for description of BRAM budget")
parser.add_argument('DSP_budget', type=int, help= "Interger for description of DSP budget")
parser.add_argument('LUT_budget', type=int, help= "Interger for description of LUT budget")
parser.add_argument('FF_budget', type=int, help= "Interger for description of Flip-flop budget")
parser.add_argument('BW_budget', type=int, help= "Interger for description of bandwidth budget")
parser.add_argument('latency_budget', type=int, help= "Interger for description of latency budget")
parser.add_argument("app_fileName", type=str, help= "The file name of the graph dumpped from ChaiDNN")
parser.add_argument("IP_fileName", type=str, help= "The file name of the graph dumpped from ChaiDNN")
parser.add_argument("pipelineLength", type=int, help= "The number of pipeline stages (IPs)")
parser.add_argument("DSE", type=int, help= "Whether run DSE or just heuristic for unconstraint case")
parser.add_argument("assumptionLevel", type=int, help= "The pre-defined assumption level")


args = parser.parse_args()

BRAM_budget = args.BRAM_budget
DSP_budget = args.DSP_budget
LUT_budget = args.LUT_budget
FF_budget = args.FF_budget
BW_budget = args.BW_budget
latency_budget = args.latency_budget
app_fileName = args.app_fileName
IP_fileName = args.IP_fileName
pipelineLength = args.pipelineLength
assert (args.DSE < 2), "herusitic can only be 0 (False) or 1 (True)"
DSE = args.DSE == 1
assert(args.assumptionLevel < 3), "assumptionLevel can only be 0, 1, 2"
assumptionLevel = args.assumptionLevel


opt = optimizer(BRAM_budget, DSP_budget, FF_budget, LUT_budget, BW_budget, latency_budget, app_fileName, IP_fileName, pipelineLength, 5000, DSE, assumptionLevel)


