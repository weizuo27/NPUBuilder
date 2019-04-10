class layerInfo_t():
    def __init__(self, layerType=None, inp_height=None,
        inp_width=None, out_height=None, out_width=None,
        out_planes=None, inp_planes=None, stride=None,
        filter_height=None, filter_width=None, pad=None,
        groupFlag=None, layerID=None, memIn=None,
        memInL=None, memInR=None, memOut=None, rowStep=None):
        self.layerType=layerType
        self.inp_height=inp_height
        self.inp_width=inp_width
        self.out_height=out_height
        self.out_width=out_width
        self.out_planes=out_planes
        self.inp_planes=inp_planes
        self.stride=stride
        self.filter_height=filter_height
        self.filter_width=filter_width
        self.pad=pad
        self.groupFlag=groupFlag  #0: Conv, 1 Conv_g
        self.layerID=layerID
        self.memIn=memIn
        self.memInL=memInL
        self.memInR=memInR
        self.memOut=memOut
        self.rowStep=rowStep
    
class IPinfo_t():
    def __init__(self,
            IPtype=None, IPidx=None, K_x_P= None,
            XI_KER_PROC=None, XI_PIX_PROC=None,
            XI_WEIGHTBUFF_DEPTH=None,
            XI_INDEPTH=None, XI_OUTDEPTH=None,
            int6bit=None, BRAM=None,
            IBRAM=None, OBRAM=None, WBRAM=None,
            OtherBRAM=None):
            self.IPtype=IPtype
            self.IPidx=IPidx
            self.K_x_P= K_x_P
            self.XI_KER_PROC=XI_KER_PROC
            self.XI_PIX_PROC=XI_PIX_PROC
            self.XI_WEIGHTBUFF_DEPTH=XI_WEIGHTBUFF_DEPTH
            self.XI_INDEPTH=XI_INDEPTH
            self.XI_OUTDEPTH=XI_OUTDEPTH
            self.int6bit=int6bit
            self.BRAM=BRAM
            self.IBRAM=IBRAM
            self.OBRAM=OBRAM
            self.WBRAM=WBRAM
            self.OtherBRAM=OtherBRAM


class runInfo_t():
#note by XInheng: I am trying to simulate latency for rounds that involves multiple pipeline chain
#latency for multiple pipeline chain would be not accurate
#we current cannot support branch structure
    def __init__(self,
        layerInfo=None, #layerInfo_t
        IPidx=None,
        nextIPidx=None, #if it is involved in a one chain pipeline, then specify next IPidx
        prevIPidx=None #if it is involved in a one chain pipeline, then specify prev IPidx
        ):
        self.layerInfo=None
        self.IPidx=None
        self.nextIPidx=None
        self.prevIPidx=None
        



class roundILPInfo_t():
    def __init__(self,
    roundIdx=None,
    rowStep=None):
        self.roundIdx=None
        self.rowStep=None
        self.IBRAMList=[];
        self.OBRAMList=[];
        self.IPindexList=[];
        self.ConstantBRAM=None;


