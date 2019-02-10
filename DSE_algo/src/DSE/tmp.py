def reorderMapping(mapping_solution):
    #For the solution, for each IP collect the mapping, 
    #reassign using the best order
    for g in mapping_solution:
        for n in list(g.nodes):
            if n.type not in hw_layers:
                g.remove_node(n)

    assignOriginalNodeMapping(mapping_solution, hw_layers)

    #Collect the set of IPs for each IP ID
    IPs = dict()
    IPsIdx =  dict()
    for g in mapping_solution:
        for n in g:
            if n.type is "combineNode":
                for m in n.node_list:
                    if m.type in hw_layers:
                        IPName = m.mappedIP.split("_")[0]
                        IPs[IPName] = [m.mappedIP] if IPName not in IPs \
                                      else (IPs[IPName] + [m.mappedIP])
    #initialize idx
    for IPName in IPs:
        IPsIdx[IPName] = 0

    #Reassign IP
    for g in mapping_solution:
        #clear idx
        for IPName in IPsIdx:
            IPsIdx[IPName] = 0

        for n in mapping_solution[g]:
            if n.type is "combineNode":
                for m in n.node_list:
                    if m.type in hw_layers:
                        IPName = m.mappedIP.split("_")[0]
                        m.mappedIP = IPs[IPName][IPsIdx[IPName]]
                        IPsIdx[IPName] += 1
            if n.type in hw_layers:
                n.mappedIP = IPs[IPName][IPsIdx[IPName]]
                IPsIdx[IPName] += 1


