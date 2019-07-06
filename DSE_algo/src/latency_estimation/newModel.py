import math
from infoClass import *
from gurobipy import *
import rowStepILP
import numpy
from modeling_new import modeling_util

def AlignSize(x, y): return -(-x//y)*y
def CeilDiv(x,y): return  -(-x//y)



#**********factor function ********/
def straddleCount( planes, filterSize, FEEDING_BUFF_DEPTH,groupNum):
    #* straddle = argmin K, s.t  alignedPlanes/2^K/4*fsize^2 <=FEEDING_BUFF_DEPTH/2-1
    numInpPlanes=AlignSize(planes,4);
    if planes < 4 :
        split=1
    else:
        split=groupNum;
    if planes >= 4 and groupNum>1:
        computeInPlane=numInpPlanes/2
    else:
        computeInPlane=numInpPlanes
    planeCapacity= (FEEDING_BUFF_DEPTH/2-1)/(filterSize*filterSize);
    straddleIndex=int.bit_length(  CeilDiv(computeInPlane/4,planeCapacity)  )-1;
    straddleVal=1<<straddleIndex;
    computePlanes=numInpPlanes/(straddleVal*split);
    return straddleVal,computePlanes

#************ Latency Functions ******************************
def memBurstReadLatency( burstNumber, burstLength, burstOverhead):
    """
    computes the function latency and bandwidth latency of a sequence of burstReads
    return: totalCycle: the total cycle number such sequence of burst read takes
            dataCycle: the total cycle number for data transfer such sequence of burst read takes ( it will be in conflict with other read)
    input burstNumber: the number of burst read in the burst sequence
    input burstLength: the length of each burst read
    input burstOverhead: the cycle number between the time last burst read data is receive till the start of issurance of next burst read
    """
    burstBreaks=CeilDiv(burstLength,16);
    acknowledgeCycle=2;
    responseCycle=26;
    dataCycle=(burstLength+burstBreaks*acknowledgeCycle)*burstNumber;
    totalCycle=(burstOverhead+responseCycle)*burstNumber+dataCycle;
    return totalCycle,dataCycle


def readInputLatencyNormal(width,rowStep,stride,plane):
    """
    computes the function latency and bandwidth latency of a sequence of one input read
    return: totalCycle: the total cycle number such sequence of burst read takes
            dataCycle: the total cycle number for data transfer such sequence of burst read takes ( it will be in conflict with other read)
    """
    burstNumber=CeilDiv(plane,16);
    burstLength=width*rowStep*stride;
    burstOverhead=16; #* this is from model sample
    return memBurstReadLatency( burstNumber, burstLength, burstOverhead);

def readInputLatencyStart(filterHeight,padnum,width,rowStep,stride,plane):
    """
    computes the function latency and bandwidth latency of a sequence of first input read
    return: totalCycle: the total cycle number such sequence of burst read takes
            dataCycle: the total cycle number for data transfer such sequence of burst read takes ( it will be in conflict with other read)
    """
    burstNumber=CeilDiv(plane,16);
    burstLength=(filterHeight+rowStep*stride-1-padnum)*width;
    burstOverhead=16;
    return memBurstReadLatency( burstNumber, burstLength, burstOverhead);



def loadWeightLatency(NKPF, computeNum):
    """
    computes the function latency and bandwidth latency of a sequence of one weight load
    return: totalCycle: the total cycle number such sequence of burst read takes
            dataCycle: the total cycle number for data transfer such sequence of burst read takes ( it will be in conflict with other read)
    """
    burstNumber= 1;
    burstLength=NKPF*computeNum; 
    burstOverhead=10 #* this is from model sample
    return memBurstReadLatency( burstNumber, burstLength, burstOverhead);

logFile=None

FEEDING_BUFF_DEPTH=1024




def computeLatencyConv (
    layerInfo,
    IPinfo,
    latencyInfo,
):
    """
    Function: computeLatency
    -----------------------------
    computing the clock cycle the IP need to compute #rowsteps of row in convolution.

    @params conv_inp_height:    the height of the input featuremap
    @params conv_inp_width:     the width of the input featuremap
    @params conv_inp_planes:    the depth of the input featuremap before grouping and dividing featuremap in depth dimension
    @params conv_out_height:    the height of the output featuremap
    @params conv_out_width:     the width of the output featuremap
    @params conv__planes:       the depth of the output featuremap before grouping and dividing featuremap in depth dimension
    @params conv_stride:        convolution stride
    @params conv_filter_height, 
            conv_filter_height: convolution filter height and width
    @params conv_pad:           convolution padding
    @params conv_group:         whether the current convolution is grouped, 1 if group is enabled otherwise 0.
    @params rowStep:            how many row olastStartOutRowo be computed
    @params int6bit:            whether currenlastStartOutRow 1 if 6bit precision is used, 0 if 8 bit is used.
    @return latency cycle number
    """
    
    conv_inp_height  = layerInfo.inp_height  
    conv_inp_width   = layerInfo.inp_width   
    conv_out_height  = layerInfo.out_height  
    conv_out_width   = layerInfo.out_width   
    conv_out_planes  = layerInfo.out_planes  
    conv_inp_planes  = layerInfo.inp_planes  
    conv_stride      = layerInfo.stride       
    fh= layerInfo.filter_height
   
    fw= layerInfo.filter_width 
    conv_pad  = layerInfo.pad          
    groupNum= layerInfo.groupFlag+1      
    rowStep = layerInfo.rowStep
    layerID = layerInfo.layerID
    memIn= layerInfo.memIn
    memOut= layerInfo.memOut
    XI_KER_PROC=IPinfo.XI_KER_PROC
    XI_PIX_PROC=IPinfo.XI_PIX_PROC
    XI_WEIGHTBUFF_DEPTH=IPinfo.XI_WEIGHTBUFF_DEPTH
    int6bit=IPinfo.int6bit


    #* intermediate variables

    
    straddle,computePlanes= straddleCount(conv_inp_planes,fh,1024,groupNum);
    computeNum = computePlanes/4*fh*fw

    latOsggBuff=XI_PIX_PROC+4
    latCompute16Ker=computeNum+XI_PIX_PROC/2+20;
    
    tmp=CeilDiv(XI_PIX_PROC,16)

    if(layerID!=0):
        latLoadFeedingBuff=CeilDiv(computePlanes,64)*( fw*tmp*fh*16+13)+20;
    else:
        latLoadFeedingBuff=(computePlanes/4*fh*( fw+conv_stride*(XI_PIX_PROC/2-1) )+6)*2;


    alignedOutputPlane = AlignSize(conv_out_planes,16)/groupNum


    # NKPF=min( alignedOutputPlane/XI_KER_PROC, (XI_WEIGHTBUFF_DEPTH -1)/ computeNum )
    NKPFtmp=(XI_WEIGHTBUFF_DEPTH -1)/ computeNum;

    while( alignedOutputPlane%(NKPFtmp*XI_KER_PROC) ):
        NKPFtmp-=1;    
    NKPF=NKPFtmp;

    
    latOsggBuff_fx=XI_PIX_PROC+4
    latProcResult_fe=latOsggBuff_fx+latCompute16Ker+(NKPF-1)*max(latOsggBuff_fx,latCompute16Ker)
    oneTime= (straddle==1) and (NKPF==alignedOutputPlane/XI_KER_PROC);
    latencyInfo.oneTime=oneTime;
   
    AXILATENCY = 1

    weightTotalCycle, weightDataCycle = loadWeightLatency(NKPF,computeNum)
    
    #* showing weightCycle computed

    latencyInfo.weightTotalCycle=weightTotalCycle;
    latencyInfo.weightDataCycle=weightDataCycle;

    
    pcLoopcnt= CeilDiv( conv_out_width*rowStep,  XI_PIX_PROC)

    latProcWeight=latLoop=pcLoopcnt*( max(latProcResult_fe,latLoadFeedingBuff)+20) #* need overhead here
    
    latencyInfo.latProcWeight=latProcWeight;
    latencyInfo.latLoadFeedingBuff=latLoadFeedingBuff;


    numProcWeight=ProcInputLoopCount=CeilDiv(alignedOutputPlane, XI_KER_PROC*NKPF)*straddle

    latencyInfo.numProcWeight=numProcWeight;
    


    if(layerID==0):
        inputTotalCycle1st=inputDataCycle1st=inputDataCycle=inputTotalCycle=conv_inp_width*(fh+(rowStep-1)*conv_stride)+20;
    else:
        inputTotalCycle,inputDataCycle=readInputLatencyNormal(conv_inp_width,rowStep,conv_stride,conv_inp_planes);
        inputTotalCycle1st,inputDataCycle1st=readInputLatencyStart(fh,conv_pad,conv_inp_width,rowStep,conv_stride,conv_inp_planes);


    latencyInfo.preOverheadTotalCycle=inputTotalCycle1st
    latencyInfo.preOVerheadDataCycle=inputDataCycle1st
    latencyInfo.inputTotalCycle=inputTotalCycle;
    latencyInfo.inputDataCycle=inputDataCycle;
    latencyInfo.inputTotalCycle1st=inputTotalCycle1st;
    latencyInfo.inputDataCycle1st=inputDataCycle1st;



    latencyInfo.FirstEndRows=fh+rowStep*conv_stride-1-conv_pad
    latencyInfo.DepsRows=rowStep*conv_stride

    lastRowStep=conv_out_height%rowStep if conv_out_height%rowStep !=0 else rowStep 
    latencyInfo.LastRowStep=lastRowStep;

    latencyInfo.outputTotalCycle = rowStep*(conv_out_width+60)*(alignedOutputPlane/16)+10;
    latencyInfo.outputDataCycle =  rowStep*conv_out_width*(alignedOutputPlane/16)+10;
    latencyInfo.outputTotalCycleLast=lastRowStep*(conv_out_width+60)*(alignedOutputPlane/16)+10;
    latencyInfo.outputDataCycleLast=lastRowStep*conv_out_width*(alignedOutputPlane/16)+10;

    lastStartOutRow=  conv_out_height-lastRowStep;
    lastStartInRow= (fh+lastStartOutRow*conv_stride-1-conv_pad)
    lastInRowStep= min( conv_inp_height-lastStartInRow,lastRowStep*conv_stride)
    latencyInfo.inputTotalCycleLast,latencyInfo.inputDataCycleLast=memBurstReadLatency( CeilDiv(conv_inp_planes,16),lastInRowStep*conv_inp_width,16 );
    
    latencyInfo.lastStartOutRow=lastStartOutRow;
    

    pcLast= CeilDiv( conv_out_width*lastRowStep,  XI_PIX_PROC)

    latencyInfo.latProcWeightLast=pcLast*( max(latProcResult_fe,latLoadFeedingBuff)+20)

def computeLatencyEle(
    layerInfo,
    IPinfo
):

    ele_out_height  = layerInfo.out_height   
    ele_out_width   = layerInfo.out_width    
    ele_out_planes  = layerInfo.out_planes  
    rowStep= layerInfo.rowStep
    memInL= layerInfo.memInL
    memInR= layerInfo.memInR
    memOut= layerInfo.memOut
  

    latProcWeight= 68+(ele_out_width+4);

    totalMem=memInL+memInR+memOut;

    if( totalMem==3 ):
        latLoadWeight= (ele_out_width+4)*2;
    elif( totalMem==2 or totalMem==1):
        latLoadWeight= (ele_out_width+4);
    else:
        latLoadWeight= 0;

    latCompNumber=ele_out_planes/16;
    if( memInL!=0 or  memInR!=0 ):
        preOverhead= (ele_out_width+4);
    else:
        preOverhead=0

    if( memOut!=0):
        postOverhead=(ele_out_width+4);
    else:
        postOverhead=0

    FirstEndRows=1;
    latReadInputData=0;
    latWritOutputData=0;
    return  [latProcWeight, latLoadWeight, latCompNumber,  preOverhead,postOverhead, latReadInputData, latWritOutputData,FirstEndRows,1]



def computeLatencyPool(
    layerInfo,
    latencyInfo
):
    pool_stride       =  layerInfo.stride      
    pool_filter_height=  layerInfo.filter_height
    pool_filter_width =  layerInfo.filter_width
    pool_inp_height   =  layerInfo.inp_height   
    pool_inp_width    =  layerInfo.inp_width   
    pool_pad          =  layerInfo.pad 
    pool_out_height   =  layerInfo.out_height   
    pool_out_width    =  layerInfo.out_width    
    pool_out_planes   =  layerInfo.out_planes    

    rowStep= layerInfo.rowStep
    memIn= layerInfo.memIn
    memOut= layerInfo.memOut


    ComputePoolingCycle= (pool_out_width*(pool_out_planes/16*(pool_filter_height*pool_filter_width+5)+10) )*rowStep;
    
    latencyInfo.ComputePoolingCycle=ComputePoolingCycle
 
    latCompNumber=rowStep

    latencyInfo.FirstEndRows=pool_filter_height+(rowStep-1)*pool_stride-pool_pad-1


    latencyInfo.inputTotalCycle1st,latencyInfo.inputDataCycle1st= memBurstReadLatency( CeilDiv(pool_out_planes,16),latencyInfo.FirstEndRows*pool_inp_width,16)

    
    latencyInfo.inputTotalCycle,latencyInfo.inputDataCycle= memBurstReadLatency( rowStep/2.0*CeilDiv(pool_out_planes,16),2*pool_stride*pool_inp_width,16)
    latencyInfo.outputTotalCycle, latencyInfo.outputDataCycle=  memBurstReadLatency( rowStep/2.0*CeilDiv(pool_out_planes,16),2*pool_out_width,16)
    

    latencyInfo.LastRowStep=lastRowStep=        pool_out_height%rowStep if pool_out_height%rowStep else rowStep
    latencyInfo.lastStartOutRow=   pool_out_height - rowStep
    latencyInfo.DepsRows=rowStep*pool_stride

    latencyInfo.inputTotalCycleLast,latencyInfo.inputDataCycleLast= memBurstReadLatency( lastRowStep/2.0*CeilDiv(pool_out_planes,16),2*pool_stride*pool_inp_width,16)
    latencyInfo.outputTotalCycleLast,latencyInfo.outputDataCycleLast= memBurstReadLatency( lastRowStep/2.0*CeilDiv(pool_out_planes,16),2*pool_out_width,16)



class convlayerInfo_t:
    def __init__(self):
        self.weightTotalCycle=None;
        self.weightDataCycle=None;
        self.latProcWeight=None;
        self.latLoadFeedingBuff=None;
        self.latProcInputBuff=None;
        self.numProcWeight=None;

        self.inputTotalCycle=None;
        self.inputDataCycle=None;
        self.inputTotalCycle1st=None;
        self.inputDataCycle1st=None;
        self.inputTotalCycleLast=None;
        self.inputDataCycleLast=None;


        self.outputTotalCycle=None;
        self.outputDataCycle=None;
        self.outputTotalCycleLast=None;
        self.outputDataCycleLast=None;
        self.FirstEndRows=None;
        self.DepsRows=None;
        self.LastRowStep=None;
        self.lastStartOutRow=None;
        self.oneTime=None;

class poolLatencyInfo_t:
    def __init__(self):
        self.ComputePoolingCycle=None;
        self.inputTotalCycle=None;
        self.inputDataCycle=None;
        self.inputTotalCycle1st=None;
        self.inputDataCycle1st=None;
        self.inputTotalCycleLast=None;
        self.inputDataCycleLast=None;
        self.outputTotalCycle=None;
        self.outputDataCycle=None;
        self.outputTotalCycleLast=None;
        self.outputDataCycleLast=None;
        self.FirstEndRows=None;
        self.DepsRows=None;
        self.LastRowStep=None;
        self.lastStartOutRow=None;
        self.oneTime=None;
    def __str__(self):

        string="ComputePoolingCycle "+str(self.ComputePoolingCycle)+"\n"
        string+="inputTotalCycle "+str(self.inputTotalCycle)+"\n"
        string+="inputDataCycle "+str(self.inputDataCycle)+"\n"
        string+="inputTotalCycle1st "+str(self.inputTotalCycle1st)+"\n"
        string+="inputDataCycle1st "+str(self.inputDataCycle1st)+"\n"
        string+="inputTotalCycleLast "+str(self.inputTotalCycleLast)+"\n"
        string+="inputDataCycleLast "+str(self.inputDataCycleLast)+"\n"
        string+="outputTotalCycle "+str(self.outputTotalCycle)+"\n"
        string+="outputDataCycle "+str(self.outputDataCycle)+"\n"
        string+="outputTotalCycleLast "+str(self.outputTotalCycleLast)+"\n"
        string+="outputDataCycleLast "+str(self.outputDataCycleLast)+"\n"
        string+="FirstEndRows "+str(self.FirstEndRows)+"\n"
        string+="DepsRows "+str(self.DepsRows)+"\n"
        string+="LastRowStep "+str(self.LastRowStep)+"\n"
        string+="lastStartOutRow "+str(self.lastStartOutRow)+"\n"
        string+="oneTime "+str(self.oneTime)+"\n"

        return string



class layerLatencyInfo_t():
    def __init__(self, layerInfo, IPinfo, rowStep):
        if(IPinfo.IPtype == "Conv"):
            conv_layer = modeling_util.ConvLayerInfo()
            conv_layer.set_from_layerInfo(layerInfo)

            test_IP = modeling_util.ConvIP()
            test_IP.set_from_IPInfo(IPinfo)
            test_IP.load_layer(conv_layer)
        elif(IPinfo.IPtype == "ELtwise"):
            elt_layer = modeling_util.PoolLayerInfo(layerInfo)
            elt_layer.set_from_file(args_file_name)

            test_IP = modeling_util.PoolIP(ConvIP, 32, 32, 8192, 2048, 4096)
            test_IP.load_layer(conv_layer)
        elif(IPinfo.IPtype == "Pool"):
            conv_layer = modeling_util.EleLayerInfo(layerInfo)
            conv_layer.set_from_file(args_file_name)

            test_IP = modeling_util.EleIP(ConvIP, 32, 32, 8192, 2048, 4096)
            test_IP.load_layer(conv_layer)
        else:
            assert(0, "unsupported IP")

        test_ip.computeLatency()


        self.PreDataCycle0=test_IP.getPreDataCycle0()
        self.PreDataCycle1=test_IP.getPreDataCycle1()
        self.PreTotalCycle=test_IP.getPreTotalCylce()
       

        self.RecurDataCycleFirst0=test_IP.getRecurDataCycleFirst0()
        self.RecurDataCycleFirst1=test_IP.getRecurDataCycleFirst1()
        self.RecurTotalCycleFirst=test_IP.getRecurTotalCycleFirst()

        self.RecurDataCycleMid0=test_IP.getRecurDataCycleMid0()
        self.RecurDataCycleMid1=test_IP.getRecurDataCycleMid1()
        self.RecurTotalCycleMid=test_IP.getTotalCycleMid()


        self.RecurDataCycleSecondLast0=test_IP.getRecurDataCycleSecondLast0()
        self.RecurDataCycleSecondLast1=test_IP.getRecurDataCycleLast1()
        self.RecurTotalCycleSecondLast=test_IP.getRecurTotalCycleLast()

        self.RecurDataCycleLast0=test_IP.getRecurDataCycleLast0()
        self.RecurDataCycleLast1=test_IP.getRecurDataCycleFirst1()
        self.RecurTotalCycleLast=test_IP.getRecurTotalCycleLast()

        self.PostDataCycle0=test_IP.getPostDataCycle0()
        self.PostDataCycle1=test_IP.getPostDataCycle1()
        self.PostTotalCycle=test_IP.getPostTotalCycle()

        self.RowNum=test_IP.getRowNum()
        self.RowStep=test_IP.getRowStep()
        self.DepsRowStepFirst=test_IP.getDepsRowStepRecur()
        self.DepsRowStepRecur=test_IP.getDepsRowStepRecur()
        self.LastStartRow=test_IP.getLastStartRow()
        self.SecondLastStartRow=test_IP.getSecondLastStartRow()
        self.Stride=test_IP.getStride()
    
        layerInfo.rowStep=rowStep


#        if( IPinfo.IPtype== "Convolution"):
#            convLatencyInfo=convlayerInfo_t();
#            computeLatencyConv(layerInfo,IPinfo,convLatencyInfo);
#            self.RowNum=layerInfo.out_height;
#            self.RowStep=rowStep;
#            if(layerInfo.memIn):
#                if IPinfo.inputPortIdx==0:
#                    self.PreDataCycle0=convLatencyInfo.inputDataCycle1st;
#                    self.PreDataCycle1=0;
#                    readDataCycle0=convLatencyInfo.inputDataCycle;
#                    readDataCycle1=0
#                    readDataCycleLast0=convLatencyInfo.inputTotalDataLast
#                    readDataCycleLast1=0;
#                else:
#                    self.PreDataCycle0=0;
#                    self.PreDataCycle1=convLatencyInfo.inputDataCycle1st;
#                    readDataCycle0=0
#                    readDataCycle1=convLatencyInfo.inputDataCycle;
#                    readDataCycleLast0=0;
#                    readDataCycleLast1=convLatencyInfo.inputDataCycleLast
#
#                self.PreTotalCycle=convLatencyInfo.inputTotalCycle1st
#                readTotalCycle=convLatencyInfo.inputTotalCycle
#                readTotalCycleLast=convLatencyInfo.inputTotalCycleLast

#            else:
#                self.PreDataCycle0=0;
#                self.PreDataCycle1=0;
#                self.PreTotalCycle=4;  
#                readDataCycle0=0;
#                readDataCycle1=0;
#                readDataCycleLast0=0;
#                readDataCycleLast1=0;
#                readTotalCycle=4;
#                readTotalCycleLast=4;
#    
#
#            if layerInfo.memOut:
#                if IPinfo.outputPortIdx==0:
#                    self.PostDataCycle0=convLatencyInfo.outputDataCycleLast;
#                    self.PostDataCycle1=0;
#                    writeDataCycle0=convLatencyInfo.outputDataCycle;
#                    writeDataCycle1=0
#                else:
#                    self.PostDataCycle0=0;
#                    self.PostDataCycle1=convLatencyInfo.outputDataCycleLast;
#                    writeDataCycle0=0
#                    writeDataCycle1=convLatencyInfo.outputDataCycle;
#                self.PostTotalCycle=convLatencyInfo.outputTotalCycleLast;
#                writeTotalCycle=convLatencyInfo.outputTotalCycle;
#            else:
#                self.PostDataCycle0=0;
#                self.PostDataCycle1=0;
#                self.PostTotalCycle=4;
#                writeDataCycle0=0;
#                writeDataCycle1=0;
#                writeTotalCycle=4;
#                
#            weightDataCycleFirst=convLatencyInfo.weightDataCycle;
#            weightTotalCycleFirst=convLatencyInfo.weightTotalCycle;
#            weightDataCycleRecur= 0 if convLatencyInfo.oneTime else weightDataCycleFirst;
#            weightTotalCycleRecur= 0  if convLatencyInfo.oneTime else weightTotalCycleFirst;
#            numProcWeight=convLatencyInfo.numProcWeight
#            numWeightLoadFirst=1 if convLatencyInfo.oneTime else convLatencyInfo.numProcWeight;
#            numWeightLoadRecur= 0 if convLatencyInfo.oneTime else convLatencyInfo.numProcWeight;
#
#    
#            self.RecurDataCycleFirst0=weightDataCycleFirst*numWeightLoadFirst+readDataCycle0;
#            self.RecurDataCycleFirst1=weightDataCycleFirst*numWeightLoadFirst+readDataCycle1;
#            procIstagingTotalCycle=max(weightTotalCycleFirst,convLatencyInfo.latLoadFeedingBuff)+numProcWeight*max(weightDataCycleRecur, convLatencyInfo.latProcWeight);
#            self.RecurTotalCycleFirst=max(procIstagingTotalCycle,readTotalCycle,writeTotalCycle);
#
#
#            self.RecurDataCycleMid0=weightDataCycleRecur*numWeightLoadRecur+readDataCycle0+writeDataCycle0;
#            self.RecurDataCycleMid1=weightDataCycleRecur*numWeightLoadRecur+readDataCycle1+writeDataCycle1;
#            procIstagingTotalCycle=max(weightTotalCycleRecur,convLatencyInfo.latLoadFeedingBuff)+numProcWeight*max(weightDataCycleRecur, convLatencyInfo.latProcWeight);
#            self.RecurTotalCycleMid=max(procIstagingTotalCycle,readTotalCycle, writeTotalCycle);
#
#            
#            self.RecurDataCycleSecondLast0=weightDataCycleRecur*numWeightLoadRecur+readDataCycleLast0+writeDataCycle0;
#            self.RecurDataCycleSecondLast1=weightDataCycleRecur*numWeightLoadRecur+readDataCycleLast1+writeDataCycle1;
#            procIstagingTotalCycle=max(weightTotalCycleRecur,convLatencyInfo.latLoadFeedingBuff)+numProcWeight*max(weightDataCycleRecur, convLatencyInfo.latProcWeight);
#            self.RecurTotalCycleSecondLast=max(procIstagingTotalCycle,readTotalCycleLast, writeTotalCycle);  
#        
#            self.RecurDataCycleLast0=weightDataCycleRecur*numWeightLoadRecur+writeDataCycle0;
#            self.RecurDataCycleLast1=weightDataCycleRecur*numWeightLoadRecur+writeDataCycle1;
#            procIstagingTotalCycle=max(weightTotalCycleRecur,convLatencyInfo.latLoadFeedingBuff)+numProcWeight*max(weightDataCycleRecur, convLatencyInfo.latProcWeightLast);
#            self.RecurTotalCycleLast=max(procIstagingTotalCycle,writeTotalCycle);  
#
#            self.LastStartRow=convLatencyInfo.lastStartOutRow  
#            self.SecondLastStartRow=convLatencyInfo.lastStartOutRow-rowStep;       
#            self.DepsRowStepFirst=convLatencyInfo.FirstEndRows
#            self.DepsRowStepRecur=convLatencyInfo.DepsRows
#            self.Stride=layerInfo.stride
#
#        elif( IPinfo.IPtype== "Eltwise"):
#            ele_out_height  = layerInfo.out_height   
#            ele_out_width   = layerInfo.out_width    
#            ele_out_planes  = layerInfo.out_planes  
#            rowStep = layerInfo.rowStep
#            memInL  = layerInfo.memInL
#            memInR  = layerInfo.memInR
#            memOut  = layerInfo.memOut
#
#            burstNumber=rowStep*CeilDiv(ele_out_planes,16)
#            burstLength=ele_out_width
#            dataCycle,TotalCycle=memBurstReadLatency( burstNumber, burstLength, 16)
#        
#            self.PreDataCycle0=memInL*dataCycle
#            self.PreDataCycle1=memInR*dataCycle
#            self.PreTotalCycle=TotalCycle
#
#            self.RecurDataCycleFirst0=memInL*dataCycle
#            self.RecurDataCycleFirst1=memInR*dataCycle+memOut*dataCycle
#            self.RecurTotalCycleFirst=TotalCycle
#
#            self.RecurDataCycleMid0=memInL*dataCycle
#            self.RecurDataCycleMid1=memInR*dataCycle+memOut*dataCycle
#            self.RecurTotalCycleMid=TotalCycle
#
#
#            self.RecurDataCycleSecondLast0=memInL*dataCycle
#            self.RecurDataCycleSecondLast1=memInR*dataCycle+memOut*dataCycle
#            self.RecurTotalCycleSecondLast=TotalCycle
#
#            self.RecurDataCycleLast0=memInL*dataCycle
#            self.RecurDataCycleLast1=memInR*dataCycle+memOut*dataCycle
#            self.RecurTotalCycleLast=TotalCycle
#
#            self.PostDataCycle0=0
#            self.PostDataCycle1=memOut*dataCycle
#            self.PostTotalCycle=TotalCycle
#
#            self.RowNum=ele_out_height
#            self.RowStep=rowStep
#            self.DepsRowStepFirst=1
#            self.DepsRowStepRecur=rowStep
#            self.LastStartRow=ele_out_height-rowStep
#            self.SecondLastStartRow=ele_out_height-rowStep*2;
#            self.Stride=1
#
#        elif( IPinfo.IPtype== "Pooling"):
#            poolLatencyInfo= poolLatencyInfo_t();
#            
#            
#            computeLatencyPool(layerInfo,poolLatencyInfo);
#        
#            memIn=layerInfo.memIn
#            memOut=layerInfo.memOut
#
#           
#
#
#            
#            self.PreDataCycle0=memIn*poolLatencyInfo.inputDataCycle1st
#     
#            self.PreDataCycle1=0
#            
#            self.PreTotalCycle=memIn*poolLatencyInfo.inputTotalCycle1st
#          
#
#
#            self.RecurDataCycleFirst0=memIn*poolLatencyInfo.inputDataCycle
#            self.RecurDataCycleFirst1=0
#            self.RecurTotalCycleFirst=max(poolLatencyInfo.ComputePoolingCycle,poolLatencyInfo.inputDataCycle)
#
#            self.RecurDataCycleMid0=memIn*poolLatencyInfo.inputDataCycle
#            self.RecurDataCycleMid1=memIn*poolLatencyInfo.outputDataCycle
#            self.RecurTotalCycleMid=max(poolLatencyInfo.ComputePoolingCycle,poolLatencyInfo.inputTotalCycle,poolLatencyInfo.outputTotalCycle)
#
#
#            self.RecurDataCycleSecondLast0=memIn*poolLatencyInfo.inputDataCycleLast
#            self.RecurDataCycleSecondLast1=memIn*poolLatencyInfo.outputDataCycle
#            self.RecurTotalCycleSecondLast=max(poolLatencyInfo.ComputePoolingCycle,poolLatencyInfo.inputTotalCycle,poolLatencyInfo.outputTotalCycle)
#
#
#            self.RecurDataCycleLast0=0
#            self.RecurDataCycleLast1=memIn*poolLatencyInfo.outputDataCycle
#            self.RecurTotalCycleLast=max(poolLatencyInfo.ComputePoolingCycle,poolLatencyInfo.outputTotalCycle)
#
#
#            self.PostDataCycle0=0
#            self.PostDataCycle1=memIn*poolLatencyInfo.outputDataCycleLast
#            self.PostTotalCycle=memIn*poolLatencyInfo.outputTotalCycleLast
#
#            self.RowNum=layerInfo.out_height 
#            self.RowStep=rowStep
#            self.DepsRowStepFirst=poolLatencyInfo.FirstEndRows
#            self.DepsRowStepRecur=poolLatencyInfo.DepsRows
#            self.LastStartRow=poolLatencyInfo.lastStartOutRow
#            self.SecondLastStartRow=poolLatencyInfo.lastStartOutRow-rowStep;
#            self.Stride=1
    def __str__(self):
        string="PreDataCycle0 "+str(self.PreDataCycle0)+"\n";
        string+="PreDataCycle1 "+str(self.PreDataCycle1)+"\n";
        string+="PreTotalCycle "+str(self.PreTotalCycle)+"\n";
        string+="RecurDataCycleFirst0 "+str(self.RecurDataCycleFirst0)+"\n";
        string+="RecurDataCycleFirst1 "+str(self.RecurDataCycleFirst1)+"\n";
        string+="RecurTotalCycleFirst "+str(self.RecurTotalCycleFirst)+"\n";
        string+="RecurDataCycleMid0 "+str(self.RecurDataCycleMid0)+"\n";
        string+="RecurDataCycleMid1 "+str(self.RecurDataCycleMid1)+"\n";
        string+="RecurTotalCycleMid "+str(self.RecurTotalCycleMid)+"\n";
        string+="RecurDataCycleSecondLast0 "+str(self.RecurDataCycleSecondLast0)+"\n";
        string+="RecurDataCycleSecondLast1 "+str(self.RecurDataCycleSecondLast1)+"\n";
        string+="RecurTotalCycleSecondLast "+str(self.RecurTotalCycleSecondLast)+"\n";
        string+="RecurDataCycleLast0 "+str(self.RecurDataCycleLast0)+"\n";
        string+="RecurDataCycleLast1 "+str(self.RecurDataCycleLast1)+"\n";
        string+="RecurTotalCycleLast "+str(self.RecurTotalCycleLast)+"\n";
        string+="PostDataCycle0 "+str(self.PostDataCycle0)+"\n";
        string+="PostDataCycle1 "+str(self.PostDataCycle1)+"\n";
        string+="PostTotalCycle "+str(self.PostTotalCycle)+"\n";
        string+="RowNum "+str(self.RowNum)+"\n";
        string+="RowStep "+str(self.RowStep)+"\n";
        string+="DepsRowStepFirst "+str(self.DepsRowStepFirst)+"\n";
        string+="DepsRowStepRecur "+str(self.DepsRowStepRecur)+"\n";
        string+="LastStartRow "+str(self.LastStartRow)+"\n";
        string+="SecondLastStartRow "+str(self.SecondLastStartRow)+"\n";
        string+="Stride "+str(self.Stride)+"\n";
        return string




            
def computeLatencyPipe2(
    latencyInfoList,
    pipeInfoStage
    ):
    layerLat=latencyInfoList[:];
    
    currentStartRows=[0]*len(layerLat)
    NrowStep=[]
    for i in layerLat: NrowStep.append(i.RowStep)

    firstOperatingLayerID=0;
    lastOperatingLayerID=0;
  
    pipeInfoStage.append( (layerLat[0].PreDataCycle0*4, layerLat[0].PreDataCycle1*4,max(layerLat[0].PreDataCycle0*4, layerLat[0].PreDataCycle1*4,   layerLat[0].PreTotalCycle*4)  ) );

    while 1:
        if( firstOperatingLayerID==lastOperatingLayerID and lastOperatingLayerID== len(layerLat) -1  and currentStartRows[lastOperatingLayerID]>=layerLat[lastOperatingLayerID].RowNum ):
            pipeInfoStage.append( (layerLat[lastOperatingLayerID].PostDataCycle0*4, layerLat[lastOperatingLayerID].PostDataCycle1*4,
            max( layerLat[lastOperatingLayerID].PostDataCycle0*4, layerLat[lastOperatingLayerID].PostDataCycle1*4,layerLat[lastOperatingLayerID].PostTotalCycle*4) )  )
            break; 

        stageDataCycle0=0;
        stageDataCycle1=0;
        stageTotalCycle=0;

        if ( firstOperatingLayerID<len(layerLat)-1 and currentStartRows[firstOperatingLayerID]>= layerLat[firstOperatingLayerID].RowNum):
            firstOperatingLayerID=firstOperatingLayerID+1; 
        if ( lastOperatingLayerID<len(layerLat)-1 and layerLat[lastOperatingLayerID+1].DepsRowStepFirst< currentStartRows[lastOperatingLayerID]):
            lastOperatingLayerID=lastOperatingLayerID+1;
            NrowStep[lastOperatingLayerID]=layerLat[lastOperatingLayerID].RowStep;

        for i in range(lastOperatingLayerID,firstOperatingLayerID,-1):
            NrowStep[i-1]=NrowStep[i]*layerLat[i].Stride;

        for i in range(firstOperatingLayerID,lastOperatingLayerID+1):
            currentEndRow=min( currentStartRows[i]+NrowStep[i], layerLat[i].RowNum)
            rowStepFactor=CeilDiv(currentEndRow-currentStartRows[i],layerLat[i].RowStep)
      
            if currentStartRows[i] <= layerLat[i].SecondLastStartRow and layerLat[i].SecondLastStartRow < currentEndRow:
                SecondLastDataCycle0=layerLat[i].RecurDataCycleSecondLast0;
                SecondLastDataCycle1=layerLat[i].RecurDataCycleSecondLast1;
                SecondLastTotalCycle=layerLat[i].RecurTotalCycleSecondLast;
                rowStepFactor-=1;
            else:
                SecondLastDataCycle0=0;
                SecondLastDataCycle1=0;
                SecondLastTotalCycle=0;

            if currentStartRows[i] <= layerLat[i].LastStartRow and layerLat[i].LastStartRow < currentEndRow:
                LastDataCycle0=layerLat[i].RecurDataCycleLast0;
                LastDataCycle1=layerLat[i].RecurDataCycleLast1;
                LastTotalCycle=layerLat[i].RecurTotalCycleLast;
                rowStepFactor-=1;
            else:
                LastDataCycle0=0;
                LastDataCycle1=0;
                LastTotalCycle=0;
    
            if currentStartRows[i]==0:
                stageDataCycle0+=layerLat[i].RecurDataCycleFirst0*rowStepFactor+LastDataCycle0+SecondLastDataCycle0;
                stageDataCycle1+=layerLat[i].RecurDataCycleFirst1*rowStepFactor+LastDataCycle1+SecondLastDataCycle1;
                stageTotalCycle=max(stageTotalCycle, layerLat[i].RecurTotalCycleFirst*rowStepFactor+LastTotalCycle+SecondLastTotalCycle )
            else:
                stageDataCycle0+=layerLat[lastOperatingLayerID].RecurDataCycleMid0*rowStepFactor+LastDataCycle0+SecondLastDataCycle0;
                stageDataCycle1+=layerLat[lastOperatingLayerID].RecurDataCycleMid1*rowStepFactor+LastDataCycle1+SecondLastDataCycle1;
                stageTotalCycle=max(stageTotalCycle, layerLat[lastOperatingLayerID].RecurTotalCycleMid*rowStepFactor+LastTotalCycle+SecondLastTotalCycle)
        for i in range(firstOperatingLayerID,lastOperatingLayerID+1):
            currentStartRows[i]+=NrowStep[i]

        pipeInfoStage.append((stageDataCycle0*4,stageDataCycle1*4,    max( stageDataCycle0*4,stageDataCycle1*4,stageTotalCycle*4) ) )


def computeLatencyParallel2(
    pipeInfoStage):
    currentTotalCycle={}
    currentDataCycle0={}
    currentDataCycle1={}
    for i in range( len(pipeInfoStage)):
        currentDataCycle0[i]=pipeInfoStage[i][0][0]
        currentDataCycle1[i]=pipeInfoStage[i][0][1]
        currentTotalCycle[i]=pipeInfoStage[i][0][2]
    latency=0
    while 1:
        if not currentTotalCycle:
            break;
        index=min(currentTotalCycle,key=currentTotalCycle.get)
        totalCycle=float(currentTotalCycle[index])
        dataCycle0=0;
        dataCycle1=0;
        for k in currentTotalCycle:
            dataCyleTemp0=currentDataCycle0[k]*totalCycle/currentTotalCycle[k];
            dataCyleTemp1=currentDataCycle1[k]*totalCycle/currentTotalCycle[k];

            currentDataCycle0[k]-=dataCyleTemp0;
            currentDataCycle1[k]-=dataCyleTemp1;
            
            currentTotalCycle[k]-=totalCycle;

            dataCycle0+=dataCyleTemp0;
            dataCycle1+=dataCyleTemp1;
        latency+=max(dataCycle0,dataCycle1,totalCycle)
    
        deleteList=[]
        for k in currentTotalCycle:
            if currentTotalCycle[k]==0:
                if pipeInfoStage[k]:
                    while (currentTotalCycle[k]==0):
                        currentDataCycle0[k],currentDataCycle1[k],currentTotalCycle[k]=pipeInfoStage[k].pop(0)
                else:
                    deleteList.append(k)
        for k in deleteList:
            del currentDataCycle0[k]
            del currentDataCycle1[k]
            del currentTotalCycle[k]
    return latency
            


def computeRoundLatency(
    roundInfo,
    IPinfoList,
    rowStep):

    pipeStageInfoList=[]
    runChain=[];
    startIdx=0;
    while( startIdx < len(roundInfo) ):
        runInfo=roundInfo[startIdx]
        IPinfoInst=IPinfoList[runInfo.IPidx];
        layerInfoInst=runInfo.layerInfo;
        runChain.append([layerInfoInst,IPinfoInst]);
        if(runInfo.nextIPidx == None):
            layerLatencyInfoList=[]
            latencyInfoStage=[]
            for i in range( len(runChain) ):
                layerInfoInst,IPinfoInst=runChain[i];
                x=layerLatencyInfo_t(layerInfoInst,IPinfoInst,rowStep);
                layerLatencyInfoList.append(x)
            computeLatencyPipe2(layerLatencyInfoList,latencyInfoStage);
            pipeStageInfoList.append(latencyInfoStage);
            runChain=[]
        startIdx=startIdx+1;
    latency=computeLatencyParallel2(pipeStageInfoList);
    return latency


    





        










    




