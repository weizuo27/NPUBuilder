1. The rule to generate XXNet_optimized_graph.txt
    1. This is based on the output of CHaiDNN, in the software folder, using the function XGraph::print(), but with some addtional information

    2. In the file, the First group is the "LayerGroups", 
        1. Must start with "# -------------------- LayerGroups ------------------------ #".
        2. Each row is a group which is considering the pipelined option.
        3. Must end with an empty line.

    3. The 2nd group is layers in the network. This is the same format as the ChaiDNN print() output.
        1. Must start with "# -------------------- Layers ------------------------ #"
        2. Must end with an emtpy line

    4. The 3rd group is the blob group. This describes the input/output of each layer. This is the same format as the ChaiDNN print() output
        1.Must start with "# -------------------- Blobs ------------------------ #"
        2. Must end with an empty line

2. The rule to generate layerIDMapping:
    Each row is a layer, following the format of "LayerName : ID". The IDs numbered using CHaiDNN software, and is dumped out from CHaiDNN

3. The rule to generate PoolingTyping:
    Each row is a pooling layer, following the format of "LayerName : [max/avg]". This is also dumped out from CHaiDNN
