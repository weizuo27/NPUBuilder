from latencyEstimation_new import computeLatency
f = open("eval.csv", 'r')
next(f)
for l in f:
    layerID, \
    layerType, \
    conv_inp_planes  , \
    conv_inp_height, \
    conv_inp_width   , \
    conv_out_planes  , \
    conv_out_height  , \
    conv_out_width   , \
    conv_filter_height,\
    conv_filter_width, \
    conv_stride      , \
    conv_pad         , \
    conv_group       , \
    rowStep,\
    XI_KER_PROC,\
    XI_PIX_PROC,\
    XI_WEIGHTBUFF_DEPTH,\
    int6bit \
    = l.strip().split(",")[0:-1]


    lat_one_row = computeLatency (
    int(conv_inp_height  ), 
    int(conv_inp_width   ), 
    int(conv_out_height  ), 
    int(conv_out_width   ), 
    int(conv_out_planes  ), 
    int(conv_inp_planes  ), 
    int(conv_stride      ), 
    int(conv_filter_height),
    int(conv_filter_width), 
    int(conv_pad         ), 
    int(conv_group       ), 
    int(rowStep),
    int(XI_KER_PROC),
    int(XI_PIX_PROC),
    int(XI_WEIGHTBUFF_DEPTH),
    int(int6bit),
    int(layerID))

    print "layerID", layerID, "latency_one_row", lat_one_row, "total latency", lat_one_row*int(conv_out_height)/int(rowStep)
f.close()
