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
    if ip_inst.type == "Convolution" or ip_inst.type == "Convolution_g":
        if(not ip_inst.necessaryHasSet):
            weight = int(2 + 2 * (ip_inst.paramList[0] > 8)  == 4)
            Out = int(ip_inst.memOutFlag)
            In = int(ip_inst.memInFlag)
            In1st = int(n.firstLayer)
            ipName  = ip_inst.name.split("_")[0]
            ip_inst.CSVparameterListNecessary += [weight, Out, In, In1st, ipName]
#    elif ip_inst.type == "Convolution_g":
#        groupNums = 2 #FIXME: Hard coded group num
#        for i in range(groupNums):
#            if(not ip_inst.necessaryHasSet):
#                weight = int(2 + 2 * (ip_inst.paramList[0] > 8)  == 4)
#                Out = int(ip_inst.memOutFlag)
#                In = int(ip_inst.memInFlag)
#                In1st = int(n.firstLayer)
#                ipName  = ip_inst.name.split("_")[0]
#                ip_inst.CSVparameterListNecessary.append([weight, Out, In, In1st, ipName])
#                ip_inst.CSVparameterListNecessary.append([weight, Out, In, In1st,ipName])
    elif ip_inst.type == "Pooling":
        if(not ip_inst.necessaryHasSet):
            In = int(ip_inst.memInFlag)
            Out = int(ip_inst.memOutFlag)

            ipName  = ip_inst.name.split("_")[0]
            ip_inst.CSVparameterListNecessary += [In, Out, ipName]
            ip_inst.necessaryHasSet = True
    elif ip_inst.type == "MUX":
        None
    elif ip_inst.type == "Eltwise":
        if(not ip_inst.necessaryHasSet):
            RIn = int(ip_inst.memInFlag)
            Out = int(ip_inst.memOutFlag)
            LIn = int(True)
            ipName = ip_inst.name.split("_")[0]
            ip_inst.CSVparameterListNecessary += [LIn, RIn, Out, ipName]
            ip_inst.necessaryHasSet = True
    else: 
        assert 0, "Unsupported IP type" #Should not come here
        
    ip_inst.necessaryHasSet = True

def CSVconfigUnNece(n, ip_inst, s, t, idle, layerIdxTable,poolingTypeTable, muxSel):
    if ip_inst.type == "Convolution" or ip_inst.type == "Convolution_g":
        ip_inst.idle = int(idle)
        ip_inst.CSVparameterListUnNece[0] = int(idle)
        if n == t:
            ip_inst.CSVparameterListUnNece[1] = 1 #in
        if n == s:
            ip_inst.CSVparameterListUnNece[2] = 1 #out
        layerIdx = layerIdxTable[n.name]
        ip_inst.CSVparameterListUnNece[3] = layerIdx
        ip_inst.layerID = int(layerIdx)

#    elif ip_inst.type == "Convolution_g":
#        groupNums = 2 #FIXME: Hard coded group num
#        for i in range(groupNums):
#            ip_inst.CSVparameterListUnNece[i][0] = int(idle)
#            if n == t:
#                ip_inst.CSVparameterListUnNece[i][1] = 1 #in
#            if n == s:
#                ip_inst.CSVparameterListUnNece[i][2] = 1 #out
#            layerIdx = layerIdxTable[n.name]
#            ip_inst.CSVparameterListUnNece[i][3] = layerIdx

    elif ip_inst.type == "Pooling":
        ip_inst.idle = int(idle)
        ip_inst.CSVparameterListUnNece[0] = int(idle)
        if n == t:
            ip_inst.CSVparameterListUnNece[1] = 1 #in
        if n == s:
            ip_inst.CSVparameterListUnNece[2] = 1 #out
        layerIdx = layerIdxTable[n.name]
        ip_inst.layerID = int(layerIdx)
        byPass = int(False)
        Avg = int((poolingTypeTable[n.name] == "avg"))
        ip_inst.CSVparameterListUnNece[3:5] = [byPass, Avg]
        ip_inst.CSVparameterListUnNece[5] = layerIdx

    elif "MUX" in ip_inst.type:
        ip_inst.idle = int(idle)
        if(not idle):
            preIdx = layerIdxTable[s.name]
            preLayerType = s.type
            preIpName  = s.mappedIP.name.split("_")[0]
            ip_inst.CSVparameterListUnNece = [int(idle), muxSel, preIdx, preLayerType, preIpName]
        else:
           ip_inst.CSVparameterListUnNece = [1, 0, -1,"X", "X"]
    elif ip_inst.type == "Eltwise":
        ip_inst.idle = int(idle)
        ip_inst.CSVparameterListUnNece[0] = int(idle)
        #FIXME: We currently do not allow ELE to have stream in.
#        if n == t:
#            ip_inst.CSVparameterListUnNece[1] = 1 #in
        if n == s:
            ip_inst.CSVparameterListUnNece[3] = 1 #out
        layerIdx = layerIdxTable[n.name]
        ip_inst.CSVparameterListUnNece[4] = layerIdx
        ip_inst.layerID = int(layerIdx)
    else:
        assert 0, "Unsupported IP type" #Should not come here


def genCSVConfigs(gs, IP_g, muxSelTable, hw_layers, outDir, pipeInfoTable):
        
    layerIdxTable = readLayerId( "./inputFiles/layerIDMapping")
    poolingTypeTable = readLayerId("./inputFiles/PoolingTyping")
    #reorder the gs
    gs_list = gs

    #reorder the graph
    def comp(elem):
        for n in elem.nodes():
            if n.type in hw_layers:
                return n.ID

    gs_list.sort(key = comp)

    #reorder the nodes in g
    def comp1(elem):
        return elem.ID

    #Config all the necessary columns
    for g in gs_list:
        for n in g.nodes():
            CSVconfigNece(n, n.mappedIP)

    #Config all the changable colums
    roundIdx = 0
    fileName = outDir + "/round.csv"
    f = open(fileName, "w")
    f.close()
    pipeInfoFileName = outDir + "/pipeInfo.csv"
    f = open(pipeInfoFileName, "w")
    f.close()
    fileNameCallOrder = outDir + "/callOrder.csv"
    f = open(fileNameCallOrder, "w")
    f.close()
    for g in gs_list:
        callOrder = []
        node_list = list(g.nodes())
        node_list.sort(key = comp1)
        if len(node_list) == 1:
            s = node_list[0]
            callOrder.append(s.mappedIP.name)
            CSVconfigUnNece(s, s.mappedIP, None, None, False, layerIdxTable, poolingTypeTable, None)
        else:
            for idx in range(len(node_list)-1):
                s = node_list[idx]
                t = node_list[idx+1]
                if (s,t) not in g.edges():
                    callOrder.append(s.mappedIP.name)
                    CSVconfigUnNece(s, s.mappedIP, None, None, False, layerIdxTable, poolingTypeTable, None)
                    CSVconfigUnNece(t, t.mappedIP, None, None, False, layerIdxTable, poolingTypeTable, None)
                else:
                    ip_s = s.mappedIP
                    ip_t = t.mappedIP
                    ips = list(nx.bellman_ford_path(IP_g, ip_s, ip_t))

                    for ip in ips[0:-1]:
                        callOrder.append(ip.name)

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
            callOrder.append(t.mappedIP.name)
        genCSVFile(IP_g, roundIdx, fileName)
        genPipeInfoFile(IP_g, roundIdx, pipeInfoFileName, pipeInfoTable, hw_layers)

        callOrderList = []
#        nSplit(callOrder, callOrderList)
#        for n in callOrderList:
        genCallOrderFile(callOrder, fileNameCallOrder, roundIdx)
        roundIdx += 1
        
        # reset the network
        for ip_inst in IP_g.nodes():
            ip_inst.resetForCSVUnNece()

def genCallOrderFile(callOrder, fileNameCallOrder, roundIdx):
    f=open(fileNameCallOrder, "a")
    f.write(str(roundIdx)+",")
    f.write(",".join(callOrder))
    f.write(",END\n")
    f.close()

def genCSVFile(IP_g, roundIdx, fileName):
    f = open(fileName, "a")
    csvParamList = [roundIdx]
    for ip_inst in IP_g.nodes():
#        if "ip_l" in ip_inst.name:
#            continue
        if(ip_inst.type == "DDR"):
            continue
        csvParamList.append(ip_inst.type)
#        if ip_inst.type == "Convolution_g":
            #gen Div

#            idle = ip_inst.CSVparameterListUnNece[0][0]
#            GroupLayerIdx = ip_inst.CSVparameterListUnNece[0][3]
#            IPIdx = ip_inst.CSVparameterListNecessary[0][4]
#
#            if ip_inst.streamInFlag:
#                csvParamList.append("Divider")
#                idle_d = not(ip_inst.CSVparameterListUnNece[0][1])
#                csvParamList +=[idle_d, GroupLayerIdx, IPIdx]
#
#            csvParamList.append(ip_inst.type)
#            for i in range(2):
#                csvParamList += (ip_inst.CSVparameterListNecessary[i] + ip_inst.CSVparameterListUnNece[i])
#            #gen Comb
#            if ip_inst.streamOutFlag:
#                print ip_inst.CSVparameterListUnNece
#                idle_c = not(ip_inst.CSVparameterListUnNece[0][2])
#                csvParamList.append("Combiner")
#                csvParamList+=[idle_c, GroupLayerIdx, IPIdx]
#        else:
        csvParamList += (ip_inst.CSVparameterListNecessary + ip_inst.CSVparameterListUnNece)
    csvParamList.append("END")
    line = ",".join(map(str, csvParamList))
    line += "\n"
    f.write(line)
    f.close()

def genPipeInfoFile(IP_g, roundIdx, fileName, pipeInfoTable, hw_layers):
    f = open(fileName, "a")
    csvParamList = [roundIdx]
    numOfFalse = 0
    nodes = list(IP_g.nodes())
    def comp(elem):
        return elem.layerID
    nodes.sort(key = comp)
    for ip_inst in nodes:
        if ip_inst.type not in hw_layers:
            continue
        if ip_inst.idle:
            continue
        layerParamList = pipeInfoTable[ip_inst.layerID]
        isPipelinedTmp = layerParamList[0]
        if(not isPipelinedTmp):
            numOfFalse += 1
    isPipelined = True if numOfFalse < 2 else False

    csvParamList.append(isPipelined)
    for ip_inst in nodes:
        if ip_inst.type not in hw_layers:
            continue
        if ip_inst.idle:
            continue
        csvParamList.append(ip_inst.type)
        layerParamList = pipeInfoTable[ip_inst.layerID]
        csvParamList += layerParamList[1:]
    csvParamList.append("END")
    line = ",".join(map(str, csvParamList))
    line = line.replace("True", "1")
    line = line.replace("False", "0")
    line += "\n"
    f.write(line)
    f.close()

def nSplit(inList, outLists):
    hasElem = dict()
    subList = []
    for idx, n in enumerate(inList):
        if n not in hasElem:
            subList.append(n)
            hasElem[n] = 1 
        else:
            outLists.append(subList)
            nSplit(inList[idx:], outLists)
        return
    outLists.append(subList)

