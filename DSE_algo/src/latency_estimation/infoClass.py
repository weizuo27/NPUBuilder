class layerInfo_t():
    layerType=None
    inp_height=None
    inp_width=None
    out_height=None
    out_width=None
    out_planes=None
    inp_planes=None
    stride=None
    filter_height=None
    filter_width=None
    pad=None
    groupFlag=None
    layerID=None
    memIn=None
    memInL=None
    memInR=None
    memOut=None
    rowStep=None

class IPinfo_t():
    IPtype=None
    IPidx=None 
    K_x_P= None
    XI_KER_PROC=None
    XI_PIX_PROC=None
    XI_WEIGHTBUFF_DEPTH=None
    XI_INDEPTH=None;
    XI_OUTDEPTH=None;
    int6bit=None
    BRAM=None
    IBRAM=None
    OBRAM=None
    WBRAM=None
    OtherBRAM=None


class runInfo_t():
    #note by XInheng: I am trying to simulate latency for rounds that involves multiple pipeline chain
    #latency for multiple pipeline chain would be not accurate
    #we current cannot support branch structure
    layerInfo=None #layerInfo_t
    IPidx=None
    nextIPidx=None #if it is involved in a one chain pipeline, then specify next IPidx
    prevIPidx=None #if it is involved in a one chain pipeline, then specify prev IPidx
    



class roundILPInfo_t():
    roundIdx=None;
    rowStep=None;
    IBRAMList=[];
    OBRAMList=[];
    IPindexList=[];
    ConstantBRAM;


