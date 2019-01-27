def addViolationPaths(self, violation_path, layerQueue, IP_table, layerIPLatencyTable):
    if(self.status == "Failed"):
        return

    violate_layers = dict()

    all_violate_IPs = dict()


#for each violate layer, collect the IPs that are smaller than this latency
    #For each layer, collect the IPs that have larger latency than current latency
    for l in voilation_path:


    for l, mappedIP in violation_path:
        if mappedIP not in violate_layer
