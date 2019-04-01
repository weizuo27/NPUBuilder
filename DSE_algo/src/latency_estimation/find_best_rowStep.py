import sys
import math

def AlignSize(x, y):
    ret = x if (x%y == 0) else ((x/y + 1)*y)
    return ret

def loopCount(start, step, end):
    if(start>=end): return 0
    else: 
        return (end-start)/step+1 if((end-start)%step) else (end-start)/step;


def nkpfCount(scalar_conv_args,KER_PROC,XI_WEIGHTBUFF_DEPTH):
    group_flag   = scalar_conv_args[11]
    inputplanes  = scalar_conv_args[16]   
    fsz          = scalar_conv_args[7]
    outDepth     = scalar_conv_args[4]
    inDepth      = scalar_conv_args[5]

    outputplanes = AlignSize(outDepth, KER_PROC)
    con_outDepth = AlignSize(outDepth, KER_PROC)
    con_inDepth = AlignSize(inDepth, 4)
    ip = inputplanes
    op = outputplanes
    if((group_flag) and (outDepth > KER_PROC)):
        op = outputplanes/2
        
    n_kbuff_depth = XI_WEIGHTBUFF_DEPTH-1
    
    max_nkpf = 0
    if KER_PROC==1:
        max_nkpf = n_kbuff_depth/(((fsz*fsz))*(ip/4)*4)
    elif KER_PROC==2:
        max_nkpf = n_kbuff_depth/(((fsz*fsz))*(ip/4)*2)
    else:
        max_nkpf = n_kbuff_depth/(((fsz*fsz))*(ip/4))

    if(max_nkpf>15):
        max_nkpf=15

    rem = 0

    if(KER_PROC==16):
        rem = op%(max_nkpf*16)
    elif (KER_PROC==8):
        rem = op%(max_nkpf*8)
    else:
        rem = op%(max_nkpf*4)

    while(rem!=0):
        max_nkpf-= 1
        
        if(KER_PROC==16):
            rem = op%(max_nkpf*16)
        elif (KER_PROC==8):
            rem = op%(max_nkpf*8)
        else:
            rem = op%(max_nkpf*4) 
    scalar_conv_args[13]=max_nkpf

def straddleFactorCount(scalar_conv_args, inDepth, filter_size, group_flag, XI_WEIGHTBUFF_DEPTH):
    numInpPlanes  = AlignSize(inDepth, 4)
    fsz2 = filter_size*filter_size
    split = 0

    if(inDepth < 4):
        split = 1
    else:
        split = group_flag + 1

    inp_planes = 0
    if((group_flag) and (inDepth > 4)):
        inp_planes = numInpPlanes/2
    else:
        inp_planes = numInpPlanes

    exp1 = False
    exp2 = False
    FEEDING_BUFF_DEPTH = 1024
    strad_fact=1
    n_inbuff_depth = FEEDING_BUFF_DEPTH-1
    # print "inp_planes",inp_planes
    while(not exp1):
        comp_planes = inp_planes/ strad_fact
        exp1 =  (((comp_planes/4)*fsz2) <=  (n_inbuff_depth/2))
        exp2 =  ((comp_planes*fsz2) <= XI_WEIGHTBUFF_DEPTH)
        strad_fact= strad_fact <<1

    straddle_factor = strad_fact>>1 
    compute_planes =  numInpPlanes / (straddle_factor*split)

    scalar_conv_args[16] = compute_planes
    # print "compute_planes",compute_planes
    scalar_conv_args[17] = straddle_factor


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
    
    conv_inp_height  = layerInfo.conv_inp_height   
    conv_inp_width   = layerInfo.conv_inp_width    
    conv_out_height  = layerInfo.conv_out_height   
    conv_out_width   = layerInfo.conv_out_width    
    conv_out_planes  = layerInfo.conv_out_planes   
    conv_inp_planes  = layerInfo.conv_inp_planes   
    conv_stride      = layerInfo.conv_stride       
    conv_filter_height= layerInfo.conv_filter_height
    conv_filter_width= layerInfo.conv_filter_width 
    conv_pad        = layerInfo.conv_pad          
    conv_group      = layerInfo.conv_group        
    rowStep= layerInfo.rowStep
    layerID= layerInfo.layerID
    streamIn= layerInfo.streamIn
    streamOut= layerInfo.streamOut
    oneTime= layerInfo.oneTime

    XI_KER_PROC=IPinfo.XI_KER_PROC
    XI_PIX_PROC=IPinfo.XI_PIX_PROC
    XI_WEIGHTBUFF_DEPTH=IPinfo.XI_WEIGHTBUFF_DEPTH
    int6bit=IPinfo.int6bit
    
    scalar_conv_args = [0] * 128
    scalar_conv_args[0]  = conv_inp_height
    scalar_conv_args[1]  = conv_inp_width
    scalar_conv_args[2]  = conv_out_height
    scalar_conv_args[3]  = conv_out_width
    scalar_conv_args[4]  = conv_out_planes
    scalar_conv_args[5]  = conv_inp_planes
    scalar_conv_args[6]  = conv_stride
    scalar_conv_args[7]  = conv_filter_height
    scalar_conv_args[8]  = conv_filter_width
    scalar_conv_args[9]  = conv_pad         
    scalar_conv_args[11] = conv_group
    scalar_conv_args[15]=rowStep
    
    straddleFactorCount(scalar_conv_args,conv_inp_planes,conv_filter_height,conv_group, XI_WEIGHTBUFF_DEPTH)
    scalar_conv_args[61] = AlignSize(scalar_conv_args[16], 4)

    scalar_conv_args[77] = conv_filter_height * conv_filter_width * (scalar_conv_args[61]/4)
    compute_loop_count=scalar_conv_args[77]

    
    feeding_buff_plane_loop_bound=scalar_conv_args[61]/4;
    feeding_buff_row_loop_bound=conv_filter_height;

    LatLoadInputBuff32Pix_fn=feeding_buff_plane_loop_bound*feeding_buff_row_loop_bound*( conv_filter_height+conv_stride*(XI_PIX_PROC/2-1) )+6;

    if(int6bit): LatLoadInputBuff32Pix_fn=LatLoadInputBuff32Pix_fn*2;
    #print "LatLoadInputBuff32Pix_fn:"+str(LatLoadInputBuff32Pix_fn);


    LatCompute16Ker_fy=(compute_loop_count+1)+XI_PIX_PROC/2+20;

    # print "LatCompute16Ker_fy:"+str(LatCompute16Ker_fy);


    nkpfCount(scalar_conv_args,XI_KER_PROC,XI_WEIGHTBUFF_DEPTH) 

    nkpf= scalar_conv_args[13]
    # print "nkpf:"+str(nkpf);


    latOsggBuff_fx=XI_PIX_PROC+8
    #print "latOsggBuff_fx:"+str(latOsggBuff_fx);


    latProcResult_fe=latOsggBuff_fx+LatCompute16Ker_fy+(nkpf-1)*max(latOsggBuff_fx,LatCompute16Ker_fy)+10
    # print "latProcResult_fe:"+str(latProcResult_fe);

    scalar_conv_args[92] =  scalar_conv_args[13] * conv_filter_height * conv_filter_width * (scalar_conv_args[61]/4)
    scalar_conv_args[62] = AlignSize(scalar_conv_args[4], 16) /(1+conv_group)

   
    AXILATENCY = 1
    # if AXILATENCY == None:
    #     AXILATENCY = 1
    if oneTime:
        latLoadWeight=latLoadKernelsEn_fz = 1
    else:
        latLoadWeight=latLoadKernelsEn_fz= (scalar_conv_args[92]/16*18)*AXILATENCY+10
    # print "latLoadKernelsEn_fz:"+str(latLoadKernelsEn_fz), AXILATENCY, "oneTime?", oneTime

    compute_planes=scalar_conv_args[61]
    latLoadFeedingBuff_fl = 0
    tmp = (XI_PIX_PROC/16+1) if (XI_PIX_PROC%16) else  (XI_PIX_PROC/16)
    if(layerID!=0):
        latLoadFeedingBuff_fl=compute_planes/64*( conv_filter_height*conv_filter_width*16*tmp+13)+20;
    else:
        latLoadFeedingBuff_fl=LatLoadInputBuff32Pix_fn+10
    # print "latLoadFeedingBuff_fl:"+str(latLoadFeedingBuff_fl)

    # *computes number of XI_PIX_PROC in the output rows
    pix_per_ker= XI_PIX_PROC if (int6bit) else XI_PIX_PROC/2
    

    pcLoopcnt= AlignSize( conv_out_width*rowStep,  pix_per_ker)/pix_per_ker

    

    latProcWeight=latLoop=pcLoopcnt*( max(latProcResult_fe,latLoadFeedingBuff_fl)+20)



    

    latCompNumber=ProcInputLoopCount=scalar_conv_args[62]/XI_KER_PROC/nkpf*scalar_conv_args[17]
    # print "ProcInputLoopCount"+str(ProcInputLoopCount)

    #print "straddle:"+str(scalar_conv_args[17]);
    # print "latLoop", latLoop, "latLoadFeedingBuff_fl", latLoadFeedingBuff_fl, "latLoadKernelsEn_fz", latLoadKernelsEn_fz
    latProcInputBuff=ProcInputLoopCount*(max(latLoop,latLoadKernelsEn_fz)+4)+max(latLoadFeedingBuff_fl,latLoadKernelsEn_fz);
    # print "latProcInputBuff:"+str(latProcInputBuff);

    layerx_loop_cnt_fg0=conv_inp_width*conv_filter_height;

    if(layerID==0):
        latReadLineBuffer=layerx_loop_cnt_fg0*2+20;
    else:
        latReadLineBuffer=rowStep*conv_stride*(scalar_conv_args[61]/16)*(40+conv_inp_width)+10
    # print "latReadLineBuffer:"+str(latReadLineBuffer)

    if(streamOut==0):
        preOverhead=(conv_filter_height+rowStep-1-conv_pad)*conv_stride*(scalar_conv_args[61]/16)*(40+conv_inp_width)+10
        latReadInputData= rowStep*conv_stride*(scalar_conv_args[61]/16)*conv_inp_width
    else:
        preOverhead=0
        latReadInputData=0
    FirstEndRows=conv_filter_height+rowStep-1-conv_pad-1
    latStoreOStagingBuff_fj = rowStep*(conv_out_width+50)*(scalar_conv_args[62]/16)+10;
    # print "latStoreOStagingBuff_fj:"+str(latStoreOStagingBuff_fj)
    if(streamIn==0):
        postOverhead=rowStep*(conv_out_width+50)*(scalar_conv_args[62]/16)+10;
        latWritOutputData= rowStep*conv_out_width*(scalar_conv_args[62]/16);
    else:
        postOverhead=0
        latWritOutputData=0
    return  [latProcWeight, latLoadWeight, latCompNumber,  preOverhead,postOverhead, latReadInputData, latWritOutputData,FirstEndRows,conv_stride]



def computeLatencyEle(
    layerInfo,
    IPinfo
):
    conv_out_height  = layerInfo.conv_out_height   
    conv_out_width   = layerInfo.conv_out_width    
    conv_out_planes  = layerInfo.conv_out_planes  
    rowStep= layerInfo.rowStep
    streamIn= layerInfo.streamIn
    streamOut= layerInfo.streamOut
    latProcWeight= 68+(conv_out_width+4);
    if( not streamIn or not streamOut ):
        latLoadWeight= (conv_out_width+4);
    else:
        latLoadWeight= 0;

    latCompNumber=conv_out_planes/16;
    if( not streamIn ):
        preOverhead= (conv_out_width+4);
    else:
        preOverhead=0

    if( not streamOut):
        postOverhead=(conv_out_width+4);
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
    conv_stride      = layerInfo.conv_stride      
    conv_filter_height= layerInfo.conv_filter_height
    conv_filter_width= layerInfo.conv_filter_width

    conv_inp_height  = layerInfo.conv_inp_height   
    conv_inp_width   = layerInfo.conv_inp_width   
    conv_pad        = layerInfo.conv_pad 

    conv_out_height  = layerInfo.conv_out_height   
    conv_out_width   = layerInfo.conv_out_width    
    conv_out_planes  = layerInfo.conv_out_planes  

    rowStep= layerInfo.rowStep
    streamIn= layerInfo.streamIn
    streamOut= layerInfo.streamOut


    latProcWeight=conv_out_height*conv_out_planes/16*conv_filter_height*conv_filter_width
    latLoadWeight=conv_inp_width*conv_stride*conv_out_planes/16
    latCompNumber=rowStep


    FirstEndRows=conv_filter_height+(rowStep-1)*conv_stride-conv_pad-1


    if( not streamIn ):
        preOverhead= FirstEndRows*conv_inp_width*conv_out_planes/16
    else:
        preOverhead=0


    if( not streamOut):
        postOverhead=rowStep*conv_out_width*conv_out_planes/16
    else:
        postOverhead=0


    latReadInputData=0
    latWritOutputData=0
    return  [latProcWeight, latLoadWeight, latCompNumber,  preOverhead,postOverhead, latReadInputData, latWritOutputData,FirstEndRows,1]

class convInfo_t():
    streamIn = None
    streamOut = None
    conv_inp_height   =None
    conv_inp_width   =None
    conv_out_height   =None
    conv_out_width   =None
    conv_out_planes  =None
    conv_inp_planes   =None
    conv_stride       =None
    conv_filter_height=None
    conv_filter_width =None
    conv_pad          =None
    conv_group        =None
    maxRowStep =None
    rowStep=None
    oneTime = None
    layerID = None
    def __init__(self):
        return;
    def info(self,
    streamIn,
    streamOut,
    conv_inp_height  ,
    conv_inp_width  ,
    conv_out_height  ,
    conv_out_width  ,
    conv_out_planes ,
    conv_inp_planes  ,
    conv_stride      ,
    conv_filter_height,
    conv_filter_width,
    conv_pad         ,
    conv_group       ,
    rowStep,
    oneTime,
    layerID
    ):
        self.streamIn=streamIn
        self.streamOut=streamOut
        self.conv_inp_height  =conv_inp_height  
        self.conv_inp_width  =conv_inp_width  
        self.conv_out_height  =conv_out_height  
        self.conv_out_width  =conv_out_width  
        self.conv_out_planes =conv_out_planes 
        self.conv_inp_planes  =conv_inp_planes  
        self.conv_stride      =conv_stride      
        self.conv_filter_height=conv_filter_height
        self.conv_filter_width=conv_filter_width
        self.conv_pad         =conv_pad         
        self.conv_group       =conv_group       
        self.rowStep=rowStep
        self.oneTime=oneTime
        self.layerID=layerID


class IPinfo_t():
    IPtype=None
    XI_KER_PROC=None
    XI_PIX_PROC=None
    XI_WEIGHTBUFF_DEPTH=None
    int6bit=None
    def __init__( self):
        self.IPtype=None
        self.XI_KER_PROC=None
        self.XI_PIX_PROC=None
        self.XI_WEIGHTBUFF_DEPTH=None
        self.int6bit=None
        return
    def info( self, IPtype,XI_KER_PROC,XI_PIX_PROC, XI_WEIGHTBUFF_DEPTH,int6bit):
        self.IPtype=IPtype
        self.XI_KER_PROC=XI_KER_PROC
        self.XI_PIX_PROC=XI_PIX_PROC
        self.XI_WEIGHTBUFF_DEPTH=XI_WEIGHTBUFF_DEPTH
        self.int6bit=int6bit

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
    return timeStamp

def findBestRowStep(finName, foutName):
    f = open(finName, 'r');
    f2 = open(foutName,"w")
    for line in f:
        line = line.replace("\ ", "")
        line = line.replace("\n", "")
        paramList = line.split(",")
        paramIter=iter(paramList);
        roundIdx=int(paramIter.next() )
        isPipeline=int(paramIter.next())
        paramItem=paramIter.next();

        layerInfoList=[]
        IPinfoList=[]
        while( paramItem!="END" ):
            if(paramItem=="Pooling"):
                x=convInfo_t();
                memin=int(paramIter.next())
                memout=int(paramIter.next())
                x.streamIn=int(memin==0)
                x.streamOut=int(memout==0)
                x.conv_inp_height=int(paramIter.next())
                x.conv_inp_width=int(paramIter.next())
                x.conv_out_height=int(paramIter.next())
                x.conv_out_width=int(paramIter.next())
                x.conv_out_planes=int(paramIter.next())
                x.conv_inp_planes=int(paramIter.next())
                x.conv_stride=int(paramIter.next())
                x.conv_filter_height=int(paramIter.next())
                x.conv_filter_width=int(paramIter.next())
                x.conv_pad=int(paramIter.next())
                x.conv_group=int(paramIter.next())
                x.maxRowStep=int(paramIter.next())
                x.oneTime=int(paramIter.next())
                x.layerID=int(paramIter.next())
                y=IPinfo_t();
                y.IPtype="Pooling"
                layerInfoList.append(x)
                IPinfoList.append(y)
            elif( paramItem=="Convolution" ):
                x=convInfo_t()
                memin=int(paramIter.next())
                memout=int(paramIter.next())
                x.streamIn=int(memin==0)
                x.streamOut=int(memout==0)
                x.conv_inp_height=int(paramIter.next())
                x.conv_inp_width=int(paramIter.next())
                x.conv_out_height=int(paramIter.next())
                x.conv_out_width=int(paramIter.next())
                x.conv_out_planes=int(paramIter.next())
                x.conv_inp_planes=int(paramIter.next())
                x.conv_stride=int(paramIter.next())
                x.conv_filter_height=int(paramIter.next())
                x.conv_filter_width=int(paramIter.next())
                x.conv_pad=int(paramIter.next())
                x.conv_group=int(paramIter.next())
                x.maxRowStep=int(paramIter.next())
                x.oneTime=int(paramIter.next())
                x.layerID=int(paramIter.next())
                y=IPinfo_t()
                y.IPtype="Convolution"
                y.XI_KER_PROC=int(paramIter.next())
                y.XI_PIX_PROC=int(paramIter.next())
                y.XI_WEIGHTBUFF_DEPTH=int(paramIter.next())
                y.int6bit=int(paramIter.next())
                layerInfoList.append(x)
                IPinfoList.append(y)
            elif(paramItem=="ElementWise"):
                x=convInfo_t()
                memin=int(paramIter.next())
                memout=int(paramIter.next())
                x.streamIn=int(memin==0)
                x.streamOut=int(memout==0)
                x.conv_out_height=int(paramIter.next())
                x.conv_out_width=int(paramIter.next())
                x.conv_out_planes=int(paramIter.next())
                x.maxRowStep=int(paramIter.next())
                x.layerID=int(paramIter.next())
                y=IPinfo_t()
                y.IPtype="ElementWise"
                layerInfoList.append(x)
                IPinfoList.append(y)
            paramItem=paramIter.next();

        if(isPipeline==0):
            for i in layerInfoList:
                f2.write(str(i.layerID)+","+str(i.maxRowStep)+"\n" );

        else:
            rowStep=1;
            rowStepArgMin=1;
            cyclesMin=sys.maxint
            while(1):
                layerLatencyInfoList=[]
                rowStepFeasibleFlag=True
                for i in range( len(layerInfoList) ):
                    if(rowStep>layerInfoList[i].maxRowStep):
                        rowStepFeasibleFlag=False
                        break;
                    x=layerLatencyInfo_t(layerInfoList[i],IPinfoList[i],rowStep);
                    layerLatencyInfoList.append(x)
                if( rowStepFeasibleFlag == False ):
                    rowStep=rowStep-1;
                    break
                cycles=computeLatencyPipe(layerLatencyInfoList)

                #print "Test result", rowStep, cycles*4/1000000
                if(cycles<cyclesMin):
                    cyclesMin=cycles;
                    rowStepArgMin=rowStep;
                rowStep=rowStep+1;
            for i in layerInfoList:
                f2.write(str(i.layerID)+", "+str(rowStepArgMin)+"\n" );

    f.close()
    f2.close()
                    
                


        
            







            






    
