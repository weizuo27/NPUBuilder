class IPSel():
    def __init__(self, BRAM_budget, DSP_budget, FF_budget, BW_budget, Lat_budget, numIPs, 
            app_fileName, IP_fileName, ESP, rowStep):

        status = "Undecided"

        hw_layers = {}

        explore_IP_types = {}

        gs = graph(app_fileName, explore_IP_types, rowStep)

        IPs = generateIPs(IP_fileName)

        IP_table = constructIPTable(IPs, BRAM_budget, 
                DSP_budget, LUT_budget, gs.explore_IP_types, explore_IP_types, numIPs)

