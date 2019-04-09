import math

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
    alignedOutputPlane =  AlignSize(conv_out_planes,16)
    NKPF=min(requiredNKPF, alignedOutputPlane/KER)
    #In CHaiDNN's flow, the NKPF shall be constraint at the factor of  alignedOutputPlane/KER, however, I think it does not have to be the real factor
    #need to modify hardware
    weightDepth= AlignSize(fh*fw*computePlanesAligned/4*NKPF+1,1024)
    return weightDepth



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















    


    




def straddle(layerInfo )




def rawDSP( K_x_P):
    """
    return the estimated DSP for a conv IP with ker_proc by pix_proc  as K_x_P in first round scheduling
    input K_x_P: the product of ker_proc and pix_proc
    return: estiumated DSP
    """
    return K_x_P*2.2

def rawLatency( layerInfo, K_x_P ):
    """
    return the estimated latency for a certain K_x_P in first round scheduling
    input layerInfo: the class containg convolution layer information
    input K_x_P: the product of ker_proc and pix_proc
    return: estimated latency
    """
    conv_filter_height= layerInfo.conv_filter_height
    conv_filter_width= layerInfo.conv_filter_width
    conv_inp_planes  = layerInfo.conv_inp_planes 
    conv_out_height  = layerInfo.conv_out_height   
    conv_out_width   = layerInfo.conv_out_width    
    conv_out_planes  = layerInfo.conv_out_planes  
    return conv_filter_height*conv_filter_width*conv_inp_planes*conv_out_planes*conv_out_height*conv_out_width/K_x_P/4;



