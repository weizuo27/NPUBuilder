
1. Input files need to be prepared to run the flow:
    go to folder ./inputFiles
    >> IP_config_w (The list of IPs to select among and their configurations)
    
        This can be generated in src/latency_estimation/genIPconfig.py (after generation, file needs to be copied here)
    
    >> layerIDMapping(The layer ID of each layer for a network. I have given example for four networks, named as "layerIDMappingXXNet", can copy them as "layerIDMapping")
    >> PoolingTyping(The pooling type of each pooling layer for a network. I have given example for four networks, named as "PoolingTypingXXNet", can copy as "PoolingTyping")
    >> input NN graph (The graph structure of the networks. I have given the graph for the four networks, named as "xxNet_optimized_graph.txt)
    
    Note: To generate this graph file for other networks, it need to be written in a specific format.

2. To run the flow (example)
    >> time python top_4.py 1400 2090 294080 448160 10000 19000000 ./inputFiles/google_optimized_graph.txt  "./inputFiles/IP_config_w" 4

    To understand the meaning of each argument:
        >> python top_4.py -h
        It gives the explaination of the arguments

3. The output of the flow:
    go to folder outputFiles. It has two parts(folders): hw and sw, which is coresponding to the generated file for hardware design and software design
    1. hw: (will add explaination later). Can copy to the correct folder (the folders need to be created)
        callOrder.csv :
        dnn_wrapper.cpp : 
        ipNameList : 
        ippackGen.sh : 
        pipeSystem.cpp : 
        pipeSystem.h : 
        round.csv :


        pipeSystemTemp : This is used for sw generation, not used for design.

    2. sw (Following the folder orgnization of the CHaiDNN)
        csvParser.cpp : Copy to scheduler folder
        csvParser.hpp : Copy to scheduler folder
        utils_wei.cpp : Copy to scheduler folder
        utils_wei.hpp : Copy to scheduler folder
        xi_scheduler.cpp : Copy to scheduler folder (replace the original xi_scheduler.cpp)
        xi_kernels.cpp : Copy to folder "common"
        xi_kernels.h :  Copy to folder "common"
