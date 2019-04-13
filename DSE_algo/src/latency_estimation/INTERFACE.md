THe interface is specified below:

1. IPinfoList
    A list of IPinfo_t involved in the current schduled result.
    IPinfo_t.IPtype,  IPinfo_t.K_x_P,  IPinfo_t.IPidx 
    should be specified while other member can remain None
    IPinfo_t.IPidx should be one of [0,len(IPinfoList)-1]
    IPinfoList should be sorted by IPinfo_t.IPidx
    example in all round, total 5 IP are used 

    ConvIP1 (K_x_P = 512);
    PoolIP1 (K_x_P = 0);
    ConvIP2 (K_x_P = 256);
    ConvIP3 (K_x_P = 128);
    ELeIP1  (K_x_P = 0);

    The IPinfoList should looks like:
        // for ConvIP1
        IPinfoList[0].IPtype="Convolution"
        IPinfoList[0].K_x_P=512
        IPinfoList[0].IPidx=0

        // for PoolIP1
        IPinfoList[1].IPtype="Pooling"
        IPinfoList[1].K_x_P=0
        IPinfoList[1].IPidx=1

        // for ConvIP2
        IPinfoList[2].IPtype="Convolution"
        IPinfoList[2].K_x_P=256
        IPinfoList[2].IPidx=2
    
        // for ConvIP3
        IPinfoList[3].IPtype="Convolution"
        IPinfoList[3].K_x_P=128
        IPinfoList[3].IPidx=3

        // for ELeIP1
        IPinfoList[4].IPtype="ELeIP1"
        IPinfoList[4].K_x_P=0
        IPinfoList[4].IPidx=4


2. roundInfoList
    datatype: runInfo_t[R][N]
    R is the round number
    N is the scheduled layer number in such round

    each runInfo_t contains the layer information, ip information and stream information of the layer in the current round

    runInfo_t member:
    runInfo_t.layerInfo: the layerInfo_t of represented layer 
    runInfo_t.IPidx: the IPidx of the IP to which the represented layer is mapped 
    runInfo_t.nextIPidx: If the layer is the end of pipeline chain, then it equals none, other wise 1;
    runInfo_t.prevIPidx:  not used, can leave it None.

    for a certain r in [0:R]
        runInfo_t[r] should be a list of runInfo_t representing layers in current rounds.
        layers should be sorted in the pipelie chain order.

        example:
        say in round r, the scheduling is following

        conv1 (mapped to IPinfoList[0] ) -> conv2 ( mapped to IPinfoList[3] ) -> pool1 ( mapped to IPinfoList[2] ) 
        conv3 (mapped to IPinfoList[1] ) -> Ele4  ( mapped to IPinfoList[4] ) 

        then roundInfoList[r] should looks like following:

        roundInfoList[r][0].layerInfo= layerInfo_t(conv1 )
        roundInfoList[r][0].IPidx= 0;
        roundInfoList[r][0].nextidx= 1;

        roundInfoList[r][1].layerInfo= layerInfo_t(conv2 )
        roundInfoList[r][1].IPidx= 3;
        roundInfoList[r][1].nextidx= 1;

        roundInfoList[r][2].layerInfo= layerInfo_t(pool1 )
        roundInfoList[r][2].IPidx= 2;
        roundInfoList[r][2].nextidx= None;

        roundInfoList[r][3].layerInfo= layerInfo_t(conv3 )
        roundInfoList[r][3].IPidx= 1;
        roundInfoList[r][3].nextidx= 1;

        roundInfoList[r][4].layerInfo= layerInfo_t(Ele4 )
        roundInfoList[r][4].IPidx= 4;
        roundInfoList[r][4].nextidx= None;

    the layerInfo_t should have
        memIn and memOut specified for conv and pool layers
        (memInL or memInR ) and  memOut specified for ele layers
        rowStep should remain None





you need to call  
    rowStepChoice,Latency=exploitK_xPCombination
    (
        roundInfoList,
        IPinfoList.
        BramBudget
    );

    the function will return   
        1. rowStepChoice, the chosen rowStep of each round
        2. the estimated latency.
    
    also, the function will
        fill 
        IPInfoList[i].XI_KER_PROC
        IPInfoList[i].XI_PIX_PROC
        IPInfoList[i].XI_WEIGHTBUFF_DEPTH
        IPInfoList[i].XI_INDEPTH
        IPInfoList[i].XI_OUTDEPTH
        of all the Convolution IPs in the IPInfoList

    you can deposit current  [IPInfoList,roundInfoList,rowStepChoice,Latency] as one solution candidate among different number of IPs.
    I can modify the code to directly put rowStepChoice in to roundInfoList




