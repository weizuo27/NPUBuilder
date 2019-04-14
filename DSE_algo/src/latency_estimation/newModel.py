import math
from infoClass import *
from gurobipy import *
import rowStepILP
import numpy

def AlignSize(x, y):
    ret = x if (x%y == 0) else ((x/y + 1)*y)
    return ret
logFile=None

FEEDING_BUFF_DEPTH=1024

def computeWeightDepth(layerInfo, KER, PIX):
    """
    return: the minimum Weight Depth
    input layerInfo: an instance of layerInfo_t with corresponding convolution layer information
    int KER: ker factor
    int PIX: pix factor
    retutrn [WeightDepth, latLoadFeedingBuff, latProcResult, latLoadWeight, onetime]
    """

    global logFile
    conv_out_planes  = layerInfo.out_planes   
    conv_inp_planes  = layerInfo.inp_planes   
    fh= layerInfo.filter_height
    fw= layerInfo.filter_width 
    groupNum= 1+layerInfo.groupFlag;
    layerID= layerInfo.layerID;

    alignedInputPlane=AlignSize(conv_inp_planes,4);
    k=int.bit_length(   -(-alignedInputPlane*fh*fw/4)//((FEEDING_BUFF_DEPTH/2-1)) );
    if(k<0):k=0;
    straddle=1<<k;
    computePlanes=alignedInputPlane/(straddle*groupNum)
    computePlanesAligned=AlignSize(computePlanes,4)

    #find latProcResult and latLoadFeedingBuff latnecy
    latOsggBuff=PIX+8
    latCompute16Ker=(fh * fw * (computePlanesAligned/4)+1)+PIX/2+20;

    tmp = (PIX/16+1) if (PIX%16) else  (PIX/16)

    if(layerID!=0):
        latLoadFeedingBuff_fl=computePlanesAligned/64*( fw*tmp*fh*16+13)+20;
    #here we made a allowance of 0.9 to make lat loatFeeding buffer correct
    requiredNKPF = int(math.ceil(latLoadFeedingBuff_fl*0.9/latCompute16Ker))
    alignedOutputPlane = AlignSize(conv_out_planes,16)
    NKPF=min(requiredNKPF, alignedOutputPlane/KER)
    #In CHaiDNN's flow, the NKPF shall be constraint at the factor of  alignedOutputPlane/KER, however, I think it does not have to be the real factor
    #need to modify hardware

    weightDepth= AlignSize(fh*fw*computePlanesAligned/4*NKPF+1,1024)
    logFile.write(str(layerInfo.layerID)+","+str(weightDepth)+","+str( conv_out_planes)+","+str( conv_inp_planes)+","+str( straddle)+","+str( computePlanes)+","+str(  requiredNKPF)+","+str( NKPF)+","+str( alignedOutputPlane)+","+str(latLoadFeedingBuff_fl)+","+str(latCompute16Ker)+"\n" )
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
    
    # oneTime= layerInfo.oneTime

    XI_KER_PROC=IPinfo.XI_KER_PROC
    XI_PIX_PROC=IPinfo.XI_PIX_PROC
    XI_WEIGHTBUFF_DEPTH=IPinfo.XI_WEIGHTBUFF_DEPTH
    int6bit=IPinfo.int6bit



    alignedInputPlane=AlignSize(conv_inp_planes,4);
    
    k=int.bit_length( -(-alignedInputPlane*fh*fw/4)//((FEEDING_BUFF_DEPTH/2-1)) );
    if(k<0):k=0;
    straddle=1<<k;
    computePlanes=alignedInputPlane/(straddle*groupNum)
    computePlanesAligned=AlignSize(computePlanes,4)
    computeNum = fh * fw * computePlanesAligned /4
    
    latOsggBuff=XI_PIX_PROC+8
    latCompute16Ker=computeNum+XI_PIX_PROC/2+20;
    tmp= -( (-XI_PIX_PROC)//16)
    if(layerID!=0):
        latLoadFeedingBuff=computePlanesAligned/64*( fw*tmp*fh*16+13)+20;
    else:
        latLoadFeedingBuff=(computePlanesAligned/4*fh*( fw+conv_stride*(XI_PIX_PROC/2-1) )+6)*2;


    alignedOutputPlane = AlignSize(conv_out_planes,16)/groupNum
    NKPF=min( alignedOutputPlane/XI_KER_PROC, (XI_WEIGHTBUFF_DEPTH -1)/ computeNum )
    latOsggBuff_fx=XI_PIX_PROC+8
    latProcResult_fe=latOsggBuff_fx+latCompute16Ker+(NKPF-1)*max(latOsggBuff_fx,latCompute16Ker)+10
    oneTime= (straddle==1) and (NKPF==alignedOutputPlane/XI_KER_PROC);
   
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
        latReadLineBuffer=rowStep*conv_stride*( -((-conv_inp_planes)//16) *(10+conv_inp_width*1.1)+10 )

    if memIn != 0 :
        preOverhead=(fh+rowStep-1-conv_pad)*conv_stride*( -((-conv_inp_planes)//16)*(10+conv_inp_width)+10)
        latReadInputData= rowStep*conv_stride*(-((-conv_inp_planes)//16)*conv_inp_width)
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


    def __init__(self, layerInfo, IPinfo, rowStep):

        self.layerType=IPinfo.IPtype
        self.rowStep=None
        self.latProcWeight=None
        self.latLoadWeight=None
        self.latLoadWeightCurrent=None,
        self.latCompNumber=None
        self.latPreOverhead=None
        self.latReadInputData=None
        self.latWritOutputData=None
        self.height=None
        self.width=None
        self.stride=layerInfo.stride
        self.currentStartRows=0
        self.currentEndRows=0
        self.currentSegmentLatency=0;
        self.FirstEndRows=None #must initiate this before start
        self.rowStep=rowStep
        self.NrowStep=rowStep
        self.height=layerInfo.out_height
        self.currentStartRows=0;
        self.currentSegmentLatency=0;
        layerInfo.rowStep=rowStep

        if( IPinfo.IPtype== "Convolution"):
            [self.latProcWeight, self.latLoadWeight, self.latCompNumber,  self.latPreOverhead, self.latPostOverhead, self.latReadInputData, self.latWritOutputData,self.FirstEndRows,self.stride]=computeLatencyConv(layerInfo,IPinfo)
        if( IPinfo.IPtype== "Eltwise"):
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
        weightTotalCycle+=weightAmount
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
    conv_filter_height  =   layerInfo.filter_height

    IN_D=1<< int.bit_length( conv_inp_width* (-(-conv_inp_planes//64))*(conv_filter_height+(rowStep*2-1)*conv_stride) );
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

def constantBramConv(wBufferSize, ker_proc, pix_proc):
    #need validation
    wBrams = math.ceil(wBufferSize / 1024.0) * ker_proc *  math.ceil(32.0/18) * 2
    feedingBrams = 2* math.ceil(32.0/18) * pix_proc/2 * 2
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
    for i in range(len(chainLatencList)):
        overLappingWeightLatency=0;
        overLappingComputeLatency=chainLatencList[i][0]-prevLatency;
        for j in range(i, len(chainLatencList)):
            overLappingWeightLatency+=chainLatencList[j][1]*float(overLappingComputeLatency)/chainLatencList[j][0];
        totalLatency+=max(overLappingComputeLatency,overLappingWeightLatency);
        prevLatency=chainLatencList[i][0];
    return totalLatency
    


def KerPixCombSearch( K_x_P):

    if( K_x_P == 0 or  K_x_P==None): return [[0,0]];
    KerPix=[]
    K=8
    P=K_x_P/K
    while( K<=16 and P>=8 ):
        if(P > 32): 
            K=K<<1;
            P=P>>1
            continue;
        KerPix.append( [K,P] );
        K=K<<1;
        P=P>>1;
    if not KerPix: print "not valid K_x_P"
    return KerPix


def updateCombineCounter(counter,counterNum ):
    idx=0;
    while(1):
        if( idx == len(counterNum) ): return True;
        counter[idx]+=1;
        if(counter[idx]==counterNum[idx]):
            counter[idx]=0;
            idx+=1;
        else:
            break;
    return False
    


def exploitK_xPCombinations(
    roundInfoList,
    IPinfoList,
    BRAMBudget
):
    KerPixCombineList=[];
    combNumListList=[]
    for i in IPinfoList:
        KerPix=KerPixCombSearch(i.K_x_P );
        KerPixCombineList.append( KerPix);
        combNumListList.append(len(KerPix));
    counter=[0]*len(combNumListList);

    depositLatency=float("inf")
    depositRowStepChoice=[]
    depositIDepthList=[0]*len(IPinfoList)
    depositODepthList=[0]*len(IPinfoList)
    depositKer=[0]*len(IPinfoList)
    depositPix=[0]*len(IPinfoList)
    depositWeight=[0]*len(IPinfoList)

   
    while(1):
        KerPixList=[];
        for i,combinIndex in enumerate(counter):
            KerPixList.append( KerPixCombineList[i][combinIndex]);

        # call in_D, out_D, W_D, rowStep finder
        roundILPInfoList,constBram=computeRoundIPindex(
            roundInfoList, 
            KerPixList,
            IPinfoList,
            1
        );


        I=len(roundILPInfoList)
        J=len(roundILPInfoList[0])
        N=len(roundILPInfoList[0][0].IBRAMList)
        IB_nij=numpy.ndarray([N,I,J]);
        OB_nij=numpy.ndarray([N,I,J]);
        L_ij=numpy.ndarray([I,J]);


        for n in range(N):
            for i in range(I):
                for j in range(J):
                    IB_nij[n][i][j]=roundILPInfoList[i][j].IBRAMList[n];
                    OB_nij[n][i][j]=roundILPInfoList[i][j].OBRAMList[n];
        for i in range(I):
            for j in range(J):
                L_ij[i][j]=roundILPInfoList[i][j].latency;
        BRAMbudget_ID=BRAMBudget-constBram;
        rowStepChoice,InIdx,OutIdx,ILPlatency=rowStepILP.rowStepILP( BRAMbudget_ID, IB_nij, OB_nij, L_ij, N, I, J);
        
            

        if( ILPlatency !=None and ILPlatency< depositLatency):
            depositLatency=ILPlatency;
            depositRowStepChoice=rowStepChoice
            depositIDepthList=[0]*len(IPinfoList)
            depositODepthList=[0]*len(IPinfoList)
            depositKer=[0]*len(IPinfoList)
            depositPix=[0]*len(IPinfoList)
            depositWeight=[0]*len(IPinfoList)
            depositIPindex=roundILPInfoList[0][0].IPindexList;
            for n in range(N):
                [i,j]=InIdx[n]
                depositIDepthList[depositIPindex[n]]=roundILPInfoList[i][j].InDepthList[n]
                [i,j]=OutIdx[n]
                depositODepthList[depositIPindex[n]]=roundILPInfoList[i][j].OutDepthList[n]
            for n in range(len(IPinfoList)):
                depositKer[n]=IPinfoList[n].XI_KER_PROC;
                depositPix[n]=IPinfoList[n].XI_PIX_PROC;
                depositWeight[n]=IPinfoList[n].XI_WEIGHTBUFF_DEPTH
       
        if(ILPlatency==None  ):
            print "ker, Pix configuration", KerPixList, "does not have feasible solution";

        if(updateCombineCounter(counter,combNumListList) ): break;

    if( not depositRowStepChoice):
        print "Feasible Solution not found in KP iteration";
        return None
    for n in range(len(IPinfoList)):
        IPinfoList[n].XI_KER_PROC=depositKer[n];
        IPinfoList[n].XI_PIX_PROC=depositPix[n];
        IPinfoList[n].XI_WEIGHTBUFF_DEPTH=depositWeight[n];
        IPinfoList[n].XI_INDEPTH=depositIDepthList[n];
        IPinfoList[n].XI_OUTDEPTH=depositODepthList[n];
    # for i,roundILPInfoList_row in enumerate( roundILPInfoList):
    #     rowStepNum=rowStepChoice[i];
    #     for roundILPInfo in roundILPInfoList_row:
    #         roundILPInfo.layerInfo.rowStep=rowStepNum
    return rowStepChoice, depositLatency
    

        







    

def computeRoundIPindex(
    roundInfoList, #list of runInfo_t[], runInfo_t 
    KerPixList, #list of [Ker, Pix] tuples for each IP, if the IP is not a conv IP, then  [Ker, Pix] = [0,0]
    IPinfoList, #list of IPinfo, the only specified value in each element should only be IPtype and K_x_P
    logIdx=None
):
    global logFile
    if(logIdx != None ):
        logFile=open("scheduling"+str(logIdx)+".log","w");
    logFile.write("IPIdx,weightDepth, out_planes, inp_planes, straddle, computePlanes,  requiredNKPF, NKPF, alignedOutputPlane,latLoadFeedingBuff_fl,latCompute16Ker\n")
    #1. choose the weight depth by finding the largest weight depth that is optimal result
    weightDepthList=[0]*len(KerPixList);
    for runInfoList in roundInfoList:
        for runInfo in runInfoList:
            if( IPinfoList[runInfo.IPidx].IPtype=="Convolution" ):
                Ker, Pix=KerPixList[runInfo.IPidx]
                weightDepth=computeWeightDepth(runInfo.layerInfo,Ker,Pix);
                if(weightDepthList[runInfo.IPidx]< weightDepth):
                    weightDepthList[runInfo.IPidx]=weightDepth;
    logFile.write("Computing Constant BRAM result\n")
    constBram=0;
    for i, IPinfo in enumerate(IPinfoList):
        if( IPinfo.IPtype=="Convolution"):
            Ker, Pix=KerPixList[i]
            constBramIP=constantBramConv(weightDepthList[i],Ker, Pix);
            constBram+=constBramIP
            IPinfoList[i].XI_WEIGHTBUFF_DEPTH=weightDepthList[i];
            IPinfoList[i].XI_KER_PROC=Ker;
            IPinfoList[i].XI_PIX_PROC=Pix;
            logFile.write("Convolution,"+str(Ker)+","+str(Pix)+","+str(weightDepthList[i])+","+str(constBramIP)+"\n")
        elif( IPinfo.IPtype=="Pooling"):
            constBram+=constantBramPool();
            logFile.write("Pooling,"+str(constantBramPool())+"\n")
        elif( IPinfo.IPtype=="Eltwise"):
            constBram+=constantBramEle();
            logFile.write("Eltwise,"+str(constantBramEle())+"\n")
        else:
            assert(0), "Unsupported IP type"


    roundILPInfoList=[];
    for roundIdx in range(len(roundInfoList)):
        roundILPInfoList_row=[];
        for rowStep in range(1,7):
            IOBRAM={}
            logFile.write("Round Latency Compute:"+str(roundIdx)+","+str(rowStep)+"\n");
            for runInfo in roundInfoList[roundIdx]:
                if( IPinfoList[runInfo.IPidx].IPtype=="Convolution"):
                    IN_D,OUT_D = computeRequiredIODepth( runInfo.layerInfo, rowStep)
                    inBrams, outBrams = computeIOBram(IN_D,OUT_D)
                    IOBRAM[runInfo.IPidx]=[inBrams,outBrams,IN_D,OUT_D ]
            chainLatencList=[];
            runChain=[];
            startIdx=0;
            while( startIdx < len(roundInfoList[roundIdx]) ):
                runInfo=roundInfoList[roundIdx][startIdx]
                IPinfoInst=IPinfoList[runInfo.IPidx];
                layerInfoInst=runInfo.layerInfo;
                runChain.append([layerInfoInst,IPinfoInst]);
                if(runInfo.nextIPidx == None):
                    layerLatencyInfoList=[]
                    for i in range( len(runChain) ):
                        layerInfoInst,IPinfoInst=runChain[i];
                        x=layerLatencyInfo_t(layerInfoInst,IPinfoInst,rowStep);
                        logFile.write(IPinfoInst.IPtype+","+str(IPinfoInst.IPidx)+","+str(x.latProcWeight)+","+str(x.latLoadWeight)+","+str(x.latCompNumber)+","+str(x.latPreOverhead)+","+str(x.latPostOverhead)+","+str(x.latReadInputData)+","+str(x.latWritOutputData)+","+str(x.FirstEndRows)+","+str(x.stride)+"\n");
                        layerLatencyInfoList.append(x)
                    cycles,weigthCycles=computeLatencyPipe(layerLatencyInfoList);
                    logFile.write("chainCycles: "+str(int(cycles) )+", weight Cycles: "+str(int(weigthCycles))+"\n")
                    chainLatencList.append([cycles,weigthCycles]);
                startIdx=startIdx+1;
            latency=multiChainLatency(chainLatencList);
            roundILPInfo=roundILPInfo_t();
            roundILPInfo.roundIdx=roundIdx;
            roundILPInfo.rowStep=rowStep;
        
            roundILPInfo.latency=latency;
            for i in range(len(IPinfoList)):
                if ( IPinfoList[i].IPtype=="Convolution" ):
                    roundILPInfo.IPindexList.append(i);
                    if i in IOBRAM:
                        inBrams,outBrams,IN_D,OUT_D=IOBRAM[i]
                        roundILPInfo.IBRAMList.append(inBrams)
                        roundILPInfo.OBRAMList.append(outBrams)
                        roundILPInfo.InDepthList.append(IN_D)
                        roundILPInfo.OutDepthList.append(OUT_D)
                    else:
                        roundILPInfo.IBRAMList.append(0)
                        roundILPInfo.OBRAMList.append(0)
                        roundILPInfo.IBRAMList.append(0)
                        roundILPInfo.OBRAMList.append(0)
            roundILPInfo.ConstantBRAM=constBram;
            roundILPInfoList_row.append(roundILPInfo);
        roundILPInfoList.append(roundILPInfoList_row);
    logFile.close();
    return roundILPInfoList,constBram


# IPlist=[];
# x=IPinfo_t(K_x_P=512)
# x.IPidx=0;
# IPlist.append(x)
# x=IPinfo_t(K_x_P=256)
# x.IPidx=0;
# IPlist.append(x)
# x=IPinfo_t(K_x_P=128)
# x.IPidx=0;
# IPlist.append(x)
# x=IPinfo_t(K_x_P=64)
# x.IPidx=0;
# IPlist.append(x)



# exploitK_xPCombinations(None,IPlist );
# KerPixList=[ [16,16],[0,0],[0,0],[16,32] ]

# IPlist=[]
# runList=[]

# x=IPinfo_t()
# x.IPidx=0;
# x.IPtype="Convolution"
# x.K_x_P=512
# IPlist.append(x)

# x=IPinfo_t()
# x.IPidx=1;
# x.IPtype="Eltwise"
# IPlist.append(x)

# x=IPinfo_t()
# x.IPidx=2;
# x.IPtype="Pooling"
# IPlist.append(x)

# x=IPinfo_t()
# x.IPidx=3;
# x.IPtype="Convolution"
# x.K_x_P=256
# IPlist.append(x)



# y=layerInfo_t()
# y.layerType="Convolution"
# y.inp_height=28
# y.inp_width=28
# y.out_height=28
# y.out_width=28
# y.out_planes=512
# y.inp_planes=1024
# y.stride=1
# y.filter_height=3
# y.filter_width=3
# y.pad=1
# y.groupFlag=0
# y.layerID=3
# y.memIn=1
# y.memInL=None
# y.memInR=None
# y.memOut=1
# y.rowStep=None
# z=runInfo_t()
# z.IPidx=3;
# z.layerInfo=y

# runList.append(z)


# y=layerInfo_t()
# y.layerType="Convolution"
# y.inp_height=28
# y.inp_width=28
# y.out_height=28
# y.out_width=28
# y.out_planes=1024
# y.inp_planes=512
# y.stride=1
# y.filter_height=3
# y.filter_width=3
# y.pad=1
# y.groupFlag=0
# y.layerID=3
# y.memIn=1
# y.memInL=None
# y.memInR=None
# y.memOut=0

# z=runInfo_t()
# z.IPidx=0;
# z.layerInfo=y
# z.nextIPidx=1
# runList.append(z)

# x=IPinfo_t()
# x.IPidx=0;
# x.IPtype="Eltwise"
# y=layerInfo_t()
# y.layerType="Eltwise"
# y.inp_height=28
# y.inp_width=28
# y.out_height=28
# y.out_width=28
# y.out_planes=1024
# y.inp_planes=512
# y.stride=1
# y.filter_height=3
# y.filter_width=3
# y.pad=1
# y.groupFlag=0
# y.layerID=3
# y.memIn=None
# y.memInL=1
# y.memInR=0
# y.memOut=0

# z=runInfo_t()
# z.IPidx=1;
# z.layerInfo=y
# runList.append(z)

# roundList=[]
# roundList.append(runList)

# # computeRoundIPindex(roundList,KerPixList,IPlist,1)



    
# exploitK_xPCombinations(roundList,IPlist, 1450)







