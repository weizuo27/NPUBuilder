This is the read me file for the assemple pipelined ChaiDNN for AlexNet.

1. Top function explanation:

Parameter 1 to 14: Data Ports for IP36
Parameter 15-26: Data Ports for IP110A
Parameter 27-38: Data Ports for IP110B
Parameter 29-32: Data Ports for pool1
Parameter 33-36: Data Ports for pool2
Parameter 37-42: Argument ports.

2. Argument Setting:
    (1) argsConvIP36/argsConvIP110A/argsConvIP110B
    The content in argsConv[128] is specified as follows:




    argsConv[0-110]: content in original scalar_conv_args.
    args[125]:No operation flag, set it to 1 if in this round the corresponding IP is idle.
    args[126]:Stream in flag. Set it to 1 if in this function call round the convoltuion IP read data from the stream port of its previous IP. Otherwise, the IP read input data from its input memory port.
    args[127]:Stream out flag. Set it to 1 if in this function call round the convoltuion IP read write to the stream port of its next IP. Otherwise, the IP write output data to its output memory port.

    (2)argsPool1/argspool2
    The content in argsPool[32] is specified as follows:

    args[21] and args[22]: 
        bypass flag and by pass number. Set bypass flag to 1 if the current pool layer requires a bypass or current pool layer is idle in current function call  round. 
    
        By pass number SHOULD equal the number of ap_uint<128> data pack that is required to by pass. If its previous layer is convolution layer, by pass number should follows following formular:
        argsPool[22]/*by pass num*/=  argsPreviousConv[2] * argsPreviousConv[3] * argsPreviousConv[62]/16 /*outHeight*outWidht*outDepth/16*/

        By pass number SHOULD equal to 0(ZERO)  if the pool IP is IDLE in this function round.

        if current pooling layer is neither idle nor bypass, set args[21] to 0 and follows following configuration.


    args[0-14]: original ChaiDNN generated pool layer spefication data.
    args[15-18]: generated with following code:
    /************************CODE*********************************/
    short in_h        	= argsPool[0]; 
	short in_w        	= argsPool[1]; 
	short out_h       	= argsPool[2]; 
	short out_w      	= argsPool[3];
	short n_planes    	= argsPool[4]; 
	short ps_h	  	    = argsPool[5];
	short ps_w	  	    = argsPool[6];
	short pwin_h	  	= argsPool[7];
	short pwin_w	  	= argsPool[8];
	unsigned char avg_pool	= argsPool[9];
	unsigned char pad	    = argsPool[10];
	unsigned char one_by_diviser	= argsPool[11];
	unsigned char conv3ds	= argsPool[12];
	unsigned char relu		= argsPool[13];
	unsigned char outshift	= argsPool[14];

	uRowIdx_t rowStep = 1;
 	uRowIdx_t initialReadRows = pwin_h+(rowStep-1)*ps_h-pad;
    ap_uint<32> inDDRPlaneStep= in_h*in_w;
    ap_uint<32> outDDRPlaneStep= out_w*out_h;

	argsPool[15] = rowStep;
	argsPool[16] = initialReadRows;
	argsPool[17] = inDDRPlaneStep;
    argsPool[18] = outDDRPlaneStep;
    /************************************************************/

    args[19]: stream in flag.
    args[20]: stream out flag.

    (3) argsStreamDivisor/argsStreamConbiner

    Divisor and combiner is used to divide the input stream into 2 stream for group convolution or combine output stream of group convolution into one stream.
    Each one have a argument array argsStreamDivisor[3]/argsStreamConbiner[3]

    IF the combiner or the divisor is idle, argsStreamDivisor[0-2]/argsStreamConbiner[0-2] SHOULD be set as 0.
    
    Otherwise set the content following:
    
    argsStreamDivisor[0]=argsGroupConvA[0];
    argsStreamDivisor[1]=argsGroupConvA[1];
    argsStreamDivisor[2]=argsGroupConvA[61]/16;  


    argsStreamCombiner[0]=argsGroupConvA[2];
    argsStreamCombiner[1]=argsGroupConvA[3];
    argsStreamCombiner[2]=argsGroupConvA[62]/16;  




void ConvPipeline
(
    gmem_weighttype *IP36_weights1, 
    gmem_weighttype *IP36_weights2,
    gmem_weighttype *IP36_weights3,
    gmem_weighttype *IP36_weights4,
    gmem_outputtype *IP36_output1,
    gmem_outputtype *IP36_output2,
    gmem_inputtype_layerx *IP36_input_other1,	
    gmem_inputtype_layerx *IP36_input_other2,
    gmem_inputtype_layer1 *IP36_input_1st,
    gmem_biastype *IP36_bias,
    gmem_inputtype_layer1 *IP36_inp_norm_2, 
    gmem_inputtype_layer1 *IP36_inp_norm_3,
    gmem_inputtype_layer1 *IP36_istg_out1,
    gmem_inputtype_layer1 *IP36_istg_out2,


    gmem_weighttype *IP110A_weights1, 
    gmem_weighttype *IP110A_weights2,
    gmem_outputtype *IP110A_output1,
    gmem_outputtype *IP110A_output2,
    gmem_inputtype_layerx *IP110A_input_other1,	
    gmem_inputtype_layerx *IP110A_input_other2,
    gmem_inputtype_layer1 *IP110A_input_1st,
    gmem_biastype *IP110A_bias,
    gmem_inputtype_layer1 *IP110A_inp_norm_2, 
    gmem_inputtype_layer1 *IP110A_inp_norm_3,
    gmem_inputtype_layer1 *IP110A_istg_out1,
    gmem_inputtype_layer1 *IP110A_istg_out2,

    gmem_weighttype *IP110B_weights1, 
    gmem_weighttype *IP110B_weights2,
    gmem_outputtype *IP110B_output1,
    gmem_outputtype *IP110B_output2,
    gmem_inputtype_layerx *IP110B_input_other1,	
    gmem_inputtype_layerx *IP110B_input_other2,
    gmem_inputtype_layer1 *IP110B_input_1st,
    gmem_biastype *IP110B_bias,
    gmem_inputtype_layer1 *IP110B_inp_norm_2, 
    gmem_inputtype_layer1 *IP110B_inp_norm_3,
    gmem_inputtype_layer1 *IP110B_istg_out1,
    gmem_inputtype_layer1 *IP110B_istg_out2,



    GMEM_MAXPOOLTYPE* pool1_inMem1,
    GMEM_MAXPOOLTYPE* pool1_inMem2,
    GMEM_MAXPOOLTYPE* pool1_outMem1,
    GMEM_MAXPOOLTYPE* pool1_outMem2,

  
    GMEM_MAXPOOLTYPE* pool2_inMem1,
    GMEM_MAXPOOLTYPE* pool2_inMem2,
    GMEM_MAXPOOLTYPE* pool2_outMem1,
    GMEM_MAXPOOLTYPE* pool2_outMem2,
  
    int* argsConvIP36,
    int* argsConvIP110A,
    int* argsConvIP110B,
    int* argsPool1,
    int* argsPool2,
    int* argsStreamDivisor,
    int* argsStreamCombiner
)