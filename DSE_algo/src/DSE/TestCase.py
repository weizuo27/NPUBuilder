import latencyEstimation_new
import infoClass

import itertools



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




def takeSecond(elem):
    return elem[1]

def edgeToDepsTable(
    EdgeTable
):
    DepsTable={}
    for i in EdgeTable:
        s,t=i;
        if t in  DepsTable:
            DepsTable[t].add(s);
        else:
            DepsTable[t]=set([s]);
    return DepsTable








def checkPartitionLegal(
    partition,
    DepsTable, # a dictionary with DepsTable[i] is a set of layerId that i depends on
    NostreamTable, # a dictionary with NostreamTable[i] is a set of layerId that i cant be scheduled in same round with
    layerNum,
):
    pCopy=dict( zip(range(len(partition)),partition ));
    
    partitionLegal=True;
    layerDone=[False]*layerNum;
    partionSchedulingList=[]
    layerDone=[False]*layerNum;

    while(1):
        if( not pCopy ): break;
        roundScheduled=False
        for roundIdx,rounds in pCopy.items():
            layerInCurrentRound=set(rounds);
            roundFufill=True;
            for layer in rounds:
                if layer not in DepsTable:
                    continue
                for depsLayer in  DepsTable[layer]:
                    if( layerDone[depsLayer]==True):
                        continue
                    if depsLayer not in layerInCurrentRound or (layer in NostreamTable and  depsLayer in NostreamTable[layer] ):
                        roundFufill=False;
                        break;
                if roundFufill==False:
                    break
            if(roundFufill==True):
                partionSchedulingList.append(rounds);
                del pCopy[roundIdx]
                roundScheduled=True;
                for layerid in rounds:
                    layerDone[layerid]=True;
        if roundScheduled==False:
            return []
    return partionSchedulingList



def ipMapping(
    layerInRound,
    layerType,
    layerPerIPlatencyList,

):
    typeDict={}
    
    for i in layerInRound:
        if layerType[i] in typeDict:
            typeDict[layerType[i]].append(i);
        else:
            typeDict[layerType[i]]=[i];
    
    for k,layerIdList in typeDict.items():
        if len(layerIdList)>=ipNumDict[k]:
            return None, None
    
    latencTotal=0;
    ipMappingDict={}
    for k,layerIdList in typeDict.items():
        ipIdxlist=range(len(layerIdList));
        latencyMinMaxType=float("inf");
        depositipIdxPermute=[]
        for idx,ipIdxPermute in itertools.permutations(ipIdxlist):
            latencyMax=0;
            for permuteIdx,layerId in enumerate(layerIdList):
                ipIdx= ipIdxPermute[ipIdxPermute];
                latencyMax=max(latencyMax,layerPerIPlatencyList[layerId][ipIdx] );

            if latencyMax < latencyMinMaxType:
                depositipIdxPermute=ipIdxPermute;
                latencyMinMaxType=latencyMax     
        latencTotal=max(latencTotal, latencyMax)
        for permuteIdx,layerId in enumerate(layerIdList):
            ipMappingDict[layerId]=depositipIdxPermute[permuteIdx];
    
    return latencTotal,ipMappingDict


def ipLatency(
    ipNumDict,
    layerPartitionScheduling,
    layerPerIPlatencyList,
    layerType
):

    for layerInRound in layerPartitionScheduling:

        typeDict={}
        for i in layerInRound:
            if layerType[i] in typeDict:
                typeDict[layerType[i]].append(i);
            else:
                typeDict[layerType[i]]=[i];
        for k,layerIdList in typeDict.items():
            if len(layerIdList)>ipNumDict[k]:
                return None, None  
    
    ipMappingDict={}
    latencyTotal=0;
    for layerInRound in layerPartitionScheduling:
        typeDict={}
        for i in layerInRound:
            if layerType[i] in typeDict:
                typeDict[layerType[i]].append(i);
            else:
                typeDict[layerType[i]]=[i];
        latencyRound=0
        for k,layerIdList in typeDict.items():
            ipIdxlist=range(len(layerIdList));
            latencyMinMaxType=float("inf");
            depositipIdxPermute=[]

            for idx,ipIdxPermute in enumerate(itertools.permutations(ipIdxlist)):
                latencyMax=0;
                for permuteIdx,layerId in enumerate(layerIdList):
                    ipIdx= ipIdxPermute[permuteIdx];
                    latencyMax=max(latencyMax,layerPerIPlatencyList[layerId][ipIdx][1] );
                if latencyMax < latencyMinMaxType:
                    depositipIdxPermute=ipIdxPermute;
                    latencyMinMaxType=latencyMax  
               
            latencyRound=max(latencyRound, latencyMinMaxType)

            for permuteIdx,layerId in enumerate(layerIdList):
                if layerId in ipMappingDict: print "Warning layerId", layerId, "already in ipMapping"
                ipMappingDict[layerId]=depositipIdxPermute[permuteIdx];
        latencyTotal=latencyTotal+latencyRound;
    return latencyTotal,ipMappingDict

            







def computeOptimalLatencyDSP(
    depencyPairSet, 
    noStreamEle,
    layerType,
    layerArray,
    layerPerIPlatencyList, 
    ConvIPnum,
    PoolIPnum,
    EleIPnum,
    MaxRound):

    ipNumDict={"Convolution":ConvIPnum,"Pooling":PoolIPnum,"Eltwise":EleIPnum}
    DepsTable=edgeToDepsTable(depencyPairSet);
    NostreamTable=edgeToDepsTable(noStreamEle);
    layerNum=len(layerType)
    LayerIds=range(layerNum );
    depositLatency=float("inf")
    depositIPmapping=None
    depositScheduling=None
    for n, p in enumerate(partition(LayerIds), 1):
        partionSchedulingList=checkPartitionLegal(p,DepsTable,NostreamTable,layerNum);
        if(not partionSchedulingList ):continue;
        latencyPartition,ipMapping=ipLatency(ipNumDict,partionSchedulingList,layerPerIPlatencyList,layerType);

        if latencyPartition and  latencyPartition<depositLatency:
            depositLatency=latencyPartition;
            depositIPmapping=ipMapping
            depositScheduling=partionSchedulingList;

    if depositIPmapping is None:
        print " no feasible scheduling found in Corssverifcation"
        return None,None,None;

    roundDict={}
    roundMapping=[]       
    
    for roundIdx,rounds in enumerate(depositScheduling):
        layerMapping=[]
        for layerIdx in rounds:
            IPIdx=depositIPmapping[layerIdx]
            roundDict[layerIdx]=roundIdx;
            layerMapping.append( (roundIdx,layerArray[layerIdx],layerPerIPlatencyList[layerIdx][IPIdx][0]) );
        roundMapping.append(layerMapping);

    return roundMapping,roundDict,depositLatency;



        
        


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




