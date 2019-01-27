class Ports:
    def __init__(self, portType):
        self.type = portType

def readTemplate(funcType):
    memIns = []
    memOuts = []
    neces = []
    streamIns = []
    streamOuts = []


    f = open("./IPTemplates/"+str(funcType))
    fList = f.readlines()
    f.close()

    idx = 0
    while(idx < len(fList)):
        lList = fList[idx].split()
        if lList[0] == "MEMIN":
            inPortNums = int(lList[1])
            for i in range(inPortNums):
                idx+=1
                memIns.append(fList[idx].strip())
        elif lList[0] == "MEMOUT":
            outPortNums = int(lList[1])
            for i in range(outPortNums):
                idx+=1
                memOuts.append(fList[idx].strip())
        elif lList[0] == "STREAMIN":
            streamInNum = int(lList[1])
            for i in range(streamInNum):
                idx+=1
                streamIns.append(fList[idx].strip())
        elif lList[0] == "STREAMOUT":
            streamOutNum = int(lList[1])
            for i in range(streamOutNum):
                idx+=1
                streamOuts.append(fList[idx].strip())
        elif lList[0] == "NECESSARY":
            neceNum = int(lList[1])
            for i in range(neceNum):
                idx+=1
                neces.append(fList[idx].strip())
        else:
            print "Unsupported type, should be one of MEMIN, MEMOUT, STREAMIN, STREAMOUT, NECESSARY"
        idx+=1
    return memIns, memOuts, neces, streamIns, streamOuts


#mIn,mOut,neces, sIns, sOuts = readTemplate("Convolution")
#print "mIn", mIn
#print "mOut", mOut
#print "neces", neces
#print "sIns", sIns
#print "sOuts", sOuts
