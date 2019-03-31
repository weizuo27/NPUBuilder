
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
    outDepth     = scalar_conv_args[16]
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
    #print "inp_planes",inp_planes
    while(not exp1):
        comp_planes = inp_planes/ strad_fact
        exp1 =  (((comp_planes/4)*fsz2) <=  (n_inbuff_depth/2))
        exp2 =  ((comp_planes*fsz2) <= XI_WEIGHTBUFF_DEPTH)
        strad_fact= strad_fact <<1

    straddle_factor = strad_fact>>1 
    compute_planes =  numInpPlanes / (straddle_factor*split)

    scalar_conv_args[16] = compute_planes
    #print "compute_planes",compute_planes
    scalar_conv_args[17] = straddle_factor


def computeLatency (
    conv_inp_height  , 
    conv_inp_width   , 
    conv_out_height  , 
    conv_out_width   , 
    conv_out_planes  , 
    conv_inp_planes  , 
    conv_stride      , 
    conv_filter_height,
    conv_filter_width, 
    conv_pad         , 
    conv_group       , 
    rowStep,
    XI_KER_PROC,
    XI_PIX_PROC,
    XI_WEIGHTBUFF_DEPTH,
    int6bit,
    layerID, 
    AXILATENCY, 
    oneTime,
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
    ##print "LatLoadInputBuff32Pix_fn:"+str(LatLoadInputBuff32Pix_fn);


    LatCompute16Ker_fy=(compute_loop_count+1)+XI_PIX_PROC/2+20;

    #print "LatCompute16Ker_fy:"+str(LatCompute16Ker_fy);


    nkpfCount(scalar_conv_args,XI_KER_PROC,XI_WEIGHTBUFF_DEPTH) 

    nkpf= scalar_conv_args[13]
    ##print "nkpf:"+str(nkpf);


    latOsggBuff_fx=XI_PIX_PROC+8
    ##print "latOsggBuff_fx:"+str(latOsggBuff_fx);


    latProcResult_fe=latOsggBuff_fx+LatCompute16Ker_fy+(nkpf-1)*max(latOsggBuff_fx,LatCompute16Ker_fy)+10
    #print "latProcResult_fe:"+str(latProcResult_fe);

    scalar_conv_args[92] =  scalar_conv_args[13] * conv_filter_height * conv_filter_width * (scalar_conv_args[61]/4)
    scalar_conv_args[62] = AlignSize(scalar_conv_args[4], 16) /(1+conv_group)

   
#    AXILATENCY = 1
    if AXILATENCY == None:
        AXILATENCY = 1
    if oneTime:
        latLoadKernelsEn_fz = 0
    else:
        latLoadKernelsEn_fz=scalar_conv_args[92]*AXILATENCY+10
    #print "latLoadKernelsEn_fz:"+str(latLoadKernelsEn_fz), AXILATENCY, "oneTime?", oneTime

    compute_planes=scalar_conv_args[61]
    latLoadFeedingBuff_fl = 0
    tmp = (XI_PIX_PROC/16+1) if (XI_PIX_PROC%16) else  (XI_PIX_PROC/16)
    if(layerID!=0):
        latLoadFeedingBuff_fl=compute_planes/64*( conv_filter_height*conv_filter_width*16*tmp+13)+20;
    else:
        latLoadFeedingBuff_fl=LatLoadInputBuff32Pix_fn+10
    #print "latLoadFeedingBuff_fl:"+str(latLoadFeedingBuff_fl)

    # *computes number of XI_PIX_PROC in the output rows
    pix_per_ker= XI_PIX_PROC if (int6bit) else XI_PIX_PROC/2
    

    pcLoopcnt= AlignSize( conv_out_width*rowStep,  pix_per_ker)/pix_per_ker
    latLoop=pcLoopcnt*( max(latProcResult_fe,latLoadFeedingBuff_fl)+20)


    ProcInputLoopCount=scalar_conv_args[62]/XI_KER_PROC/nkpf*scalar_conv_args[17]
    #print "ProcInputLoopCount"+str(ProcInputLoopCount)
    ##print "straddle:"+str(scalar_conv_args[17]);
#    #print "latLoop", latLoop, "latLoadFeedingBuff_fl", latLoadFeedingBuff_fl, "latLoadKernelsEn_fz", latLoadKernelsEn_fz
    latProcInputBuff=ProcInputLoopCount*(max(latLoop,latLoadKernelsEn_fz)+4)+max(latLoadFeedingBuff_fl,latLoadKernelsEn_fz);
    #print "latProcInputBuff:"+str(latProcInputBuff);

    layerx_loop_cnt_fg0=conv_inp_width*conv_filter_height;

    if(layerID==0):
        latReadLineBuffer=layerx_loop_cnt_fg0*2+20;
    else:
        latReadLineBuffer=rowStep*conv_stride*(scalar_conv_args[61]/16)*(9+conv_inp_width*2)+5
    ##print "latReadLineBuffer:"+str(latReadLineBuffer)

    latOutputWrite_fk = rowStep*conv_out_width+10;

    ##print "latOutputWrite_fk:"+str(latOutputWrite_fk)
    # latency of writing back one row
    latStoreOStagingBuff_fj = (latOutputWrite_fk+10)*(scalar_conv_args[62]/16)+10;
    ##print "latStoreOStagingBuff_fj:"+str(latStoreOStagingBuff_fj)


    procistg_tripcount=conv_out_height/rowStep;
    # whole image latency
    latProcIstagingBuff=latStoreOStagingBuff_fj+latReadLineBuffer+latProcInputBuff+procistg_tripcount*(max(latReadLineBuffer,max(latOutputWrite_fk,latReadLineBuffer)))
    #print "latProcIstagingBuff:"+str(latProcIstagingBuff)


    #* latency of loading input for computation of one row: latReadLineBuffer
    #* latency of writing output of  one row: latStoreOStagingBuff_fj
    #* latency of computing one row: latProcInputBuff_fd
    #* return the maximum of above three as the one row latency. usually it is latProcInputBuff_fd


    #print "return value", max(latReadLineBuffer, latStoreOStagingBuff_fj, latProcInputBuff)
   


    return max(latReadLineBuffer, latStoreOStagingBuff_fj, latProcInputBuff)
    
conv_inp_height = 112
conv_inp_width = 112
conv_out_height =112
conv_out_width = 112
conv_out_planes =  128
conv_inp_planes = 128
conv_stride = 1 
conv_filter_height = 3
conv_filter_width = 3
conv_pad = 1
conv_group = 0
rowStep = 2
XI_KER_PROC = 16
XI_PIX_PROC = 32
XI_WEIGHTBUFF_DEPTH = 1024

#conv_inp_height = 16 
#conv_inp_width = 16
#conv_out_height = 14
#conv_out_width = 14
#conv_out_planes =  1
#conv_inp_planes = 1
#conv_stride = 1 
#conv_filter_height = 3
#conv_filter_width = 3
#conv_pad = 0
#conv_group = 1
#rowStep = 1
#XI_KER_PROC = 8
#XI_PIX_PROC = 8
#XI_WEIGHTBUFF_DEPTH = 512

#conv_inp_height = 18 
#conv_inp_width = 18
#conv_out_height = 16
#conv_out_width = 16
#conv_out_planes =  1
#conv_inp_planes = 1
#conv_stride = 1 
#conv_filter_height = 3
#conv_filter_width = 3
#conv_pad = 0
#conv_group = 1
#rowStep = 1
#XI_KER_PROC = 8
#XI_PIX_PROC = 8
#XI_WEIGHTBUFF_DEPTH = 512
#

# conv_inp_height = 13
# conv_inp_width = 13
# conv_out_height = 13
# conv_out_width = 26
# conv_out_planes =  384
# conv_inp_planes = 256
# conv_stride = 1 
# conv_filter_height = 3
# conv_filter_width = 3
# conv_pad = 1
# conv_group = 1
# rowStep = 1
# XI_KER_PROC = 16
# XI_PIX_PROC = 16
# XI_WEIGHTBUFF_DEPTH = 1024

#conv_inp_height = 13
#conv_inp_width = 13
#conv_out_height = 13
#conv_out_width = 26
#conv_out_planes =  384
#conv_inp_planes = 256
#conv_stride = 1 
#conv_filter_height = 3
#conv_filter_width = 3
#conv_pad = 1
#conv_group = 1
#rowStep = 1
#XI_KER_PROC = 16
#XI_PIX_PROC = 32
#XI_WEIGHTBUFF_DEPTH = 1024

#aa = computeLatency(
#    conv_inp_height  , 
#    conv_inp_width   , 
#    conv_out_height  , 
#    conv_out_width   , 
#    conv_out_planes  , 
#    conv_inp_planes  , 
#    conv_stride      , 
#    conv_filter_height,
#    conv_filter_width, 
#    conv_pad         , 
#    conv_group       , 
#    rowStep,
#    XI_KER_PROC,
#    XI_PIX_PROC,
#    XI_WEIGHTBUFF_DEPTH,
#    1,
#    1,
#    1,
#    False
#    )

##print aa, aa*conv_out_height/rowStep
#
#
def computeLatency_pooling(ow, fw, fh, odepth, pipelined):
    return ow*fw*fh *odepth/16+300

def computeLatency_eltwise(ow, odepth):
    return ow*odepth/16


    # conv_inp_height  , 
    # conv_inp_width   , 
    # conv_out_height  , 
    # conv_out_width   , 
    # conv_out_planes  , 
    # conv_inp_planes  , 
    # conv_stride      , 
    # conv_filter_height,
    # conv_filter_width, 
    # conv_pad         , 
    # conv_group       , 
    # rowStep,
    # XI_KER_PROC,
    # XI_PIX_PROC,
    # XI_WEIGHTBUFF_DEPTH,
    # int6bit,
    # layerID, 
    # AXILATENCY, 
    # oneTime,


def computeLatency_conv_g(
    conv_inp_height  , 
    conv_inp_width   , 
    conv_out_height  , 
    conv_out_width   , 
    conv_out_planes  , 
    conv_inp_planes  , 
    conv_stride      , 
    conv_filter_height,
    conv_filter_width, 
    conv_pad         , 
    conv_group       , 
    rowStep,
    XI_KER_PROC,
    XI_PIX_PROC,
    XI_WEIGHTBUFF_DEPTH,
    int6bit,
    layerID, 
    AXILATENCY, 
    oneTime,
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

    LatLoadInputBuff32Pix_fn=feeding_buff_plane_loop_bound*feeding_buff_row_loop_bound*(conv_filter_height+conv_stride*(XI_PIX_PROC/2-1) )+6;

    if(int6bit): LatLoadInputBuff32Pix_fn=LatLoadInputBuff32Pix_fn*2;
    ##print "LatLoadInputBuff32Pix_fn:"+str(LatLoadInputBuff32Pix_fn);


    LatCompute16Ker_fy=(compute_loop_count+1)+XI_PIX_PROC/2+20;

    #print "LatCompute16Ker_fy:"+str(LatCompute16Ker_fy);


    nkpfCount(scalar_conv_args,XI_KER_PROC,XI_WEIGHTBUFF_DEPTH) 

    nkpf= scalar_conv_args[13]
    ##print "nkpf:"+str(nkpf);


    latOsggBuff_fx=XI_PIX_PROC+8
    ##print "latOsggBuff_fx:"+str(latOsggBuff_fx);


    latProcResult_fe=latOsggBuff_fx+LatCompute16Ker_fy+(nkpf-1)*max(latOsggBuff_fx,LatCompute16Ker_fy)+10
    #print "latProcResult_fe:"+str(latProcResult_fe);

    scalar_conv_args[92] =  scalar_conv_args[13] * conv_filter_height * conv_filter_width * (scalar_conv_args[61]/4)
    scalar_conv_args[62] = AlignSize(scalar_conv_args[4], 16) /(1+conv_group)

   
#    AXILATENCY = 1
    if AXILATENCY == None:
        AXILATENCY = 1
    if oneTime:
        latLoadKernelsEn_fz = 0
    else:
        latLoadKernelsEn_fz=scalar_conv_args[92]*AXILATENCY+10
    #print "latLoadKernelsEn_fz:"+str(latLoadKernelsEn_fz), AXILATENCY, "oneTime?", oneTime

    compute_planes=scalar_conv_args[61]
    latLoadFeedingBuff_fl = 0
    tmp = (XI_PIX_PROC/16+1) if (XI_PIX_PROC%16) else  (XI_PIX_PROC/16)
    if(layerID!=0):
        latLoadFeedingBuff_fl=compute_planes/64*conv_filter_height*conv_filter_width*16*tmp+20;
    else:
        latLoadFeedingBuff_fl=LatLoadInputBuff32Pix_fn+10
    #print "latLoadFeedingBuff_fl:"+str(latLoadFeedingBuff_fl)

    # *computes number of XI_PIX_PROC in the output rows
    pix_per_ker= XI_PIX_PROC if (int6bit) else XI_PIX_PROC/2
    

    pcLoopcnt= AlignSize( conv_out_width*rowStep,  pix_per_ker)/pix_per_ker
    latLoop=pcLoopcnt*( max(latProcResult_fe,latLoadFeedingBuff_fl)+20)


    ProcInputLoopCount=scalar_conv_args[62]/XI_KER_PROC/nkpf*scalar_conv_args[17]
    ##print "ProcInputLoopCount"+str(ProcInputLoopCount)
    ##print "straddle:"+str(scalar_conv_args[17]);
#    #print "latLoop", latLoop, "latLoadFeedingBuff_fl", latLoadFeedingBuff_fl, "latLoadKernelsEn_fz", latLoadKernelsEn_fz
    latProcInputBuff=ProcInputLoopCount*(max(latLoop,latLoadKernelsEn_fz)+4)+max(latLoadFeedingBuff_fl,latLoadKernelsEn_fz);
    # #print "latProcInputBuff:"+str(latProcInputBuff);

    layerx_loop_cnt_fg0=conv_inp_width*conv_filter_height;

    if(layerID==0):
        latReadLineBuffer=layerx_loop_cnt_fg0*2+20;
    else:
        latReadLineBuffer=rowStep*conv_stride*(scalar_conv_args[61]/16)*(9+conv_inp_width*2)+5
    ##print "latReadLineBuffer:"+str(latReadLineBuffer)

    latOutputWrite_fk = rowStep*conv_out_width+10;

    ##print "latOutputWrite_fk:"+str(latOutputWrite_fk)
    # latency of writing back one row
    latStoreOStagingBuff_fj = (latOutputWrite_fk+10)*(scalar_conv_args[62]/16)+10;
    #print "latStoreOStagingBuff_fj:"+str(latStoreOStagingBuff_fj)


    procistg_tripcount=conv_out_height-1;
    # whole image latency
    latProcIstagingBuff=latStoreOStagingBuff_fj+latReadLineBuffer+latProcInputBuff+procistg_tripcount*(max(latReadLineBuffer,max(latOutputWrite_fk,latReadLineBuffer)))
    #print "latProcIstagingBuff:"+str(latProcIstagingBuff)


    #* latency of loading input for computation of one row: latReadLineBuffer
    #* latency of writing output of  one row: latStoreOStagingBuff_fj
    #* latency of computing one row: latProcInputBuff_fd
    #* return the maximum of above three as the one row latency. usually it is latProcInputBuff_fd


    #print "return value", max(latReadLineBuffer, latStoreOStagingBuff_fj, latProcInputBuff)
   
    latReadLineBuffer=latReadLineBuffer*2;
    latStoreOStagingBuff_fj=latStoreOStagingBuff_fj*2;
    latProcInputBuff=latProcInputBuff*2;

    return max(latReadLineBuffer, latStoreOStagingBuff_fj, latProcInputBuff)

# computeLatency(7,7,7,7,2048,512,1,1,1,1,0,4,16,32,2048,True,14, None, 0)



conv_inp_height = 7
conv_inp_width = 7
conv_out_height = 7
conv_out_width = 7
conv_out_planes =  512
conv_inp_planes = 2048
conv_stride = 1 
conv_filter_height = 1
conv_filter_width = 1
conv_pad = 1
conv_group = 0
rowStep = 2
XI_KER_PROC = 16
XI_PIX_PROC = 32
XI_WEIGHTBUFF_DEPTH = 1024

computeLatency (
    conv_inp_height  , 
    conv_inp_width   , 
    conv_out_height  , 
    conv_out_width   , 
    conv_out_planes  , 
    conv_inp_planes  , 
    conv_stride      , 
    conv_filter_height,
    conv_filter_width, 
    conv_pad         , 
    conv_group       , 
    rowStep,
    16,
    32,
    1024,
    1,
    6, 
    1, 
    0)
