1. Installing:
    1.  Install Gurobi following this link. 
1. Input files need to be prepared to run the flow:
    go to folder ./inputFiles
    1. IP_config_w_DSP (The list of IPs to select among and their DSP consumptions configurations)
    2. layerIDMapping(The layer ID of each layer for a network. I have given example for four networks, named as "layerIDMappingXXNet", can copy them as "layerIDMapping")
    3. PoolingTyping(The pooling type of each pooling layer for a network. I have given example for four networks, named as "PoolingTypingXXNet", can copy as "PoolingTyping")
    .4 input NN graph (The graph structure of the networks. I have given the graph for the four networks, named as "xxNet_optimized_graph.txt)
        Note: To generate this graph file for other networks, it need to be written in a specific format.

2. To run the flow (example)
    1. python top_4.py 1800 2190 294080 448160 10000 10000000000000 ./inputFiles/res_optimized_graph.txt  ./inputFiles/IP_config_w_DSP 2 2 0 2 1 2 2

    2. To understand the meaning of each argument:
        1. python top_4.py -h
            It gives the explaination of the arguments

3. The output of the flow:
    go to folder outputFiles. It has two parts(folders): hw and sw, which is coresponding to the generated file for hardware design and software design
    1. hw: (will add explaination later). Can copy to the correct folder (the folders need to be created)
        callOrder.csv : The IP calling order for each round. E.g., there are 3 IPs used to compose the NPU, the order of each round may be different.
        dnn_wrapper.cpp : The wrapper cpp file which is used for the 
        ipNameList : The list of IPs used in the NPU
        ippackGen.sh : This should be the shell script to generate each IP, but since currently the interface is changing, it may not work.
        pipeSystem.cpp : The top level NPU CPP file
        pipeSystem.h : The headerfile for the NPU
        round.csv : The IP configuration of each round

        pipeSystemTemp : This is used for sw generation, not used for design.

    2. sw (Following the folder orgnization of the CHaiDNN)
        csvParser.cpp : Copy to scheduler folder
        csvParser.hpp : Copy to scheduler folder
        utils_wei.cpp : Copy to scheduler folder
        utils_wei.hpp : Copy to scheduler folder
        xi_scheduler.cpp : Copy to scheduler folder (replace the original xi_scheduler.cpp)
        xi_kernels.cpp : Copy to folder "common"
        xi_kernels.h :  Copy to folder "common"
