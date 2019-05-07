from newModel import *
from infoClass import * 


f = open("modebug.csv","r");

while 1:
    line=f.readline();
    if line=="": break
    if "[MODELROUNDSTART]" in  line:
        scheduleInfoList=[]
        line=f.readline();
        while  "[MODELROUNDEND]" not in line:
            line = line.replace("\ ", "")
            line = line.replace("\n", "")
            IPinfoParam = line.split(",")
            line=f.readline();  
            line = line.replace("\ ", "")
            line = line.replace("\n", "")
            layerInfoParam = line.split(",")   
            IPInfo=None;
            layerInfo=None

            IPNAME=IPinfoParam[1];
            IPInfo=IPinfo_t(
                IPtype="Convolution", IPidx=0, K_x_P= 0,
                XI_KER_PROC=int(IPinfoParam[2]),
                XI_PIX_PROC=int(IPinfoParam[3]),
                XI_INDEPTH=int(IPinfoParam[4]), 
                XI_OUTDEPTH=int(IPinfoParam[5]),
                XI_WEIGHTBUFF_DEPTH=int(IPinfoParam[6]),
                int6bit=1, 
                BRAM=None,
                IBRAM=None, 
                OBRAM=None, 
                WBRAM=None,
                OtherBRAM=None)

            layerInfo=layerInfo_t(
                layerType="Convolution", 
                inp_width=int(layerInfoParam[2]), 
                inp_height=int(layerInfoParam[3]),
                out_width=int(layerInfoParam[4]),
                out_height=int(layerInfoParam[5]), 
                out_planes=int(layerInfoParam[6]), 
                inp_planes=int(layerInfoParam[7]), 
                stride=int(layerInfoParam[8]),
                filter_height=int(layerInfoParam[9]), 
                filter_width=int(layerInfoParam[10]), 
                pad=int(layerInfoParam[11]),
                groupFlag=0, 
                layerID=int(layerInfoParam[12]), 
                memIn=int(layerInfoParam[13]),
                memInL=True, 
                memInR=True, 
                memOut=int(layerInfoParam[14]), 
                rowStep=int(layerInfoParam[15]))

            scheduleInfoList.append( (layerInfo,IPInfo) );
            line=f.readline();

        startIdx=0;
        pipeStageInfoList=[]
        runChain=[]
        while  startIdx < len(scheduleInfoList):

         
            layerInfoInst,IPinfoInst=scheduleInfoList[startIdx];
            runChain.append([layerInfoInst,IPinfoInst]);

            if(layerInfoInst.memOut == 1):
                
                layerLatencyInfoList=[]
                latencyInfoStage=[]
                for i in range( len(runChain) ):
                    layerInfoInst,IPinfoInst=runChain[i];
                    x=layerLatencyInfo_t(layerInfoInst,IPinfoInst,layerInfoInst.rowStep);
                    layerLatencyInfoList.append(x)
                computeLatencyPipe2(layerLatencyInfoList,latencyInfoStage);
                pipeStageInfoList.append(latencyInfoStage);
                runChain=[]
            startIdx=startIdx+1;
        latency=computeLatencyParallel2(pipeStageInfoList);

        
        for (i,j) in scheduleInfoList:
            print i.layerID,
        print latency
