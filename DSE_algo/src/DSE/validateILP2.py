import infoClass
import newModel
from infoClass import *
import math
import numpy
import rowStepILP

def AlignSize(x, y):
    ret = x if (x%y == 0) else ((x/y + 1)*y)
    return ret

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
    OUT_D= AlignSize( int( conv_out_width*math.ceil(conv_inp_planes/32)*rowStep ) , 1024)
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



def generateKxPChoiceList(IPinfoList):
    KxPChoiceList=[]
    KxPChoiceNumList=[]
    for IPinfo in IPinfoList:
        KxPChoice=KerPixCombSearch(IPinfo.K_x_P);
        KxPChoiceList.append(KxPChoice);
        KxPChoiceNumList.append(len(KxPChoice));
    return KxPChoiceList,KxPChoiceNumList


def updateK_Pchain(KxPChoiceList, counter, counterNum ):
    K_PList=[]
    for idx,choiceIdx in  enumerate(counter):
        K_PList.append( KxPChoiceList[idx][choiceIdx] );
    End=updateCombineCounter(counter,counterNum);
    return End,K_PList

def generateWeightChoiceList(IPinfoList):
    weightChoiceList=[]
    weightChoiceNumList=[]
    for IPinfo in IPinfoList:
        if IPinfo.IPtype=="Convolution":      
            weightChoice=[1024,2048,3072,4096]
        else:
            weightChoice=[0]
        weightChoiceList.append(weightChoice);
        weightChoiceNumList.append(len(weightChoice));
    return weightChoiceList,weightChoiceNumList






def generateRunInfo(
    roundInfoList, #list of runInfo_t[], runInfo_t 
    KerPixList, #list of [Ker, Pix] tuples for each IP, if the IP is not a conv IP, then  [Ker, Pix] = [0,0]
    IPinfoList, #list of IPinfo, the only specified value in each element should only be IPtype and K_x_P
    weightDepthList,
    bramBudget
):
    constBram=0;
    for i, IPinfo in enumerate(IPinfoList):
        if( IPinfo.IPtype=="Convolution"):
            Ker, Pix=KerPixList[i]
            constBramIP=constantBramConv(weightDepthList[i],Ker, Pix);
            constBram+=constBramIP
            IPinfoList[i].XI_WEIGHTBUFF_DEPTH=weightDepthList[i];
            IPinfoList[i].XI_KER_PROC=Ker;
            IPinfoList[i].XI_PIX_PROC=Pix;
            # logFile.write("Convolution,"+str(Ker)+","+str(Pix)+","+str(weightDepthList[i])+","+str(constBramIP)+"\n")
        elif( IPinfo.IPtype=="Pooling"):
            constBram+=constantBramPool();
            IPinfo.BRAM=constantBramPool();
            # logFile.write("Pooling,"+str(constantBramPool())+"\n")
        elif( IPinfo.IPtype=="Eltwise"):
            constBram+=constantBramEle();
            IPinfo.BRAM=constantBramEle();
            # logFile.write("Eltwise,"+str(constantBramEle())+"\n")
        else:
            assert(0), "Unsupported IP type"

    if constBram > bramBudget:
        return False, False

    roundILPInfoList=[];
    for roundIdx in range(len(roundInfoList)):
        roundILPInfoList_row=[];
        for rowStep in range(1,7):
            IOBRAM={}
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
                        x=newModel.layerLatencyInfo_t(layerInfoInst,IPinfoInst,rowStep);
                        layerLatencyInfoList.append(x)
                    cycles,weigthCycles=newModel.computeLatencyPipe(layerLatencyInfoList);
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
                        roundILPInfo.InDepthList.append(0)
                        roundILPInfo.OutDepthList.append(0)
            roundILPInfo.ConstantBRAM=constBram;
            roundILPInfoList_row.append(roundILPInfo);
        roundILPInfoList.append(roundILPInfoList_row);
    return roundILPInfoList,constBram



def generateILPinput(
    roundILPInfoList):
    
    I=len(roundILPInfoList)
    J=len(roundILPInfoList[0])
    N=len(roundILPInfoList[0][0].IBRAMList)
    IB_nij=numpy.ndarray([N,I,J]);
    OB_nij=numpy.ndarray([N,I,J]);
    L_ij=numpy.ndarray([I,J]);


    for i in range(I):
        for j in range(J):
            L_ij[i][j]=roundILPInfoList[i][j].latency;
    for n in range(N):
        for i in range(I):
            for j in range(J):
                IB_nij[n][i][j]=roundILPInfoList[i][j].IBRAMList[n];
                OB_nij[n][i][j]=roundILPInfoList[i][j].OBRAMList[n];
    return IB_nij, OB_nij, L_ij, N, I, J

def updateDepositArrays(
    weightList,
    IPinfoList,
    roundILPInfoList,
    rowStepChoice,
    ILPlatency,
    InIdx,
    OutIdx,
    N
):
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
        depositWeight[n]=weightList[n]
    return depositLatency,depositRowStepChoice,depositIDepthList,depositODepthList,depositKer,depositPix,depositIPindex,depositWeight


def updateIPinfo_RoundInfo(
    depositKer,depositPix,depositWeight,depositIDepthList,depositODepthList,depositRowStepChoice,
    IPinfoList,roundInfoList

):
    
    for n in range(len(IPinfoList)):
        IPinfoList[n].XI_KER_PROC=depositKer[n];
        IPinfoList[n].XI_PIX_PROC=depositPix[n];
        IPinfoList[n].XI_WEIGHTBUFF_DEPTH=depositWeight[n];
        IPinfoList[n].XI_INDEPTH=depositIDepthList[n];
        IPinfoList[n].XI_OUTDEPTH=depositODepthList[n];
        print "[IPINFO]",IPinfoList[n].XI_KER_PROC, IPinfoList[n].XI_PIX_PROC, IPinfoList[n].XI_WEIGHTBUFF_DEPTH, IPinfoList[n].XI_INDEPTH, IPinfoList[n].XI_OUTDEPTH

    for i in IPinfoList:
        if(i.IPtype=="Convolution"):
            i.IBRAM,i.OBRAM = computeIOBram(i.XI_INDEPTH, i.XI_OUTDEPTH);
            i.OtherBRAM = constantBramConv(i.XI_WEIGHTBUFF_DEPTH,i.XI_KER_PROC, i.XI_PIX_PROC);
            i.WBRAM=  math.ceil(i.XI_WEIGHTBUFF_DEPTH / 1024.0) * i.XI_KER_PROC *  math.ceil(32.0/18) * 2
            i.BRAM= i.IBRAM+i.OBRAM+i.OtherBRAM;
        else:
            i.IBRAM=0;
            i.OBRAM=0;
            i.WBRAM=0;
            i.OtherBRAM=0;
    for i,roundInfoList_row in enumerate( roundInfoList):
        rowStepNum=depositRowStepChoice[i];
        for roundILPInfo in roundInfoList_row:
            roundILPInfo.layerInfo.rowStep=rowStepNum

def exploitK_xPCombinationsValidation(
    roundInfoList,
    IPinfoList,
    BRAMBudget
):
    KxPChoiceList,KxPChoiceNumList=generateKxPChoiceList(IPinfoList);
    weightChoiceList,weightChoiceNumList=generateWeightChoiceList(IPinfoList);
    KxPCounter=[0]*len(KxPChoiceNumList)
    depositLatency=float("inf")

    depositRowStepChoice=[]
    depositIDepthList=[0]*len(IPinfoList)
    depositODepthList=[0]*len(IPinfoList)
    depositKer=[0]*len(IPinfoList)
    depositPix=[0]*len(IPinfoList)
    depositWeight=[0]*len(IPinfoList)
    depositIPindex=[]

    while(1):
        EndFlagKxP,KxPList=updateK_Pchain(KxPChoiceList,KxPCounter,KxPChoiceNumList);
        WeightCounter=[0]*len(weightChoiceNumList)  
        
        while(1):
            EndFlgWeight,weightList = updateK_Pchain(weightChoiceList,WeightCounter,weightChoiceNumList)
            print KxPList,weightList
            roundILPInfoList,constBram=generateRunInfo(roundInfoList,KxPList,IPinfoList,weightList,BRAMBudget)
            if constBram == False:
                if EndFlgWeight: break;
                else: continue;
            
            IB_nij, OB_nij, L_ij, N, I, J=generateILPinput(roundILPInfoList);
            rowStepChoice,InIdx,OutIdx,ILPlatency=rowStepILP.rowStepILP( BRAMBudget-constBram, IB_nij, OB_nij, L_ij, N, I, J);
            
            if( ILPlatency !=None and ILPlatency< depositLatency):
                depositLatency,depositRowStepChoice,depositIDepthList,depositODepthList,depositKer,depositPix,depositIPindex,depositWeight=updateDepositArrays(
                    weightList,IPinfoList,roundILPInfoList,rowStepChoice,ILPlatency,InIdx,OutIdx,N)
                print depositLatency,depositRowStepChoice
         
            if EndFlgWeight: break;
        if EndFlagKxP: break;
    
    if( not depositRowStepChoice):
        print "Feasible Solution not found in KP iteration";
        return None,None
    print depositWeight
    updateIPinfo_RoundInfo( depositKer,depositPix,depositWeight,depositIDepthList,depositODepthList,depositRowStepChoice,
    IPinfoList,roundInfoList)

    return depositRowStepChoice, depositLatency
    