import networkx as nx

def readLayerId(fileName):
    layerIdxTable = dict()
    f = open(fileName)
    for l in f:
        layer, idx = l.replace(" ", "").strip().split(":")
        layerIdxTable[layer] = idx
    f.close()
    return layerIdxTable

def CSVconfig(n, ip_inst, s, t, idle, layerIdxTable,poolingTypeTable, muxSel):
    if ip_inst.type == "Convolution":
        ip_inst.CSVparameterList.append(idle)
        if(not ip_inst.necessaryHasSet):
            #XI_KER_PROC
            weight = (2 + 2 * (ip_inst.paramList[0] > 8)  == 4)
            Out = ip_inst.memOutFlag
            In = ip_inst.memInFlag
            In1st = n.firstLayer
            idx = layerIdxTable[n.name]
            ip_inst.CSVparameterList += [weight, Out, In, In1st, idx]
            ip_inst.necessaryHasSet = True
        if(idle):
            None
            streamIn = False
            streamIn = False
        else:
            streamIn = (n == t)
            streamOut = (n == s)
        ip_inst.CSVparameterList += [streamIn, streamOut]

    elif ip_inst.type == "Convolution_g":
        groupNums = 2 #FIXME: Hard coded group num
        for i in range(groupNums):
            if(not ip_inst.necessaryHasSet):
                weight = (2 + 2 * (ip_inst.paramList[0] > 8)  == 4)

                Out = ip_inst.memOutFlag
                In = ip_inst.memInFlag

                In1st = n.isFirstLayer()
                idx = layerIdxTable[n]
                ip_inst.CSVparameterList += [weight, Out, In, In1st, idx]
            if(idle):
                None
            else:
                streamIn = (n == t)
                streamOut = (n == s)
                n.CSVparameterList += [streamIn, streamOut]
        ip_inst.necessaryHasSet = True

    elif ip_inst.type == "Pooling":
        ip_inst.CSVparameterList.append(idle)
        if(not ip_inst.necessaryHasSet):
            byPass = False
            streamIn = (n == t)
            streamOut = (n == s)
            In = ip_inst.memInFlag
            Out = ip_inst.memOutFlag
            Avg = (poolingTypeTable[n.name] == "avg")
            ip_inst.CSVparameterList += [byPass, streamIn, streamOut, In, Out, Avg]

    elif "MUX" in ip_inst.type:
        if not muxSel:
            return
        preIdx = layerIdxTable[s.name]
        ip_inst.CSVparameterList = [preIdx, muxSel]

def genCSVConfigs(gs, IP_g, muxSelTable):
    layerIdxTable = readLayerId( "./inputFiles/layerIDMapping")
    poolingTypeTable = readLayerId("./inputFiles/PoolingTyping")
    for g in gs:
        for s, t in g.edges():
            ip_s = s.mappedIP
            ip_t = t.mappedIP
            ips = list(nx.bellman_ford_path(IP_g, ip_s, ip_t))
            print "from", s.name, "to", t.name, "path is "
            for ip in ips:
                print ip.name
            for idx, ip_inst in enumerate(ips):
                if ip_inst == ip_s:
                    n = s
                elif ip_inst == ip_t:
                    n = t
                else:
                    n = None
                if idx == 0:
                    muxSel =None 
                else:
                    muxSel = None if (ips[idx-1], ip_inst) not in muxSelTable else muxSelTable[(ips[idx-1], ip_inst)]
                CSVconfig(n, ip_inst, s, t, False, layerIdxTable, poolingTypeTable,  muxSel)

#print ip_inst.name, ip_inst.CSVparameterList

    #for IPs that are not configed in this round, 
    #need to set idle.
