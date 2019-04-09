class layerInfo_t():
    layerType= None
    inp_height   =None
    inp_width   =None
    out_height   =None
    out_width   =None
    out_planes  =None
    inp_planes   =None
    stride       =None
    filter_height=None
    filter_width =None
    pad          =None
    groupFlag        =None
    layerID = None

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
    layerInfo=None #layerInfo_t, or pointer to layerInfo_t
    IPInfo=None #IPInfo_t, or pointer to IPInfo_t
    nextIPidx=None
    rowStep=None
    memIn=None
    memInL=None
    memInR=None
    memOut=None
    memOutL=None
    memOutR=None

class roundInfo():
    roundIdx=None;
    rowStep=None;
    IBRAMList=[];
    OBRAMList=[];
    IPindexList=[];
    ConstantBRAM


