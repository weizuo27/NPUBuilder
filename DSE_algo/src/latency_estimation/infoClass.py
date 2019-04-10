class layerInfo_t():
    self.layerType=None
    self.inp_height=None
    self.inp_width=None
    self.out_height=None
    self.out_width=None
    self.out_planes=None
    self.inp_planes=None
    self.stride=None
    self.filter_height=None
    self.filter_width=None
    self.pad=None
    self.groupFlag=None
    self.layerID=None
    self.memIn=None
    self.memInL=None
    self.memInR=None
    self.memOut=None
    self.rowStep=None

class IPinfo_t():
    self.IPtype=None
    self.IPidx=None 
    self.K_x_P= None
    self.XI_KER_PROC=None
    self.XI_PIX_PROC=None
    self.XI_WEIGHTBUFF_DEPTH=None
    self.XI_INDEPTH=None;
    self.XI_OUTDEPTH=None;
    self.int6bit=None
    self.BRAM=None
    self.IBRAM=None
    self.OBRAM=None
    self.WBRAM=None
    self.OtherBRAM=None


class runInfo_t():
    #note by XInheng: I am trying to simulate latency for rounds that involves multiple pipeline chain
    #latency for multiple pipeline chain would be not accurate
    #we current cannot support branch structure
    self.layerInfo=None #layerInfo_t
    self.IPidx=None
    self.nextIPidx=None #if it is involved in a one chain pipeline, then specify next IPidx
    self.prevIPidx=None #if it is involved in a one chain pipeline, then specify prev IPidx
    



class roundILPInfo_t():
    self.roundIdx=None;
    self.rowStep=None;
    self.IBRAMList=[];
    self.OBRAMList=[];
    self.IPindexList=[];
    self.ConstantBRAM;


