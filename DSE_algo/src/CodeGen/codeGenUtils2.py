import networkx as nx

def readLayerId(fileName):
    layerIdxTable = dict()
    f = open(fileName)
    for l in f:
        layer, idx = l.replace(" ", "").strip().split(":")
        layerIdxTable[layer] = idx
    f.close()
    return layerIdxTable

def CSVconfigNece(n, ip_inst):
    if ip_inst.type == "Convolution":
        if(not ip_inst.necessaryHasSet):
            weight = int(2 + 2 * (ip_inst.paramList[0] > 8)  == 4)
            Out = int(ip_inst.memOutFlag)
            In = int(ip_inst.memInFlag)
            In1st = int(n.firstLayer)
            ip_inst.CSVparameterListNecessary += [weight, Out, In, In1st, ip_inst.name]
    if ip_inst.type == "Convolution_g":
        groupNums = 2 #FIXME: Hard coded group num
        for i in range(groupNums):
            if(not ip_inst.necessaryHasSet):
                weight = int(2 + 2 * (ip_inst.paramList[0] > 8)  == 4)
                Out = int(ip_inst.memOutFlag)
                In = int(ip_inst.memInFlag)
                In1st = int(n.firstLayer)
                ip_inst.CSVparameterListNecessary.append([weight, Out, In, In1st, ip_inst.name])
    if ip_inst.type == "Pooling":
        if(not ip_inst.necessaryHasSet):
            In = int(ip_inst.memInFlag)
            Out = int(ip_inst.memOutFlag)
            ip_inst.CSVparameterListNecessary += [In, Out, ip_inst.name]
            ip_inst.necessaryHasSet = True
    if ip_inst.type == "MUX":
        None
    ip_inst.necessaryHasSet = True

def CSVconfigUnNece(n, ip_inst, s, t, idle, layerIdxTable,poolingTypeTable, muxSel):
    if ip_inst.type == "Convolution":
        ip_inst.CSVparameterListUnNece[0] = int(idle)
        if n == t:
            ip_inst.CSVparameterListUnNece[1] = 1 #in
        if n == s:
            ip_inst.CSVparameterListUnNece[2] = 1 #out
        layerIdx = layerIdxTable[n.name]
        ip_inst.CSVparameterListUnNece[3] = layerIdx

    elif ip_inst.type == "Convolution_g":
        groupNums = 2 #FIXME: Hard coded group num
        for i in range(groupNums):
            ip_inst.CSVparameterListUnNece[i][0] = int(idle)
            if n == t:
                ip_inst.CSVparameterListUnNece[i][1] = 1 #in
            if n == s:
                ip_inst.CSVparameterListUnNece[i][2] = 1 #out
            layerIdx = layerIdxTable[n.name]
            ip_inst.CSVparameterListUnNece[i][3] = layerIdx

    elif ip_inst.type == "Pooling":
        ip_inst.CSVparameterListUnNece[0] = int(idle)
        if n == t:
            ip_inst.CSVparameterListUnNece[1] = 1 #in
        if n == s:
            ip_inst.CSVparameterListUnNece[2] = 1 #out
        layerIdx = layerIdxTable[n.name]
        byPass = int(False)
        Avg = int((poolingTypeTable[n.name] == "avg"))
        ip_inst.CSVparameterListUnNece[3:5] = [byPass, Avg]
        ip_inst.CSVparameterListUnNece[5] = layerIdx

    elif "MUX" in ip_inst.type:
        if(not idle):
            preIdx = layerIdxTable[s.name]
            preLayerType = s.type
            ip_inst.CSVparameterListUnNece = [int(idle), muxSel, preIdx, preLayerType]
        else:
            ip_inst.CSVparameterListUnNece = [1, 0, -1,"X"]
        print "abc", ip_inst.name, ip_inst.CSVparameterListUnNece

def genCSVConfigs(gs, IP_g, muxSelTable, hw_layers):
        
    layerIdxTable = readLayerId( "./inputFiles/layerIDMapping")
    poolingTypeTable = readLayerId("./inputFiles/PoolingTyping")
    #reorder the gs
    gs_list = gs.keys()

    #reorder the graph
    def comp(elem):
        for n in elem.nodes():
            if n.type in hw_layers:
                return n.ID

    gs_list.sort(key = comp)

    #Config all the necessary columns
    for g in gs_list:
        for n in g.nodes():
            CSVconfigNece(n, n.mappedIP)

    #Config all the changable colums
    for g in gs_list:
        for s, t in g.edges():
            ip_s = s.mappedIP
            ip_t = t.mappedIP
            ips = list(nx.bellman_ford_path(IP_g, ip_s, ip_t))
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
                    if "MUX" in ip_inst.type:
                        if (ip_inst, (ips[idx-1], ip_inst)) in muxSelTable:
                            muxSel = muxSelTable[(ip_inst, (ips[idx-1], ip_inst))]
                        elif(ip_inst, (ip_inst, ips[idx+1]))in muxSelTable:
                            muxSel = muxSelTable[(ip_inst, (ip_inst, ips[idx+1]))]
                    else:
                         muxSel == None

                CSVconfigUnNece(n, ip_inst, s, t, False, layerIdxTable, poolingTypeTable,  muxSel)

        genCSVFile(IP_g)
        
        # reset the network
        for ip_inst in IP_g.nodes():
            print "before", ip_inst.name, ip_inst.CSVparameterListUnNece
            ip_inst.resetForCSVUnNece()
            print "after", ip_inst.name, ip_inst.CSVparameterListUnNece

def genCSVFile(IP_g):
    f = open("round.csv", "a")
    csvParamList = []
    for ip_inst in IP_g.nodes():
        csvParamList.append(ip_inst.type)
        if ip_inst.type == "Convolution_g":
            for i in range(2):
                csvParamList += (ip_inst.CSVparameterListNecessary[i] + ip_inst.CSVparameterListUnNece[i])
        else:
            csvParamList += (ip_inst.CSVparameterListNecessary + ip_inst.CSVparameterListUnNece)
    print "csvParamList", csvParamList
    line = ",".join(map(str, csvParamList))
    line += "\n"
    f.write(line)
    f.close()
