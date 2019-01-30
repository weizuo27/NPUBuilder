
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
        
    n_kbuff_depth = XI_WEIGHTBUFF_DEPTH
    
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
    n_inbuff_depth = FEEDING_BUFF_DEPTH

    while(not exp1):
        comp_planes = inp_planes/ strad_fact
        exp1 =  (((comp_planes/4)*fsz2) <=  (n_inbuff_depth/2))
        exp2 =  ((comp_planes*fsz2) <= XI_WEIGHTBUFF_DEPTH)
        strad_fact= strad_fact <<1

    straddle_factor = strad_fact>>1 
    compute_planes =  numInpPlanes / (straddle_factor*split)

    scalar_conv_args[16] = compute_planes
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
    layerID
):

    ChaiDnn = True
    if ChaiDnn:
        rowStep = 4
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

    straddleFactorCount(scalar_conv_args,conv_inp_planes,conv_filter_height,conv_group, XI_WEIGHTBUFF_DEPTH)
    scalar_conv_args[61] = AlignSize(scalar_conv_args[16], 4)

    scalar_conv_args[77] = conv_filter_height * conv_filter_width * (scalar_conv_args[61]/4)
    compute_loop_count=scalar_conv_args[77]

    
    feeding_buff_plane_loop_bound=scalar_conv_args[61]/4;
    feeding_buff_row_loop_bound=conv_filter_height;

    LatLoadInputBuff32Pix_fn=feeding_buff_plane_loop_bound*feeding_buff_row_loop_bound*conv_out_width+6;

    if(int6bit): LatLoadInputBuff32Pix_fn=LatLoadInputBuff32Pix_fn*2;
    #print "LatLoadInputBuff32Pix_fn:"+str(LatLoadInputBuff32Pix_fn);


    LatCompute16Ker_fy=(compute_loop_count+1)+XI_PIX_PROC/2+20;

    #print "LatCompute16Ker_fy:"+str(LatCompute16Ker_fy);


    nkpfCount(scalar_conv_args,XI_KER_PROC,XI_WEIGHTBUFF_DEPTH) 

    nkpf= scalar_conv_args[13]
    #print "nkpf:"+str(nkpf);

    latOsggBuff_fx=XI_PIX_PROC+8
    #print "latOsggBuff_fx:"+str(latOsggBuff_fx);


    latProcResult_fe=latOsggBuff_fx+LatCompute16Ker_fy+(nkpf-1)*max(latOsggBuff_fx,LatCompute16Ker_fy)+10
    #print "latProcResult_fe:"+str(latProcResult_fe);

    scalar_conv_args[92] =  scalar_conv_args[13] * conv_filter_height * conv_filter_width * (scalar_conv_args[61]/4)
    scalar_conv_args[62] = AlignSize(scalar_conv_args[4], 16) 


    AXILATENCY = 1
    latLoadKernelsEn_fz=scalar_conv_args[92]*AXILATENCY+10
    #print "latLoadKernelsEn_fz:"+str(latLoadKernelsEn_fz);

    ker_loop_cnt=scalar_conv_args[62]

    ker_loop_tripcount=  loopCount(XI_KER_PROC*nkpf,XI_KER_PROC*nkpf,ker_loop_cnt)
    #print "ker_loop_tripcount:"+str(ker_loop_tripcount);
    # ker_loop_cnt/(XI_KER_PROC*nkpf)+1 if ker_loop_cnt%(XI_KER_PROC*nkpf) else ker_loop_cnt%(XI_KER_PROC*nkpf)

    latProcWeightBuff_fd=latLoadKernelsEn_fz+latProcResult_fe+ker_loop_tripcount*max(latLoadKernelsEn_fz,latProcResult_fe)
    #print "latProcWeightBuff_fd:"+str(latProcWeightBuff_fd);

    # The numnber of bits of weights needed to load to process one rowStep
    requestNumber=scalar_conv_args[92] * ker_loop_tripcount * 128 * 4

    scalar_conv_args[15]=rowStep

    total_pixel_fc0 = scalar_conv_args[15]*conv_out_width;
    pix_per_kp = XI_PIX_PROC
    pcmf_off1_fc0 = (total_pixel_fc0/pix_per_kp) +1;
    pcmf_m1=(scalar_conv_args[17]-1);
    pcmf_off_fc0 = pcmf_off1_fc0*pcmf_m1
    pc_loop_mul_fc0=pix_per_kp * pcmf_off_fc0;
    pc_loop_bound = total_pixel_fc0 + pc_loop_mul_fc0;


    if((scalar_conv_args[15] * conv_out_width) < pix_per_kp):
        pc_loop_bound = scalar_conv_args[17]*pix_per_kp    
    #print "pc_loop_bound:"+str(pc_loop_bound)
    pc_tripcount= loopCount(XI_PIX_PROC,XI_PIX_PROC,pc_loop_bound)
    #print "pc_tripcount:"+str(pc_tripcount)
    # pc_loop_bound/XI_PIX_PROC+1 if (pc_loop_bound%XI_PIX_PROC) else (pc_loop_bound)/XI_PIX_PROC

    compute_planes=scalar_conv_args[61]
    latLoadFeedingBuff_fl = 0
    tmp = (XI_PIX_PROC/16+1) if (XI_PIX_PROC%16) else  (XI_PIX_PROC/16)
    if(layerID!=0):
        latLoadFeedingBuff_fl=compute_planes/64*conv_filter_height*conv_filter_width*16*2*tmp;
    else:
        latLoadFeedingBuff_fl=LatLoadInputBuff32Pix_fn+10

    latProcInputBuff_fd=latLoadFeedingBuff_fl+latProcWeightBuff_fd+ pc_tripcount*max(latLoadFeedingBuff_fl,latProcWeightBuff_fd)


  


    #print "latProcInputBuff_fd:"+str(latProcInputBuff_fd)

    layerx_loop_cnt_fg0=conv_inp_width*conv_filter_height;

    if(layerID==0):
        latReadLineBuffer=layerx_loop_cnt_fg0*2+20;
    else:
        latReadLineBuffer=rowStep*conv_stride*(scalar_conv_args[61]/16)*(9+conv_inp_width*2)+5
    #print "latReadLineBuffer:"+str(latReadLineBuffer)

    latOutputWrite_fk = rowStep*conv_out_width+10;

    #print "latOutputWrite_fk:"+str(latOutputWrite_fk)
    # latency of writing back one row
    latStoreOStagingBuff_fj = (latOutputWrite_fk+10)*(scalar_conv_args[62]/16)+10;
    # print "latStoreOStagingBuff_fj:"+str(latStoreOStagingBuff_fj)


    procistg_tripcount=conv_out_height-1;
    # whole image latency
    latProcIstagingBuff=latStoreOStagingBuff_fj+latReadLineBuffer+latProcInputBuff_fd+procistg_tripcount*(max(latReadLineBuffer,max(latOutputWrite_fk,latReadLineBuffer)))
    # print "latProcIstagingBuff:"+str(latProcIstagingBuff)


    #* latency of loading input for computation of one row: latReadLineBuffer
    #* latency of writing output of  one row: latStoreOStagingBuff_fj
    #* latency of computing one row: latProcInputBuff_fd
    #* return the maximum of above three as the one row latency. usually it is latProcInputBuff_fd

    if ChaiDnn:
        return max(latReadLineBuffer, latStoreOStagingBuff_fj, latProcInputBuff_fd)/rowStep * (conv_group + 1)
    else:
        return max(latReadLineBuffer, latStoreOStagingBuff_fj, latProcInputBuff_fd)

def computeLatency_pooling(ow, fw, fh, odepth, pipelined):
    
    pipelined = False
    if pipelined:
        return ow*fw*fh *odepth/16
    else:
        return ow*fw*fh *odepth/32

def computeLatency_eltwise(ow, odepth):
    return ow*odepth/16

conv_inp_height = 20
conv_inp_width = 20
conv_out_height = 18
conv_out_width = 18
conv_out_planes =  1
conv_inp_planes = 1
conv_stride = 1 
conv_filter_height = 3
conv_filter_width = 3
conv_pad = 0
conv_group = 1
rowStep = 1
XI_KER_PROC = 8
XI_PIX_PROC = 16
XI_WEIGHTBUFF_DEPTH = 512

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

conv_inp_height = 13
conv_inp_width = 13
conv_out_height = 13
conv_out_width = 26
conv_out_planes =  384
conv_inp_planes = 256
conv_stride = 1 
conv_filter_height = 3
conv_filter_width = 3
conv_pad = 1
conv_group = 1
rowStep = 1
XI_KER_PROC = 16
XI_PIX_PROC = 16
XI_WEIGHTBUFF_DEPTH = 1024

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

aa = computeLatency(
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
    0,
    1
    )

print aa, aa*conv_out_height/rowStep
#
#
#computeLatency(224,224,55,55,96,4,4,11,11,0,0,1,16,32,1024,1,0)
