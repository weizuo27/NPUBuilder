import latencyEstimation_new
import infoClass









def partition(collection):
    if len(collection) == 1:
        yield [ collection ]
        return

    first = collection[0]
    for smaller in partition(collection[1:]):
        # insert `first` in each of the subpartition's subsets
        for n, subset in enumerate(smaller):
            yield smaller[:n] + [[ first ] + subset]  + smaller[n+1:]
        # put `first` in its own subset 
        yield [ [ first ] ] + smaller








def computeOpsPooling( layerInfo ):
    return layerInfo.out_height*layerInfo.out_width*layerInfo.filter_height*layerInfo.filter_width*layerInfo.out_planes/16;

def computeOpsEle( layerInfo ):
    return layerInfo.out_height*layerInfo.out_width*layerInfo.out_planes/16;

def computeOpsConv(layerInfo):
     return layerInfo.out_height*layerInfo.out_width*layerInfo.filter_height*layerInfo.filter_width*layerInfo.out_planes*layerInfo.inp_planes;



           

OpsFun={"Convolution":computeOpsConv,
        "Pooling":computeOpsPooling,
        "Eltwise":computeOpsEle}

solution=[]
def takeSecond(elem):
    return elem[1]


def computeOptimalLatencyDSP(
    DepsTable,
    RstsTable,
    layerInfoList,
    IPtable,
    blobKeys
):

    LayerIds=range( len(layerInfoList) );
    depositLatency=float("inf");
    depositKxP=None
    depositPartition=None
    for n, p in enumerate(partition(LayerIds), 1):
        #p is one possible partition of [0:layerNUmber-1]

        #check whether the partition of P is legal
        pCopy=dict( zip(range(len(p)),p ))

        computed=dict.fromkeys(blobKeys,False);
        


        partitionLegal=True;

        while(1):
            #break if all the round can be computed
            if( not pCopy ): break;
            #check whether any layer dependency is fufilled
            
            depsOKRoundIdx=[];
            CanSchedule=False
            passedRound=0;
            for roundIdx,rounds in pCopy.items():
                computedInternal=dict.fromkeys(blobKeys,False);
                #compute internal result, the result are assumed to be computed if for pipelined layers
                for layerid in rounds:
                    blobId = RstsTable[layerid]
                    computedInternal[ blobId ] =True;

                #all depedents in all the layer should be fufilled;

                roundFufill=True;
                for layerid in rounds:
                    for blobId in DepsTable[layerid]:
                        if( computedInternal[blobId] == False and computed[blobId] == False ):
                            roundFufill=False;
                            break;
                    if(roundFufill==False):
                        break;

                if(roundFufill==True):
                    depsOKRoundIdx.append(roundIdx);
                    for layerid in rounds:
                        blobId=RstsTable[layerid];
                        computed[ blobId ] =True;
            
                    
    
                
            if(not depsOKRoundIdx):
                #if after such search, no new rounds depedency is fufilled, then the partition is illegal
                # print "Illegal partition!", p
                partitionLegal=False;
                break;
            else:
                for i in depsOKRoundIdx:
                    del pCopy[i];
        # print "Legal Partition", p
    
        if(partitionLegal==False ):continue;

        IPfeasible=True
        runInfo=[]
        totalLatency=0
        KxPTable={}
        for runs in p:
            layerInfo={}
            for idx in runs:
                layerType=layerInfoList[idx].layerType
                if( layerType not in  layerInfo ):
                    layerInfo[layerType]=[];
                layerInfo[layerType].append([idx,OpsFun[layerType](layerInfoList[idx]),1]);

            for k,v in layerInfo.items():
                v.sort(key=takeSecond);


            breakFlag=False
            roundLatency=[]
            for k,v in layerInfo.items():
                if(len(v) > len(IPtable[k] )):
                    print "illegal IP number", len(v), len(IPtable[k] ), v
                    breakFlag=True
                    break
                for o,d in zip(v,IPtable[k]):
                    o[2]=d
                    KxPTable[o[0]]=d;
                    tempIPinfo=infoClass.IPinfo_t(K_x_P=d, IPtype=layerInfoList[o[0]].layerType);
                    roundLatency.append( latencyEstimation_new.computeLatencyDSP( layerInfoList[o[0]],tempIPinfo) );

            if breakFlag:
                IPfeasible=False;
                break;
            totalLatency+=max(roundLatency);
        if IPfeasible and totalLatency< depositLatency:
            # print "legal pipeline",p
            # print totalLatency
            # print KxPTable
            depositKxP=KxPTable
            depositLatency=totalLatency
            depositPartition=p
        # elif IPfeasible:
        #     print "Not depositing",totalLatency,depositLatency
        
        # else:
        #     print "Illegal IP" 


    return depositLatency,depositPartition,depositKxP


def updateCombineCounterDescending(counter,Num ):
    idx=0;
    while(1):        
        counter[idx]+=1;
        if( counter[idx]==Num ):
            if(idx < len(counter)-1 ):
                counter[idx]=counter[idx+1]+1;
                idx+=1;
            else:
                return True;
        else:
            break;
    return False


def computeOptimalLatencyExploreK_x_P(
    DepsTable,
    RstsTable,
    layerInfoList,
    DSPbudget,
    ConvIPNumber,
    PoolIPNumber,
    ELeIPNUmber,
    blobKeys
):

    IPtable={}
    IPtable["Pooling"]=[1]*PoolIPNumber;
    IPtable["Eltwise"]=[1]*ELeIPNUmber;
    counter=[0]*ConvIPNumber;
    counter[0]=-1;
    depositLatency=float("inf")
    depositKxP=None
    depositPartition=None
    while(not updateCombineCounterDescending(counter,4) ):
        print counter;
        # IPtable["Eltwise"]=
        IPtable["Convolution"]= [ 1<<(6+i) for i in counter ];
        
        DSP=sum(IPtable["Convolution"])*2.2+sum(IPtable["Eltwise"])*37+sum(IPtable["Pooling"])*28;
        print IPtable["Convolution"], DSP, DSPbudget
        if DSP<0.5*DSPbudget or DSP>DSPbudget: continue

        Latency,Partition,KxP=computeOptimalLatencyDSP(
            DepsTable,
            RstsTable,
            layerInfoList,
            IPtable,
            blobKeys
        );
        if ( Latency<depositLatency ):
            depositLatency=Latency;
            depositKxP=KxP;
            depositPartition=Partition
            print "legal pipeline",Partition
            print Latency
            print KxP
        else:
            print "not depositing solution", Latency, depositLatency

    print depositLatency
    print depositPartition
    print depositKxP

    return depositLatency,depositPartition,depositKxP




# BlobKey=["one","two","three","four","five"]            
# Deps=[ [],[],["one"],["two"],["three","four"] ]
# Rsts=["one","two","three","four","five"]





# Ops=[300000,100000,30,2000000,20];
# # Ops = computeLatencyDSP(layerInfo, IPInfo) with IPInfo.K_x_P = 1

# IPtable= { "Convolution":[512,256],
#            "Pooling":[1],
#            "Eltwise":[1]}

# # structure, () is blob, [1] is layer
# # (0)->[0:Conv]->(1)->[2:Conv]->(3)
# # (0)->[1:Pool]->(2)->[3:Conv]->(4)
# # (2,4)->[4:ELe]->(5)


# layerInfoList=[]

# x=infoClass.layerInfo_t(
#         layerType="Convolution", 
#         inp_height=224,
#         inp_width=224, 
#         out_height=224, 
#         out_width=224,
#         out_planes=256, 
#         inp_planes=256, 
#         stride=None,
#         filter_height=3, 
#         filter_width=3, 
#         pad=None,
#         groupFlag=None, 
#         layerID=None, 
#         memIn=None,
#         memInL=None, 
#         memInR=None, 
#         memOut=None, 
#         rowStep=None)
# layerInfoList.append(x)

# x=infoClass.layerInfo_t(
#         layerType="Pooling", 
#         inp_height=224,
#         inp_width=224, 
#         out_height=224, 
#         out_width=224,
#         out_planes=256, 
#         inp_planes=256, 
#         stride=None,
#         filter_height=2, 
#         filter_width=2, 
#         pad=None,
#         groupFlag=None, 
#         layerID=None, 
#         memIn=None,
#         memInL=None, 
#         memInR=None, 
#         memOut=None, 
#         rowStep=None)

# layerInfoList.append(x)

# x=infoClass.layerInfo_t(
#         layerType="Convolution", 
#         inp_height=224,
#         inp_width=224, 
#         out_height=224, 
#         out_width=224,
#         out_planes=16, 
#         inp_planes=256, 
#         stride=None,
#         filter_height=1, 
#         filter_width=1, 
#         pad=None,
#         groupFlag=None, 
#         layerID=None, 
#         memIn=None,
#         memInL=None, 
#         memInR=None, 
#         memOut=None, 
#         rowStep=None);

# layerInfoList.append(x)

# x=infoClass.layerInfo_t(
#         layerType="Convolution", 
#         inp_height=224,
#         inp_width=224, 
#         out_height=224, 
#         out_width=224,
#         out_planes=256, 
#         inp_planes=16, 
#         stride=None,
#         filter_height=1, 
#         filter_width=1, 
#         pad=None,
#         groupFlag=None, 
#         layerID=None, 
#         memIn=None,
#         memInL=None, 
#         memInR=None, 
#         memOut=None, 
#         rowStep=None);

# layerInfoList.append(x)


            
# x=infoClass.layerInfo_t(
#     layerType="Eltwise", 
#     inp_height=224,
#     inp_width=224, 
#     out_height=224, 
#     out_width=224,
#     out_planes=256, 
#     inp_planes=256, 
#     stride=None,
#     filter_height=5, 
#     filter_width=5, 
#     pad=None,
#     groupFlag=None, 
#     layerID=None, 
#     memIn=None,
#     memInL=None, 
#     memInR=None, 
#     memOut=None, 
#     rowStep=None);              
                    
# layerInfoList.append(x)




                    
                




          




            
                    
# # computeOptimalLatencyDSP(
# #     DepsTable=Deps,
# #     RstsTable=Rsts,
# #     layerInfoList=layerInfoList,
# #     IPtable=IPtable,
# #     blobKeys=BlobKey,
# #     blobNumber=6
# # )
    


# computeOptimalLatencyExploreK_x_P(
#     Deps,
#     Rsts,
#     layerInfoList,
#     2090,
#     2,
#     1,
#     1,
#     BlobKey
# )
    



















