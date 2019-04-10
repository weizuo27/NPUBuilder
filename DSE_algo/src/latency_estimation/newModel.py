import math
from infoClass import *
def AlignSize(x, y):
    ret = x if (x%y == 0) else ((x/y + 1)*y)
    return ret


FEEDING_BUFF_DEPTH=1023.0

def computeWeightDepth(layerInfo, KER, PIX):
    """
    return: the minimum Weight Depth
    input layerInfo: an instance of layerInfo_t with corresponding convolution layer information
    int KER: ker factor
    int PIX: pix factor
    retutrn [WeightDepth, latLoadFeedingBuff, latProcResult, latLoadWeight, onetime]
    """
    conv_out_planes  = layerInfo.out_planes   
    conv_inp_planes  = layerInfo.inp_planes   
    conv_stride      = layerInfo.stride       
    fh= layerInfo.filter_height
    fw= layerInfo.filter_width 
    groupNum= 1+layerInfo.groupFlag;
    layerID= layerInfo.layerID;

    alignedInputPlane=AlignSize(conv_inp_planes,4);
    k=math.ceil( math.log2( FEEDING_BUFF_DEPTH/2*4/alignedInputPlane/fh/fw));
    if(k<0):k=0;
    straddle=1<<k;
    computePlanes=alignedInputPlane/(straddle*groupNum)
    computePlanesAligned=AlignSize(computePlanes,4)

    print("computePlanesAligned "+str(computePlanesAligned))
    print("straddle "+str(straddle))

    #find latProcResult and latLoadFeedingBuff latnecy
    latOsggBuff=PIX+8
    latCompute16Ker=(fh * fw * (computePlanesAligned/4)+1)+PIX/2+20;
    print("LatCompute16Ker "+str(latCompute16Ker));

    tmp = (PIX/16+1) if (PIX%16) else  (PIX/16)

    if(layerID!=0):
        latLoadFeedingBuff_fl=computePlanesAligned/64*( fw*tmp*fh*16+13)+20;
    #here we made a allowance of 0.9 to make lat loatFeeding buffer correct
    requiredNKPF = math.ceil(latLoadFeedingBuff_fl*0.9/latCompute16Ker)
    alignedOutputPlane = AlignSize(conv_out_planes,16)
    NKPF=min(requiredNKPF, alignedOutputPlane/KER)
    #In CHaiDNN's flow, the NKPF shall be constraint at the factor of  alignedOutputPlane/KER, however, I think it does not have to be the real factor
    #need to modify hardware
    weightDepth= AlignSize(fh*fw*computePlanesAligned/4*NKPF+1,1024)
    return weightDepth





def computeLatencyConv (
    layerInfo,
    IPinfo
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
    @params rowStep:            how many row of output need to be computed
    @params int6bit:            whether current is precision, 1 if 6bit precision is used, 0 if 8 bit is used.
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
    
    oneTime= layerInfo.oneTime

    XI_KER_PROC=IPinfo.XI_KER_PROC
    XI_PIX_PROC=IPinfo.XI_PIX_PROC
    XI_WEIGHTBUFF_DEPTH=IPinfo.XI_WEIGHTBUFF_DEPTH
    int6bit=IPinfo.int6bit



    alignedInputPlane=AlignSize(conv_inp_planes,4);
    k=math.ceil( math.log2( FEEDING_BUFF_DEPTH/2*4/alignedInputPlane/fh/fw));

    if(k<0):k=0;
    straddle=1<<k;

    computePlanes=alignedInputPlane/(straddle*groupNum)
    computePlanesAligned=AlignSize(computePlanes,4)
    computeNum = fh * fw * computePlanesAligned/4
    
    latOsggBuff=XI_PIX_PROC+8
    latCompute16Ker=computeNum+XI_PIX_PROC/2+20;

    if(layerID!=0):
        latLoadFeedingBuff=computePlanesAligned/64*( fw*tmp*fh*16+13)+20;
    else:
        latLoadFeedingBuff=(computePlanesAligned/4*fh*( fw+conv_stride*(XI_PIX_PROC/2-1) )+6)*2;


    alignedOutputPlane = AlignSize(conv_out_planes,16)/groupNum
    NKPF=min( alignedOutputPlane, (XI_WEIGHTBUFF_DEPTH -1)/ computeNum )
    latOsggBuff_fx=XI_PIX_PROC+8
    latProcResult_fe=latOsggBuff_fx+latCompute16Ker+(NKPF-1)*max(latOsggBuff_fx,latCompute16Ker)+10

   
    AXILATENCY = 1
    if oneTime:
        latLoadWeight=latLoadKernelsEn_fz = 1
    else:
        latLoadWeight=latLoadKernelsEn_fz= (NKPF*computeNum/16*18)*AXILATENCY+10

    pcLoopcnt= AlignSize( conv_out_width*rowStep,  XI_PIX_PROC)/XI_PIX_PROC
    latProcWeight=latLoop=pcLoopcnt*( max(latProcResult_fe,latLoadFeedingBuff)+20)
    latCompNumber=ProcInputLoopCount=math.ceil( float(alignedOutputPlane)/XI_KER_PROC/NKPF)*straddle
    latProcInputBuff=ProcInputLoopCount*(max(latLoop,latLoadKernelsEn_fz)+4)+max(latLoadFeedingBuff,latLoadKernelsEn_fz);
    if(layerID==0):
        latReadLineBuffer=conv_inp_width*(fh+(rowStep-1)*conv_stride)+20;
    else:
        latReadLineBuffer=rowStep*conv_stride*(Align( conv_inp_planes,16)/16) *(10+conv_inp_width*1.1)+10 

    if(memIn!=0):
        preOverhead=(fh+rowStep-1-conv_pad)*conv_stride*( Align( conv_inp_planes,16)/16)*(10+conv_inp_width)+10
        latReadInputData= rowStep*conv_stride*(Align( conv_inp_planes,16)/16)*conv_inp_width
    else:
        preOverhead=0
        latReadInputData=0

    FirstEndRows=fh+rowStep-1-conv_pad-1
    latStoreOStagingBuff = rowStep*(conv_out_width+50)*(alignedOutputPlane/16)+10;


    if(memOut!=0):
        postOverhead=rowStep*(conv_out_width+10)*(alignedOutputPlane/16)+10;
        latWritOutputData= rowStep*conv_out_width*(alignedOutputPlane/16);
    else:
        postOverhead=0
        latWritOutputData=0
    return  [latProcWeight, latLoadWeight, latCompNumber,  preOverhead,postOverhead, latReadInputData, latWritOutputData,FirstEndRows,conv_stride]





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
    IPinfo
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


    latProcWeight=pool_out_height*pool_out_planes/16*pool_filter_height*pool_filter_width
    latLoadWeight=pool_inp_width*pool_stride*pool_out_planes/16
    latCompNumber=rowStep


    FirstEndRows=pool_filter_height+(rowStep-1)*pool_stride-pool_pad-1


    if( memIn ):
        preOverhead= FirstEndRows*pool_inp_width*pool_out_planes/16
    else:
        preOverhead=0


    if( memOut):
        postOverhead=rowStep*pool_out_width*pool_out_planes/16
    else:
        postOverhead=0


    latReadInputData=0
    latWritOutputData=0
    return  [latProcWeight, latLoadWeight, latCompNumber,  preOverhead,postOverhead, latReadInputData, latWritOutputData,FirstEndRows,1]

class layerLatencyInfo_t():
    layerType=None
    rowStep=None
    latProcWeight=None
    latLoadWeight=None
    latLoadWeightCurrent=None,
    latCompNumber=None
    latPreOverhead=None
    latReadInputData=None
    latWritOutputData=None
    height=None
    width=None
    stride=None
    currentStartRows=0
    currentEndRows=0
    currentSegmentLatency=0;
    NrowStep=None
    FirstEndRows=None #must initiate this before start

    def __init__(self, layerInfo, IPinfo, rowStep):
        self.rowStep=rowStep
        self.NrowStep=rowStep
        self.height=layerInfo.conv_out_height
        self.currentStartRows=0;
        self.currentSegmentLatency=0;
        layerInfo.rowStep=rowStep

        if( IPinfo.IPtype== "Convolution"):
            [self.latProcWeight, self.latLoadWeight, self.latCompNumber,  self.latPreOverhead, self.latPostOverhead, self.latReadInputData, self.latWritOutputData,self.FirstEndRows,self.stride]=computeLatencyConv(layerInfo,IPinfo)
        if( IPinfo.IPtype== "ElementWise"):
            [self.latProcWeight, self.latLoadWeight, self.latCompNumber,  self.latPreOverhead,  self.latPostOverhead, self.latReadInputData, self.latWritOutputData,self.FirstEndRows,self.stride]=computeLatencyEle(layerInfo,IPinfo)
        if( IPinfo.IPtype== "Pooling"):
            [self.latProcWeight, self.latLoadWeight, self.latCompNumber,  self.latPreOverhead,  self.latPostOverhead, self.latReadInputData, self.latWritOutputData,self.FirstEndRows,self.stride]=computeLatencyPool(layerInfo,IPinfo)


def computeLatencyPipe(
    layers
):
    layersCopy=layers[:];

    timeStamp=0;
    weightTotalCycle=0;

    timeStamp+=layers[0].latPreOverhead;

    layers[0].FirstEndRows=-1;

    firstOperatingLayerID=0;
    lastOperatingLayerID=0;

    segmentIdx=0;
    while 1:

        # compute by the rowstep timing range for the latest running stage
        if( firstOperatingLayerID==lastOperatingLayerID and lastOperatingLayerID== len(layersCopy) -1  and layersCopy[lastOperatingLayerID].currentStartRows>=layersCopy[lastOperatingLayerID].height ):
            timeStamp+=layersCopy[lastOperatingLayerID].latPostOverhead
            break;
        # print "round ", segmentIdx
        segmentIdx+=1
        #updating first pipeline stage
        if ( firstOperatingLayerID<len(layersCopy)-1 and layersCopy[firstOperatingLayerID].currentStartRows>= layersCopy[firstOperatingLayerID].height):
            firstOperatingLayerID=firstOperatingLayerID+1;
        
        #updating last pipeline stage
        if ( lastOperatingLayerID<len(layersCopy)-1 and layersCopy[lastOperatingLayerID+1].FirstEndRows< layersCopy[lastOperatingLayerID].currentStartRows):
            lastOperatingLayerID=lastOperatingLayerID+1;
            layersCopy[lastOperatingLayerID].NrowStep=layersCopy[lastOperatingLayerID].rowStep;

        for i in range(lastOperatingLayerID,firstOperatingLayerID,-1):
            layersCopy[i-1].NrowStep=layersCopy[i].NrowStep*layersCopy[i].stride;
        
        weightAmount=1;
        for i in range(firstOperatingLayerID,lastOperatingLayerID+1):
            weightAmount+=(layersCopy[i].latLoadWeight*layersCopy[i].latCompNumber+ layersCopy[i].latReadInputData+layersCopy[i].latWritOutputData)*layersCopy[i].NrowStep/layersCopy[i].rowStep;
        weightTotalCycle+=weightTotalCycle
        maxLatency=0;

        for i in range(firstOperatingLayerID,lastOperatingLayerID+1):
            layersCopy[i].latLoadWeightCurrent=layersCopy[i].latLoadWeight*weightAmount/ float(layersCopy[i].latLoadWeight*layersCopy[i].latCompNumber*layersCopy[i].NrowStep/layersCopy[i].rowStep);
            layersCopy[i].currentSegmentLatency=( layersCopy[i].latLoadWeightCurrent+ (layersCopy[i].latCompNumber-1)*max(layersCopy[i].latLoadWeightCurrent, layersCopy[i].latProcWeight )+ layersCopy[i].latProcWeight);
            if maxLatency< layersCopy[i].currentSegmentLatency:
                maxLatency = layersCopy[i].currentSegmentLatency
            # print "latency ", i, layersCopy[i].latLoadWeightCurrent, layersCopy[i].currentSegmentLatency, "MaxLatency ", maxLatency
 
        timeStamp+=maxLatency;
        # for i in range(firstOperatingLayerID,lastOperatingLayerID+1):
        #     # print "Layer ", i, "startRow ", layersCopy[i].currentStartRows, "endRow",  layersCopy[i].currentStartRows+layersCopy[i].NrowStep-1;
        for i in range(firstOperatingLayerID,lastOperatingLayerID+1):
            layersCopy[i].currentStartRows+=layersCopy[i].NrowStep;
    return [timeStamp, weightTotalCycle]



def computeRequiredIODepth(layerInfo, rowStep):
    conv_out_planes     =   layerInfo.out_planes   
    conv_inp_planes     =   layerInfo.inp_planes  
    conv_stride         =   layerInfo.stride 
    conv_inp_height     =   layerInfo.inp_height
    conv_inp_width      =   layerInfo.inp_width
    conv_out_width      =   layerInfo.out_width
    conv_filter_height  =   layerInfo.filer_height

    IN_D=1<< math.ceil( math.log2( conv_inp_width*math.ceil(conv_inp_planes/64)*(conv_filter_height+(rowStep*2-1)*conv_stride) ) );
    IN_D=max(IN_D,1024)
    OUT_D= AlignSize( conv_out_width*math.ceil(conv_inp_planes/32)*rowStep , 1024)
    return [IN_D,OUT_D]
    

def computeIOBram(IN_D,OUT_D):
    inBrams = 2*math.ceil(IN_D/1024.0) * 8 * 2 * math.ceil(32.0/18)
    outBrams = 2*math.ceil(OUT_D/1024.0) * 8 * math.ceil(72.0/18) * 2
    return [inBrams, outBrams]

def computeWeightBRAM(wBufferSize, KER):
    wBrams = math.ceil(wBufferSize / 1024.0)  * math.ceil(32.0/18) * 2
    return  wBrams

def constantBramConv(wBufferSizei, ker_proc, pix_proc):
    #need validation
    wBrams = ceil(wBufferSizei / 1024.0) * ker_proc * ceil(32.0/18) * 2
    feedingBrams = 2*ceil(32.0/18) * pix_proc/2 * 2
    resulting = 2*ker_proc * 2 * 2
    bias_scale = 24
    brams = wBrams + feedingBrams + resulting + bias_scale
    return brams

def constantBramPool():
    return 106;

def constantBramEle():
    return 48;

def takeFirst(a):
    return a[0]

def multiChainLatency(
    chainLatencList
):
    chainLatencList.sort(key=takeFirst);
    prevLatency=0;
    totalLatency=0;
    for i in len(chainLatencList):
        overLappingWeightLatency=0;
        overLappingComputeLatency=chainLatencList[i][0]-prevLatency;
        for j in range(i, len(chainLatencList)):
            overLappingWeightLatency+=chainLatencList[j][1]*float(overLappingComputeLatency)/chainLatencList[j][0];
        totalLatency+=max(overLappingComputeLatency,overLappingWeightLatency);
        prevLatency=chainLatencList[i][0];
    
    



def computeRoundIPindex(
    roundInfoList, #list of runInfo_t[], runInfo_t 
    KerPixList, #list of [Ker, Pix] tuples for each IP, if the IP is not a conv IP, then  [Ker, Pix] = [0,0]
    IPinfoList #list of IPinfo, the only specified value in each element should only be IPtype and K_x_P
):
    #1. choose the weight depth by finding the largest weight depth that is optimal result
    weightDepthList=[0]*len(KerPixList);
    for runInfoList in roundInfoList:
        for runInfo in runInfoList:
            if( runInfo.IPInfo.IPtype=="Convolution" and runInfo.idle== False):
                Ker, Pix=KerPixList[runInfo.IPidx]
                weightDepth=computeWeightDepth(runInfo.layerInfo,Ker,Pix);
                if(weightDepthList[runInfo.IPidx]< weightDepth):
                    weightDepthList[runInfo.IPidx]=weightDepth;

    constBram=0;
    for i, IPinfo in enumerate(IPinfoList):
        if( IPinfo.IPtype=="Convolution"):
            Ker, Pix=KerPixList[i]
            constBram+=constantBramConv(weightDepthList[i],Ker, Pix);
            IPinfoList[i].XI_WEIGHTBUFF_DEPTH=weightDepthList[i];
            IPinfoList[i].XI_KER_PROC=Ker;
            IPinfoList[i].XI_PIX_PROC=Pix;
        elif( IPinfo.IPtype=="Pooling"):
            constBram+=constantBramPool();
        elif( IPinfo.IPtype=="Eltwise"):
            constBram+=constantBramEle();
        else:
            assert(0), "Unsupported IP type"
    roundILPInfoList=[];
    for roundIdx in range(len(roundInfoList)):
        roundILPInfoList_row=[];
        for rowStep in range(1,7):
            IOBRAM={}
            for runInfo in roundInfoList[roundIdx]:
                if( IPinfoList[runInfo.IPidx].IPtype=="Convolution"):
                    IN_D,OUT_D = computeRequiredIODepth( runInfo.layerInfo, rowStep)
                    inBrams, outBrams = computeIOBram(IN_D,OUT_D)
                    IOBRAM[runInfo.IPidx]=[inBrams,outBrams]
            #Segment Different pipeline chain
            chainLatencList=[];
            runChain=[];
            startIdx=0;
            while( startIdx < len(roundInfoList[roundIdx]) ):
                runInfo=roundInfoList[roundIdx] 
                IPinfoInst=IPinfoList[runInfo.IPidx];
                layerInfoInst=runInfo.layerInfo;
                runChain.append([layerInfoInst,IPinfoInst]);
                if(runInfo.nextIPidx == None):
                    layerLatencyInfoList=[]
                    for i in range( len(runChain) ):
                        IPinfoInst,layerInfoInst=runChain[i];
                        x=layerLatencyInfo_t(IPinfoInst,layerInfoInst,rowStep);
                        layerLatencyInfoList.append(x)
                    cycles,weigthCycles=computeLatencyPipe(layerLatencyInfoList);
                    chainLatencList.append([cycles,weigthCycles]);
                startIdx=startIdx+1;
            latency=multiChainLatency(chainLatencList);
            #generate a validation testcase and add it into round.csv
            roundILPInfo=roundILPInfo_t();
            roundILPInfo.roundIdx=roundIdx;
            roundILPInfo.rowStep=rowStep;
            for i in range(len(IPinfoList)):
                if ( IPinfoList[i].IPtype=="Convolution" ):
                    roundILPInfo.IPindexList.append(i);
                    if i in IOBRAM:
                        inBrams,outBrams=IOBRAM[i]
                        roundILPInfo.IBRAMList.append(inBrams)
                        roundILPInfo.OBRAMList.append(outBrams)
                    else:
                        roundILPInfo.IBRAMList.append(0)
                        roundILPInfo.OBRAMList.append(0)
            roundILPInfo.ConstantBRAM=constBram;
            roundILPInfoList_row.append(roundILPInfo);
        roundILPInfoList.append(roundILPInfoList_row);
    return [roundILPInfoList, IPinfoList]


    
    

    
        



# def rawDSP( K_x_P):
#     """
#     return the estimated DSP for a conv IP with ker_proc by pix_proc  as K_x_P in first round scheduling
#     input K_x_P: the product of ker_proc and pix_proc
#     return: estiumated DSP
#     """
#     return K_x_P*2.2

# def rawLatency( layerInfo, K_x_P ):
#     """
#     return the estimated latency for a certain K_x_P in first round scheduling
#     input layerInfo: the class containg convolution layer information
#     input K_x_P: the product of ker_proc and pix_proc
#     return: estimated latency
#     """
#     conv_filter_height= layerInfo.conv_filter_height
#     conv_filter_width= layerInfo.conv_filter_width
#     conv_inp_planes  = layerInfo.conv_inp_planes 
#     conv_out_height  = layerInfo.conv_out_height   
#     conv_out_width   = layerInfo.conv_out_width    
#     conv_out_planes  = layerInfo.conv_out_planes  
#     return conv_filter_height*conv_filter_width*conv_inp_planes*conv_out_planes*conv_out_height*conv_out_width/K_x_P/4;



