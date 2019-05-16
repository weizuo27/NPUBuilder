import infoClass
import newModel
from infoClass import *
import math
import numpy
import rowStepILP

import RowStepILP

def AlignSize(x, y):
    ret = x if (x%y == 0) else ((x/y + 1)*y)
    return ret
def CeilDiv(x,y): return  -(-x//y)


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
    
    OUT_D= AlignSize( int( conv_out_width*CeilDiv(conv_out_planes,32)*rowStep ) , 1024)
    return [IN_D,OUT_D]
    
def computeIOBram(IN_D,OUT_D):
    inBrams = 2*math.ceil(IN_D/1024.0) * 8 * 2 * math.ceil(32.0/18)
    outBrams = 2*math.ceil(OUT_D/1024.0) * 8 * math.ceil(72.0/18) * 2
    return [inBrams, outBrams]

def computeIODepth(inBrams,outBrams):
    IN_D=inBrams/32/math.ceil(32.0/18)*1024
    OUT_D=outBrams/32/math.ceil(72.0/18) *1024
    return [IN_D, OUT_D]

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
        KerPix.append( (K,P) );
        K=K<<1;
        P=P>>1;
    if not KerPix: print "not valid K_x_P"
    return KerPix

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
    groupInfoList,
    # roundInfoList, #list of runInfo_t[], runInfo_t 
    KerPixList, #list of [Ker, Pix] tuples for each IP, if the IP is not a conv IP, then  [Ker, Pix] = [0,0]
    IPinfoList, #list of IPinfo, the only specified value in each element should only be IPtype and K_x_P
    weightDepthList,
    bramBudget):
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

    groupILPinfoList=[]

    IOBRAM={}
    for g,groupSolutionPool in enumerate(groupInfoList):
        solutionPoolRoundInfoList=[]
        for s,roundInfoList in enumerate(groupSolutionPool):
            roundILPInfoList=[]
            for roundIdx in range(len(roundInfoList)):
                roundILPInfoList_row=[];
                for rowStep in range(1,7):
                    for runInfo in roundInfoList[roundIdx]:
                        if( IPinfoList[runInfo.IPidx].IPtype=="Convolution"):
                            IN_D,OUT_D = computeRequiredIODepth( runInfo.layerInfo, rowStep)
                            inBrams, outBrams = computeIOBram(IN_D,OUT_D)
                            IOBRAM[runInfo.IPidx]=[inBrams,outBrams,IN_D,OUT_D]


                    latency=int(newModel.computeRoundLatency(roundInfoList[roundIdx], IPinfoList,rowStep) );                        
                        
    
                    
                    roundILPInfo=roundILPInfo_t();
                    roundILPInfo.roundIdx=roundIdx;
                    roundILPInfo.rowStep=rowStep;
                    roundILPInfo.latency=latency;

                    for i in range(len(IPinfoList)):
                        if ( IPinfoList[i].IPtype=="Convolution" ):
                            if i in IOBRAM:
                                inBrams,outBrams,IN_D,OUT_D=IOBRAM[i]
                                roundILPInfo.IBRAMList.append(inBrams)
                                roundILPInfo.OBRAMList.append(outBrams)
                            else:
                                roundILPInfo.IBRAMList.append(0)
                                roundILPInfo.OBRAMList.append(0)


                    roundILPInfo.ConstantBRAM=constBram;
                    roundILPInfoList_row.append(roundILPInfo);
                roundILPInfoList.append(roundILPInfoList_row);
            solutionPoolRoundInfoList.append(roundILPInfoList);
        groupILPinfoList.append(solutionPoolRoundInfoList);
    return groupILPinfoList,constBram
    
def generateILPinput(
    groupILPinfList):

    IB_gsrkn=[];OB_gsrkn=[];L_gsrk=[]
    for g,groupSolutionPool in enumerate(groupILPinfList):
        IB_srkn=[];OB_srkn=[];L_srk=[]
        for s,solutionCandidates in enumerate(groupSolutionPool):
            IB_rkn=[];OB_rkn=[];L_rk=[]
            
            for r,roundILP_row in enumerate(solutionCandidates):
                IB_kn=[];OB_kn=[];L_k=[]
                
                for k,roundILP in enumerate(roundILP_row):
                    IB_n=[];OB_n=[]
                    for n in range( len(roundILP.IBRAMList) ):
                        IB_n.append(roundILP.IBRAMList[n])
                        OB_n.append(roundILP.OBRAMList[n])
                    
                    IB_kn.append(IB_n);OB_kn.append(OB_n);L_k.append( roundILP.latency)
                IB_rkn.append(IB_kn);OB_rkn.append(OB_kn);L_rk.append(L_k)
            IB_srkn.append(IB_rkn); OB_srkn.append(OB_rkn); L_srk.append(L_rk)
        IB_gsrkn.append(IB_srkn);OB_gsrkn.append(OB_srkn);L_gsrk.append(L_srk)

        
    return IB_gsrkn,OB_gsrkn,L_gsrk,len(OB_gsrkn[0][0][0][0])
            
                        
                    
def updateDepositArrays(
    length,
    IPindexList,
    InDepthList,
    OutDepthList):
  
   
    depositIDepthList=[0]*length
    depositODepthList=[0]*length


    for n in range(len(IPindexList)):
        depositIDepthList[IPindexList[n]]=InDepthList[n]
        depositODepthList[IPindexList[n]]=OutDepthList[n]

    return depositIDepthList,depositODepthList


# def updateIPinfo_RoundInfo(
def updateIPinfo_RoundInfo( depositKxPlist,depositWeight,depositIDepthList,depositODepthList,IPinfoList):
    
    for n in range(len(IPinfoList)):
        k,p=depositKxPlist[n]
        IPinfoList[n].XI_KER_PROC=k;
        IPinfoList[n].XI_PIX_PROC=p;
        IPinfoList[n].XI_WEIGHTBUFF_DEPTH=depositWeight[n];
        IPinfoList[n].XI_INDEPTH=depositIDepthList[n];
        IPinfoList[n].XI_OUTDEPTH=depositODepthList[n];

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


def IOBRAMtoIODEPTH(IB, OB,    IDEPTH,   ODEPTH, convIPNum):

    for i in range(convIPNum):
        ID,OD=computeIODepth(IB[i],OB[i]);
        IDEPTH.append(ID)
        ODEPTH.append(OD)


def computeLatencyValidate(
        IB_gsrkn,
        OB_gsrkn,
        L_gsrk,
        budget,
        ConvIPNum,
        IBRAM,
        OBRAM,
        groupChoice,
        testLatency
    ):
    
    if sum(IBRAM)+sum(OBRAM) > budget:
        print "BRAM exceeding budget"
        return False
    TotalLatency=0;

    for gIdx,L_srk in enumerate(L_gsrk):
        sIdx=groupChoice[gIdx][0]
        rowStepTable=groupChoice[gIdx][1]
        L_rk=L_srk[sIdx];
        for rIdx,L_k in enumerate(L_rk):
            rowStep=rowStepTable[rIdx];
            latency=L_k[rowStep];
            for n in range(ConvIPNum ):
                if IBRAM[n] < IB_gsrkn[gIdx][sIdx][rIdx][rowStep][n] or OBRAM[n] < OB_gsrkn[gIdx][sIdx][rIdx][rowStep][n]:
                    print "BRAM cannot Hold RowStep"
                    return False
            TotalLatency+=latency
        
    if TotalLatency != testLatency:
        print "Latency not computed correctly", TotalLatency,testLatency
        return False
    print "Solution valid and correct"
    return True




def brutalSearchSolution(
    IB_gsrkn,
    OB_gsrkn,
    L_gsrk,
    budget,
    ConvIPNum
    
    ):

    IDEPTHTABLE=[1024,2048,4096]
    ODEPTHTABLE=[1024,2048,3072]
    IBRAMTABLE=[None]*3;
    OBRAMTABLE=[None]*3;

    for i in range(3):
        IBRAMTABLE[i],OBRAMTABLE[i]=computeIOBram(IDEPTHTABLE[i],ODEPTHTABLE[i])
    IDEPTHcounterNum=[3]*ConvIPNum;
    ODEPTHcounterNum=[3]*ConvIPNum;
    ODEPTHcounter=[0]*ConvIPNum;
    IDEPTHcounter=[0]*ConvIPNum;

    IBRAM=[None]*ConvIPNum;
    OBRAM=[None]*ConvIPNum;

    depositTotalLatency=float("inf")
    depositTotalSolutionChoice=[]
    depositIBRAM=[]
    depositOBRAM=[]

    while 1:
        for i in range(ConvIPNum):
            IBRAM[i]=IBRAMTABLE[ IDEPTHcounter[i]];

        ODEPTHcounterNum=[3]*ConvIPNum;
        ODEPTHcounter=[0]*ConvIPNum;

        while 1:
            for i in range(ConvIPNum):
                OBRAM[i]=OBRAMTABLE[ ODEPTHcounter[i]];
            if sum(OBRAM)+sum(IBRAM) > budget:
                if updateCombineCounter(ODEPTHcounter,ODEPTHcounterNum ): break;
                continue
            TotalLatency=0;
            TotalRowStepTable=[];
            TotalSolutionChoice=[]
            for g,L_srk in enumerate(L_gsrk):
                groupValid=False;
                depositSolutionLatency=float("inf")
                depositSolutionChoice=None
                for s,L_rk in enumerate(L_srk):
                    SolutionValid=True;
                    SolutionLatency=0;
                    rowStepTable=[]
                    for r,L_k in enumerate(L_rk):
                        RoundLatency=float("inf")
                        for k,L in enumerate(L_k):
                            RowStepValid=True
                            for n in range(ConvIPNum):
                                if IB_gsrkn[g][s][r][k][n] > IBRAM[n] or OB_gsrkn[g][s][r][k][n] > OBRAM[n]: 
                                    RowStepValid=False;
                                    break;
                            if RowStepValid and L<RoundLatency:
                                RoundLatency=L
                                rowStep=k
                        if RoundLatency==float("inf"):
                            SolutionValid=False;
                            break;
                        else:
                            SolutionLatency+=RoundLatency;
                            rowStepTable.append(rowStep);
                    if SolutionValid and SolutionLatency<depositSolutionLatency:
                        depositSolutionLatency=SolutionLatency;
                        depositSolutionChoice=(s,rowStepTable);
                        groupValid=True
                if groupValid == False:
                    break;
                else:
                    TotalLatency+=depositSolutionLatency;
                    TotalSolutionChoice.append(depositSolutionChoice)
            if groupValid and TotalLatency < depositTotalLatency:
                depositTotalLatency=TotalLatency
                depositTotalSolutionChoice=TotalSolutionChoice
                depositIBRAM=copy.deepcopy(IBRAM)
                depositOBRAM=copy.deepcopy(OBRAM)

            if updateCombineCounter(ODEPTHcounter,ODEPTHcounterNum ): break;

        if updateCombineCounter(IDEPTHcounter,IDEPTHcounterNum ): break;

    return depositIBRAM,depositOBRAM,depositTotalSolutionChoice,depositTotalLatency



def checkConcstraint(IB_gsrkn,OB_gsrkn,L_gsrk,budget,
    groupChoice, # list [(solutionIdx,[rowStep])
    ConvIPnum,
    IBrst,OBrst):
    Y_gs=[]
    X_gsrk=[]
    IB_n=[]
    IB_gsrn=[]
    OB_n=[]
    OB_gsrn=[]


    for g in range(len(L_gsrk)):
        Y_s=[];
        X_s=[]
        sIdx,rowStepAray=groupChoice[g]
        for s in range( len(L_gsrk[g]) ):
            if(s==sIdx):
                Y_s.append(1);
            else:
                Y_s.append(0);
            X_r=[]
            print "Group",g,"Solution",s,
            for r in  range(len( L_gsrk[g][s]) ):
                X_k=[]
                if(s==sIdx ):
                    rowStep=rowStepAray[r];
                else:
                    rowStep=None
                for k in range(len( L_gsrk[g][s][r]) ):
                    if( k ==rowStep and s==sIdx):
                        X_k.append(1);
                    else:
                        X_k.append(0);
                print "(",
                for n in range(ConvIPnum):
                    exprI=0
                    for k,X in enumerate(X_k):
                        exprI+=IB_gsrkn[g][s][r][k][n]*X
                    print exprI,
                print ")",
                X_r.append(X_k);
            print ""
            
            

            X_s.append(X_r);
        Y_gs.append(Y_s)
        X_gsrk.append(X_s)


    


    for g in range(len(L_gsrk)):
        I_g=[]
        O_g=[]
        for s in range( len(L_gsrk[g]) ):
            I_s=[]
            O_s=[]
            for r in  range(len( L_gsrk[g][s]) ):
                I_r=[]
                O_r=[]
                for n in range(ConvIPnum):
                    I_r.append(None)
                    O_r.append(None)
                I_s.append(I_r)
                O_s.append(O_r)
            I_g.append(I_s)
            O_g.append(O_s)
        IB_gsrn.append(I_g)
        OB_gsrn.append(O_g)

    
    for g,X_g in enumerate(X_gsrk):
        for s,X_s in enumerate(X_g):
            for r,X_r in enumerate(X_s):
                for n in range(ConvIPnum):
                    exprI=0;
                    exprO=0;
                    for k,X_k in enumerate(X_r):
                        exprI+=IB_gsrkn[g][s][r][k][n]*X_k
                        exprO+=OB_gsrkn[g][s][r][k][n]*X_k
                    IB_gsrn[g][s][r][n]=exprI
                    OB_gsrn[g][s][r][n]=exprO
 
    IB_n=IBrst
    OB_n=OBrst


    for g,Y_s in enumerate(Y_gs):
        if sum(Y_s) !=1:
            print "Constraint 1 is not fufilled"
            exit()

    for g,X_g in enumerate(X_gsrk):
        for s,X_s in enumerate(X_g):
            for r in X_s:
                expr=0;
                for k in r:
                    expr+=k;
                if (expr != Y_gs[g][s]):
                    print "Constraint 2 is not fufilled"
                    exit()

    for g,X_srk in enumerate(X_gsrk):
        for s,X_rk in enumerate(X_srk):
            for r,X_k in enumerate(X_rk):
                for n in range(ConvIPnum):
                    exprI=0;
                    exprO=0;
                    count=0
                    for k,X in enumerate(X_k):
                        if X : count+=1;
                        exprI+=X*IB_gsrkn[g][s][r][k][n];
                        exprO+=X*OB_gsrkn[g][s][r][k][n];
                    if count>1:
                        print "Solution:",g,s,r,n,"is scheduled with", counter,"rowSteps"
                    if IB_gsrn[g][s][r][n]!=exprI or OB_gsrn[g][s][r][n]!=exprO:
                        print "Constraint 3 is not fufilled";
                        exit()

    IB_flatten=[]
    OB_flatten=[]
  
    for n in range(ConvIPnum): 
        IB_flatten_n=[]
        OB_flatten_n=[]
        for g,I_g in enumerate(IB_gsrn):
            for s,I_s in enumerate(I_g):
                for r,I_r in enumerate(I_s):
                    IB_flatten_n.append(IB_gsrn[g][s][r][n]);
                    OB_flatten_n.append(OB_gsrn[g][s][r][n]);
        IB_flatten.append(IB_flatten_n)
        OB_flatten.append(OB_flatten_n)          
                
                    
                
   
     
    print IB_flatten[1]

    
    for n in range(ConvIPnum):
        if IB_n[n]<max(IB_flatten[n]) or  OB_n[n]<max(OB_flatten[n]) :
            print "Constraint 4 is not fufilled",max(IB_flatten[n]),IB_n[n],max(OB_flatten[n]),OB_n[n],n
            exit()
    
    expr=0;
    
    for n in range(ConvIPnum):
        expr+= IB_n[n] 
        expr+= OB_n[n] 
    if expr > budget:
        print "Constraint 5 is not fufilled";
        exit()
    

    



def exploitK_xPCombinationsValidation(
    groupSolutionList,
    IPinfoList,
    BRAMBudget
):
    """
    groupSolutionList: a list of groupSolutionPool 
    groupSolutionPool: a list of rouldInfoList, each  rouldInfoList is a candidate of the roundInfo
    IPinfoList, a list of IP info
    """

    KxPChoiceList,KxPChoiceNumList=generateKxPChoiceList(IPinfoList);
    weightChoiceList,weightChoiceNumList=generateWeightChoiceList(IPinfoList);
    KxPCounter=[0]*len(KxPChoiceNumList)
    
    depositLatency=float("inf")


        
    depositIDepthList=[]
    depositODepthList=[]
    depositKxPlist=[]
    depositWeight=[]
    depositsolutionChoice=[]


    IPindexList=[]
    for i in range(len(IPinfoList)):
        if ( IPinfoList[i].IPtype=="Convolution" ):
            IPindexList.append(i);

    while(1):
        EndFlagKxP,KxPList=updateK_Pchain(KxPChoiceList,KxPCounter,KxPChoiceNumList);
        WeightCounter=[0]*len(weightChoiceNumList)  
        
        while(1):
            EndFlgWeight,weightList = updateK_Pchain(weightChoiceList,WeightCounter,weightChoiceNumList)

            groupILPInfoList,constBram=generateRunInfo(groupSolutionList,KxPList,IPinfoList,weightList,BRAMBudget)

            if constBram == False:
                if EndFlgWeight: break;
                else: continue;

            IB_gsrkn,OB_gsrkn,L_gsrk,ConvIPNum=generateILPinput(groupILPInfoList);
            #iterate through all the IO depth combinations, find the best rowstep solution:

            IBrst2,OBrst2,solutionChoice2,ILPlatency2=brutalSearchSolution(IB_gsrkn,OB_gsrkn, L_gsrk, BRAMBudget-constBram, ConvIPNum);
            IBrst,OBrst,solutionChoice,ILPlatency= RowStepILP.RowStepILP(IB_gsrkn,OB_gsrkn, L_gsrk, BRAMBudget-constBram, ConvIPNum);

            # checkConcstraint(IB_gsrkn,OB_gsrkn,L_gsrk,BRAMBudget-constBram, solutionChoice2, ConvIPNum,IBrst2,OBrst2)
    
            if  not( ILPlatency2==float("inf") and ILPlatency==None) and  ILPlatency2!=ILPlatency:
                print "validation fail",ILPlatency2,ILPlatency

                if ILPlatency!=None:
                    computeLatencyValidate(
                        IB_gsrkn,
                        OB_gsrkn,
                        L_gsrk,
                        BRAMBudget-constBram,
                        ConvIPNum,
                        IBrst,
                        OBrst,
                        solutionChoice,
                        ILPlatency
                    )
                if ILPlatency2!=float("inf"):
                    computeLatencyValidate(
                        IB_gsrkn,
                        OB_gsrkn,
                        L_gsrk,
                        BRAMBudget-constBram,
                        ConvIPNum,
                        IBrst2,
                        OBrst2,
                        solutionChoice2,
                        ILPlatency2
                    )
            else:
                print "validation success", ILPlatency2,ILPlatency

            if( ILPlatency !=None and ILPlatency< depositLatency):
                IDEPTH=[];ODEPTH=[];
                IOBRAMtoIODEPTH(IBrst,OBrst,IDEPTH,ODEPTH,ConvIPNum)
                depositLatency=ILPlatency
                depositKxPlist=KxPList
                depositWeight=weightList
                depositsolutionChoice=solutionChoice
                depositIDepthList,depositODepthList=updateDepositArrays(len(IPinfoList),IPindexList,IDEPTH,ODEPTH)
            


            if EndFlgWeight: break;
        if EndFlagKxP: break;
    
    if( not depositsolutionChoice):
        print "Feasible Solution not found in KP iteration";
        return None,None
  

    updateIPinfo_RoundInfo( depositKxPlist,depositWeight,depositIDepthList,depositODepthList,IPinfoList)
    
    return depositsolutionChoice, depositLatency

