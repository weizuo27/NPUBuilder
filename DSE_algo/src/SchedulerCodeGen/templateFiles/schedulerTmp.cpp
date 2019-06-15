/*----------------------------------------------------
Copyright 2017 Xilinx, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
----------------------------------------------------*/
#include "xi_scheduler.hpp"
#include "csvParser.hpp"
#include "utils_wei.hpp"
#include "../include/hw_settings.h"


#define OUTPUTSIZEBYTE 9216
char output1_gold[OUTPUTSIZEBYTE*2];
char output2_gold[OUTPUTSIZEBYTE*2];

template <class T>
void load_answer
(
    char* filename,
    T* output1_gold,
    int byteNum
)

{
    printf("Load %s\n",filename );
    FILE* fd = fopen(filename, "rb");
	int a=0;
	if(fd ==NULL) printf("%s not found\n",filename );
    a+=fread( output1_gold,sizeof(char),byteNum,fd);
    fclose(fd);
	printf("%d btytes loaded\n",a);
}

void save_answer
(
    char* filename,
    char* output1_gold,
    char* output2_gold,
    int byteNum
)
{
    printf("Save %s\n",filename );
    FILE* fd = fopen(filename, "wb");
    if(fd == NULL){
        printf("Cannot open %s\n", filename);
        return;
    }
    fwrite( output1_gold,sizeof(char),byteNum,fd);
    fwrite( output2_gold,sizeof(char),byteNum,fd);
    fclose(fd);
}



void save_file
(
    const char* filename,
    void* output,
    size_t Num
)
{
    printf("Savefile %s\n",filename );
    FILE* fd = fopen(filename, "wb");
    if(fd == NULL){
        printf("Cannot open %s\n", filename);
        return;
    }
    fwrite( (char*)output,sizeof(char),Num,fd);
    fclose(fd);
}

void setPoolingArgs( int *args, int *prev_args,bool idle,  bool bypass,
        bool stream_in, bool stream_out){
    if(idle){
        args[21] = 1;
        args[22] = 0;
        return;
    }
    if(bypass){
        args[21] = 1;
        args[22] = prev_args[2] * prev_args[3] * prev_args[62]/16;
        return;
    } 
    short in_h         = args[0];
    short in_w              = args[1];
    short out_h             = args[2];
    short out_w             = args[3];
    short n_planes          = args[4];
    short ps_h                  = args[5];
    short ps_w                  = args[6];
    short pwin_h            = args[7];
    short pwin_w            = args[8];
    unsigned char avg_pool  = args[9];
    unsigned char pad           = args[10];
    unsigned char one_by_diviser    = args[11];
    unsigned char conv3ds   = args[12];
    unsigned char relu              = args[13];
    unsigned char outshift  = args[14];

    int rowStep = 1;
    int initialReadRows = pwin_h+(rowStep-1)*ps_h-pad;
    unsigned int inDDRPlaneStep= in_h*in_w;
    unsigned int outDDRPlaneStep= out_w*out_h;

    args[15] = rowStep;
    args[16] = initialReadRows;
    args[17] = inDDRPlaneStep;
    args[18] = outDDRPlaneStep;

    args[19] = stream_in;
    args[20] = stream_out;
    args[21] = 0;
}

 void convertAvgPoolArgs(
         int* convArgs,
         int* poolArgs
         )
{
    poolArgs[0]     = convArgs[0];
    poolArgs[1]     = convArgs[1];
    poolArgs[2]     = convArgs[2];
    poolArgs[3]     = convArgs[3];
    poolArgs[4]     = convArgs[50];
    poolArgs[5]     = convArgs[53];
    poolArgs[6]     = convArgs[53];
    poolArgs[7]     = convArgs[47];
    poolArgs[8]     = convArgs[48];
    poolArgs[9]     =  0 ;
    poolArgs[10]    = convArgs[52];
    poolArgs[11]    = (1<<convArgs[57])/(poolArgs[7]*poolArgs[8]);
    poolArgs[12]    = 1;
    poolArgs[13]    = convArgs[54];
    poolArgs[14]    = convArgs[57];
}

//# Checks Dependence of a layer
bool chkDeps(std::vector<bool> &layerDone, std::vector<layerID> &previous)
{
    bool retFlag = true;
    uint16_t nProds = previous.size();
#if ENABLE_CONSOLE_TEXT
    std::cout << "[DEBUG] Previous ID : " << previous[0].seqidx << std::endl;
#endif
    if(previous[0].seqidx == -1)
        return true;
    for(uint16_t prod = 0; prod < nProds; ++prod)
        retFlag &= layerDone[previous[prod].seqidx];
    return retFlag;
}

//# Scheduler for all the layers/tasks in the network in optimal way
//# to the PL or PS
void xiExec(void *handle, vector<void *> input, vector<void *> output)
{
    if(handle == NULL)
    {
        fprintf(stderr, "Failed to read handle\n");
    }

    chaihandle_t *chaihandle_info = (chaihandle*)handle;
    std::vector<xChangeLayer> *hwQueue = chaihandle_info->JobQueue;

    //# Number of layers to be scheduled
    uint16_t totalLayers = hwQueue[0].size();

    //# Number of layers to be scheduled
    if(totalLayers <= 0)
    {
        std::cerr << "\n[ERROR] Invalid Queue size !" << std::endl;
        return;
    }

    /* Assigning user's input and output pointers to scheduler jobqueue */
    if((hwQueue[0][0].kernType == CONV))// && (layer1_or_not == 1))
    {
        hwQueue[0][0].in_ptrs[2] = (IO_DATA_TYPE *)input[0];
    }
    else
    {
        for(int i = 0; i < input.size(); i++)
        {
            hwQueue[0][0].in_ptrs[i] = (IO_DATA_TYPE *)input[i];
        }
    }

    //# Last layer index
    uint16_t lastLayerIdx = totalLayers - 1;

    for(int i = 0; i < output.size(); i++)
    {
        hwQueue[0][lastLayerIdx].out_ptrs[i] = output[i];
	}


	//# Layer-wise Sequence IDs
    std::vector<int> convSeq;
    std::vector<int> poolSeq;
    std::vector<int> deconvSeq;
	std::vector<int> fcSeq;
	std::vector<int> softmaxSeq;
	std::vector<int> nmsSeq;
	std::vector<int> permuteSeq;
	std::vector<int> normSeq;
	std::vector<int> cropSeq;

	std::vector<int> xcustomSeq;
	std::vector<int> xpackSeq;
	std::vector<int> eltwaddSeq;

	//# Initialize layer-wise sequence
	for(uint16_t idx = 0; idx < totalLayers; ++idx)
	{
		kernel_type_e layerType = hwQueue[0][idx].kernType;
                        //* XINHENG TO CHANGE
         //* if type is Conv and from the opcode we can know that  it is a avgpooling.
                if(idx==70)
                {
                        int params[128];
                        for(int i=0;i<128;i++)
                        {
                                params[i]=( (INT_TYPE *)hwQueue[0][idx].params )[i];
                        }
                        int poolParams[32];
                        convertAvgPoolArgs(params,poolParams);
 
                        for(int i=0;i<32;i++)
                        {
                                ( (INT_TYPE *)hwQueue[0][idx].params )[i]=poolParams[i];
                        }
 
                        layerType= POOL;
                }
 
                if(layerType== POOL)
                        setPoolingArgs((INT_TYPE*)hwQueue[0][idx].params,NULL,0,0,0,0);
		switch (layerType) 
		{
        case CONV: convSeq.push_back(idx); break;
        case POOL: poolSeq.push_back(idx); break;
        case DECONV: deconvSeq.push_back(idx); break;
		case FC_LAYER: 	fcSeq.push_back(idx); 		break;
		case SOFTMAX: 	softmaxSeq.push_back(idx); 	break;
		case NORM: 		normSeq.push_back(idx); 	break;
		case NMS: 		nmsSeq.push_back(idx); 		break;
		case PERMUTE: 	permuteSeq.push_back(idx); 	break;
		case CROP: 		cropSeq.push_back(idx); 	break;
		case XCUSTOM:	xcustomSeq.push_back(idx);	break;
		case XPACK: 	xpackSeq.push_back(idx);	break;
		case ELTWISEADD:eltwaddSeq.push_back(idx);	break;
		}
	}

	//# Count of Different layers
	uint16_t tFCLayers		= fcSeq.size();
	uint16_t tSoftMaxLayers = softmaxSeq.size();
	uint16_t tNormLayers	= normSeq.size();
	uint16_t tPermuteLayers = permuteSeq.size();
	uint16_t tNmsLayers		= nmsSeq.size();
	uint16_t tCropLayers	= cropSeq.size();
 #if NEEDED_POOL
    uint16_t tPoolLayers    = poolSeq.size();
#endif

	uint16_t txCustomLayers	= xcustomSeq.size();
	uint16_t txPackLayers	= xpackSeq.size();
	uint16_t tEltwaddLayers	= eltwaddSeq.size();

	std::cout << "[INFOx] Total FC Layers :      " << tFCLayers << std::endl;
	std::cout << "[INFOx] Total Norm Layers :    " << tNormLayers << std::endl;
	std::cout << "[INFOx] Total Permute Layers : " << tPermuteLayers << std::endl;
	std::cout << "[INFOx] Total SoftMax Layers : " << tSoftMaxLayers << std::endl;
	std::cout << "[INFOx] Total NMS Layers :     " << tNmsLayers << std::endl;
	std::cout << "[INFOx] Total Crop Layers :    " << tCropLayers << std::endl;
	std::cout << "[INFOx] Total xCustom Layers : " << txCustomLayers << std::endl;
	std::cout << "[INFOx] Total xPack Layers :   " << txPackLayers << std::endl;
	std::cout << "[INFOx] Total Eltwadd Layers :   " << tEltwaddLayers << std::endl;

	//# Counter for all the layers
	uint16_t fcCnt[1]      = {0},
			softmaxCnt[1] = {0},
			normCnt[1]    = {0},
			nmsCnt[1]     = {0},
			permuteCnt[1] = {0},
			cropCnt[1]    = {0},
			xcustomCnt[1] = {0},
			xpackCnt[1]   = {0},
			eltwaddCnt[1] = {0},
#if NEEDED_POOL
            poolCnt[1] = {0},
#endif
            pipeCnt[1] = {0};

	//# In-use flags
    bool pipeInUse      = false;
#if NEEDED_POOL
    bool poolInUse          = false;
#endif
	bool fcInUse 		= false;
	bool softmaxInUse 	= false;
	bool nmsInUse 		= false;
	bool permuteInUse 	= false;
	bool normInUse 		= false;
	bool cropInUse 		= false;

	bool xcustomInUse 	= false;
	bool xpackInUse 	= false;
	bool eltwaddInUse 	= false;

	bool ImreadInUse	= false;

	//# Image IDs for different layers
    int pipeImgId,
#if NEEDED_POOL
        poolImgId,
#endif
	deconvImgId, fcImgId,
	softmaxImgId, normImgId, permuteImgId, nmsImgId,
	cropImgId,xcustomImgId,xpackImgId,eltwaddImgId;

	//# Done flags for all the layers
	std::vector<bool> layerDone[1];

	//# Reset flags before scheduling
    //# Initialize done flags
    for(uint16_t idx = 0; idx < totalLayers; ++idx)
    {
        layerDone[0].push_back(false);
    }

	uint16_t ImageDoneCount = 0;				//# Number of images completed
	uint16_t ImageDispatchCount = 1;		//# Number of images dispatched
	int ImgId;									//# Image ID for parallel image execution

	//# Software thread & done flags
	pthread_t softmaxThread, normThread, nmsThread, permuteThread, imageReadThread,
	          cropThread, xcustomThread, xpackThread, eltwaddThread;

	uint8_t normThreadDone 		= 0;
	uint8_t nmsThreadDone  		= 0;
	uint8_t softmaxThreadDone	= 0;
	uint8_t permuteThreadDone	= 0;
	uint8_t cropThreadDone 		= 0;

	uint8_t xcustomThreadDone	= 0;
	uint8_t	xpackThreadDone		= 0;
	uint8_t	eltwaddThreadDone	= 0;

	//# Check flags for all individual layers done
    bool allPipeDone,
#if NEEDED_POOL
         allPoolDone,
#endif
	allFCDone, allSoftMaxDone,
	allPermuteDone, allNmsDone, allNormDone,
	allCropDone,allxCustomDone,allxPackDone,allEltwaddDone;

	int totalImages = 1;//total_layers;

	//# Create Crop thread argument structure
	CropThreadArgs cropArgs;
	xCustomThreadArgs xcustomArgs;
	xPackThreadArgs xpackArgs;
	//# Initialize
	cropArgs.cropThreadDone = &cropThreadDone;

	xcustomArgs.xcustomThreadDone = &xcustomThreadDone;
	xpackArgs.xpackThreadDone = &xpackThreadDone;

    //Args array
    std::vector<void* > newArgs;

    int tPipeLayers= 0;
    std::vector<std::vector<void*> > argsToFunction;
    std::vector< std::vector<int> > pipeLayerIds;

#if NEEDED_POOL
    if(convSeq.size() + deconvSeq.size() != 0){
#else
    if(convSeq.size() + poolSeq.size() + deconvSeq.size() != 0){
#endif
    //ParsePipeConvCSV
        tPipeLayers = ParsePipeCSV(newArgs, argsToFunction, hwQueue, pipeLayerIds);
    }
    cout<< "tPipeLayers " << tPipeLayers << endl;

    //Start timer
    long long int totalStart =sds_clock_counter();
    vector<long long int> timeStamp;

#if ENABLE_SCHEDULER
	//# Scheduler Entry Point ################################################
    int i = 0;
	while(1)
	{
#if ENABLE_CONSOLE_TEXT
		std::cout << "[DEBUG] while(1)" << std::endl;
#endif
        if((pipeInUse == false) && tPipeLayers){
#if ENABLE_CONSOLE_TEXT
            std::cout << "[DEBUG] pipeInuse == false " << std::endl;
#endif
            allPipeDone = (pipeCnt[0] == tPipeLayers) ? true : false;
            bool depsDone = true;
            int whichPipe = pipeCnt[0];
            if(!allPipeDone){
            std::vector<int> layers = pipeLayerIds[whichPipe];
            std::vector<int>::iterator itrr = layers.begin();
            for(; itrr != layers.end(); ++itrr){
                std::vector<layerID> ::iterator prevIter = hwQueue[0][*itrr].previous.begin();
                std::vector<layerID> previousOutCurRound = {};
                for(; prevIter != hwQueue[0][*itrr].previous.end(); ++prevIter){
                    if(std::find(layers.begin(), layers.end(), (int)(prevIter->seqidx)) == layers.end()){
                        previousOutCurRound.push_back(*prevIter);
                    }
                }
                if(previousOutCurRound.size() > 0) 
                    depsDone &= chkDeps(layerDone[0],previousOutCurRound);
            }
            }


            if(!allPipeDone && (depsDone)){
                int i = whichPipe;
//INSERT PIPE FUNCTION
                        pipeImgId = 0;
                        pipeInUse = true; 
            }
        } //NEEDED_PIPE

#if NEEDED_POOL
        if((poolInUse == false) && tPoolLayers)
        {
#if ENABLE_CONSOLE_TEXT
            std::cout << "[DEBUG] poolInUse == false " << std::endl;
#endif

            for(ImgId = 0; ImgId < NUM_IMG; ++ImgId)
            {
                allPoolDone = (poolCnt[ImgId] == tPoolLayers) ? true : false;
                uint16_t whichPool = poolSeq[poolCnt[ImgId]];
                if(!allPoolDone && (chkDeps(layerDone[ImgId], hwQueue[ImgId][whichPool].previous)))
                {
#if LAYERWISE_PERFORMANCE
                    hwQueue[ImgId][whichPool].startclk = sds_clock_counter();
#endif
                    //# Call Pool wrapper
                    PoolForward(
                            (SHORT_TYPE*)hwQueue[ImgId][whichPool].in_ptrs[0], (SHORT_TYPE*)hwQueue[ImgId][whichPool].out_ptrs[0],
                            (SHORT_TYPE*)hwQueue[ImgId][whichPool].in_ptrs[1], (SHORT_TYPE*)hwQueue[ImgId][whichPool].out_ptrs[1],
                            (INT_TYPE*)hwQueue[ImgId][whichPool].params
                            );
                    poolImgId = ImgId;
                    poolInUse = true;



#if ENABLE_CONSOLE_TEXT
                    std::cout << "[DEBUG] poolForward : " << poolImgId << std::endl;
#endif
                    break;
                }
            }
#if ENABLE_CONSOLE_TEXT
            std::cout << "quit Pool " << std::endl;
#endif
        }
#endif//NEEDED_POOL

#if NEEDED_FC
        if((fcInUse == false) && tFCLayers)
        {
            int ImgId = 0;
            uint16_t fcCount = fcCnt[ImgId];

            allFCDone = (fcCount == tFCLayers) ? true : false;
            uint16_t whichFc = fcSeq[fcCount];
            if(!allFCDone && (chkDeps(layerDone[ImgId], hwQueue[ImgId][whichFc].previous)))
            {
#if LAYERWISE_PERFORMANCE
                hwQueue[ImgId][whichFc].startclk = sds_clock_counter();
#endif 
                //# Call FC wrapper
                SwFcForward(
                        (IO_DATA_TYPE*)hwQueue[0][whichFc].in_ptrs[0],
                        (IO_DATA_TYPE*)hwQueue[0][whichFc].in_ptrs[1],
                        (SW_FC_DATA_TYPE *)hwQueue[0][whichFc].in_ptrs[2],
                        (SW_FC_DATA_TYPE *)hwQueue[0][whichFc].wts_ptrs[0],
                        (SW_FC_DATA_TYPE *)hwQueue[0][whichFc].bias_ptr,
                        (SW_FC_DATA_TYPE *)hwQueue[0][whichFc].out_ptrs[0],
                        (INT_TYPE *)hwQueue[0][whichFc].params
                        );

                fcImgId = ImgId; 
                fcInUse = true; 
            }
        }
#endif//NEEDED_FC

#if NEEDED_NORM
		if((normInUse == false) && tNormLayers)
		{
#if ENABLE_CONSOLE_TEXT
			std::cout << "[DEBUG] normInUse == false " << std::endl;
#endif
            int ImgId = 0;
            allNormDone = (normCnt[ImgId] == tNormLayers) ? true : false;
            uint16_t whichNorm = normSeq[normCnt[ImgId]];
            if(!allNormDone && (chkDeps(layerDone[ImgId], hwQueue[ImgId][whichNorm].previous)))
            {
#if PTHREAD
                pthread_create(&normThread, NULL, normRoutine, (void *)&hwQueue[ImgId][whichNorm]);
#else
                normRoutine((void *)&hwQueue[ImgId][whichNorm]);
#endif
                normImgId = ImgId; 
                normInUse = true;
            }
        }
#endif//NEEDED_NORM

#if NEEDED_PERMUTE	
        if((permuteInUse == false) && tPermuteLayers)
        {
            int ImgId = 0;
            allPermuteDone = (permuteCnt[ImgId] == tPermuteLayers) ? true : false;
            uint16_t whichPermute = permuteSeq[permuteCnt[ImgId]];
            if(!allPermuteDone && (chkDeps(layerDone[ImgId], hwQueue[ImgId][whichPermute].previous)))
            {
#if LAYERWISE_PERFORMANCE
                hwQueue[ImgId][whichPermute].startclk = sds_clock_counter();
#endif

#if PTHREAD
                pthread_create(&permuteThread, NULL, permuteRoutine, (void *)&hwQueue[ImgId][whichPermute]);
#else
                permuteRoutine((void *)&hwQueue[ImgId][whichPermute]);
#endif

                permuteImgId = ImgId; 
                permuteInUse = true;
            }
        }
#endif//NEEDED_PERMUTE

#if NEEDED_SOFTMAX
        if((softmaxInUse == false) && tSoftMaxLayers)
        {
            int ImgId = 0; 
            allSoftMaxDone = (softmaxCnt[ImgId] == tSoftMaxLayers) ? true : false;
            uint16_t whichSoftmax = softmaxSeq[softmaxCnt[ImgId]];
            if(!allSoftMaxDone && (chkDeps(layerDone[ImgId], hwQueue[ImgId][whichSoftmax].previous)))
            {
#if LAYERWISE_PERFORMANCE
                hwQueue[ImgId][whichSoftmax].startclk = sds_clock_counter();
#endif					
                //# Call SoftMax wrapper
#if PTHREAD
                pthread_create(&softmaxThread, NULL, softmaxRoutine, (void *)&hwQueue[ImgId][whichSoftmax]);
#else
                softmaxRoutine((void *)&hwQueue[ImgId][whichSoftmax]);
#endif
                softmaxImgId = ImgId;
                softmaxInUse = true;
#if ENABLE_CONSOLE_TEXT
                std::cout << "[DEBUG] softmaxForward : " << softmaxImgId << ", " << allSoftMaxDone << std::endl;
#endif
            }
        }
#endif//NEEDED_SOFTMAX

#if NEEDED_NMS
        if((nmsInUse == false) && tNmsLayers)
        {
            int ImgId = 0; 
            allNmsDone = (nmsCnt[ImgId] == tNmsLayers) ? true : false;
            uint16_t whichNms = nmsSeq[nmsCnt[ImgId]];
            if(!allNmsDone && (chkDeps(layerDone[ImgId], hwQueue[ImgId][whichNms].previous)))
            {
#if LAYERWISE_PERFORMANCE
                hwQueue[ImgId][whichNms].startclk = sds_clock_counter();
#endif

#if PTHREAD
                pthread_create(&nmsThread, NULL, nmsRoutine, (void *)&hwQueue[ImgId][whichNms]);
#else
                nmsRoutine((void *)&hwQueue[ImgId][whichNms]);
#endif
                nmsImgId = ImgId;
                nmsInUse = true;
            }
        }
#endif//NEEDED_NMS

#if NEEDED_CROP
		if((cropInUse == false) && tCropLayers)
		{
            int ImgId = 0; 
            allCropDone = (cropCnt[ImgId] == tCropLayers) ? true : false;
            //# Get the Crop layer ID
            uint16_t whichCrop = cropSeq[cropCnt[ImgId]];
            //# Check dependencies are satisfied or not
            if(!allCropDone && (chkDeps(layerDone[ImgId], hwQueue[ImgId][whichCrop].previous)))
            {
                //# Call Crop layer
                //std::cout << "\n\n[DEBUG] Calling Thread : Crop" << std::endl;
                cropArgs.Layer = &hwQueue[ImgId][whichCrop];
                pthread_create(&cropThread, NULL, cropRoutine, &cropArgs);
                //std::cout << "\n\n[DEBUG] Calling Thread : Crop : Done" << std::endl;
                cropImgId = ImgId; 
                cropInUse = true; 
            }
		}
#endif//NEEDED_CROP

#if NEEDED_XCUSTOM
		if((xcustomInUse == false) && txCustomLayers)
		{
            int ImgId = 0;
            allxCustomDone = (xcustomCnt[ImgId] == txCustomLayers) ? true : false;
            //# Get the Custom layer ID
            uint16_t whichxcustom = xcustomSeq[xcustomCnt[ImgId]];
            //# Check dependencies are satisfied or not
            if(!allxCustomDone && (chkDeps(layerDone[ImgId], hwQueue[ImgId][whichxcustom].previous)))
            {

                xcustomArgs.Layer = &hwQueue[ImgId][whichxcustom];

                //xcustomRoutine(&xcustomArgs);
                pthread_create(&xcustomThread, NULL, xcustomRoutine, &xcustomArgs);
                //std::cout << "\n\n[DEBUG] Calling Thread : Custom : Done" << std::endl;
                xcustomImgId = ImgId;
                xcustomInUse = true;
            }
		}
#endif//NEEDED_XCUSTOM

#if NEEDED_XPACK
		if((xpackInUse == false) && txPackLayers)
		{
            int ImgId = 0;
            allxPackDone = (xpackCnt[ImgId] == txPackLayers) ? true : false;
            //# Get the Pack layer ID
            uint16_t whichxpack = xpackSeq[xpackCnt[ImgId]];
            //# Check dependencies are satisfied or not
            if(!allxPackDone && (chkDeps(layerDone[ImgId], hwQueue[ImgId][whichxpack].previous)))
            {
                //# Call Pack layer
                //std::cout << "\n\n[DEBUG] Calling Thread : Pack" << std::endl;
                xpackArgs.Layer = &hwQueue[ImgId][whichxpack];
                pthread_create(&xpackThread, NULL, xpackRoutine, &xpackArgs);
                //std::cout << "\n\n[DEBUG] Calling Thread : Pack : Done" << std::endl;
                xpackImgId = ImgId;
                xpackInUse = true;
            }
        }
#endif//NEEDED_XPACK

//#######################################################################################//

		if(pipeInUse == true)
		{
			//# wait for pipe to be completed
//#ifdef __SDSOC
//			sds_wait(1);
//#endif
            if(sds_try_wait(1)){
                pipeInUse = false;
                int whichPipe = pipeCnt[0];
                std::vector<int> layers = pipeLayerIds[whichPipe];
                std::vector<int>::iterator itrr = layers.begin();
                for(; itrr != layers.end(); ++itrr){
                    layerDone[pipeImgId][*itrr] = true;
                }
                pipeCnt[pipeImgId]++;
            }
		}  //NEEDED_PIPE

#if NEEDED_POOL
        if(poolInUse == true)
        {

            if(sds_try_wait(2))
            {

                unsigned long long int end=sds_clock_counter();
                timeStamp.push_back(end);

#if ENABLE_CONSOLE_TEXT
                std::cout << "[DEBUG] poolForward : Done : Image : " << poolImgId << " Layer : " << poolCnt[poolImgId] << std::endl;
#endif
#if ENABLE_ERROR_CHECKS
                if(poolImgId == 0)
                {
                    int poolErr = errorCheck(hwQueue[poolImgId][poolSeq[poolCnt[poolImgId]]]);
                    if(poolErr)
                        std::cout << "\n[ERROR] Pool Layer : " << poolSeq[poolCnt[poolImgId]] << " Image : " << poolImgId << " Fail !" << std::endl;
                    else
                        std::cout << "\n[ERROR] Pool Layer : " << poolSeq[poolCnt[poolImgId]] << " Image : " << poolImgId << " Pass !" << std::endl;
                }
#endif

#if LAYERWISE_PERFORMANCE
                hwQueue[poolImgId][poolSeq[poolCnt[poolImgId]]].endclk = sds_clock_counter();
#endif

                layerDone[poolImgId][poolSeq[poolCnt[poolImgId]]] = true;
                poolCnt[poolImgId]++;
                poolInUse = false;
            }
        }


#endif//NEEDED_POOL

#if NEEDED_FC
        if(fcInUse == true)
		{
#ifdef __SDSOC
			if(1)//sds_try_wait(3))
#else
				if(1)
#endif
				{
#if ENABLE_ERROR_CHECKS
					if(fcImgId == 0){
						int fcErr = errorCheck(hwQueue[fcImgId][fcSeq[fcCnt[fcImgId]]]);
						if(fcErr)
							std::cout << "\n[ERROR] FC Layer : " << fcSeq[fcCnt[fcImgId]] << " Image : " << fcImgId << " Fail !" << std::endl;
						else
							std::cout << "\n[ERROR] FC Layer : " << fcSeq[fcCnt[fcImgId]] << " Image : " << fcImgId << " Pass !" << std::endl;
					}
#endif
#if LAYERWISE_PERFORMANCE
			hwQueue[fcImgId][fcSeq[fcCnt[fcImgId]]].endclk = sds_clock_counter();
#endif
					layerDone[fcImgId][fcSeq[fcCnt[fcImgId]]] = true;
					fcCnt[fcImgId]++;
					fcInUse = false;
				}
				else
				{
					fcInUse = true;
				}
		}
#endif//NEEDED_FC

#if NEEDED_NORM
		if(normInUse == true)
		{
			uint16_t whichNorm = normSeq[normCnt[normImgId]];
			normThreadDone = hwQueue[normImgId][whichNorm].layer_done[0];

			//# Check for thread completion
			if(normThreadDone)
			{
#if PTHREAD
				int normRet = pthread_join(normThread, NULL);
#else
				int normRet = 0;
#endif

#if ENABLE_CONSOLE_TEXT
				if(normRet != 0)
				{ std::cerr << "\n[ERROR] normThread Fail ! " << "Image : " << normImgId << ", Layer ID : " << normSeq[normCnt[normImgId]] << std::endl; }
				else
				{ std::cout << "** normForward : Done" << std::endl; }
#endif
				hwQueue[normImgId][whichNorm].layer_done[0] = 0;
				normThreadDone = 0;

#if ENABLE_ERROR_CHECKS
				if(normImgId == 0){
					int normErr = errorCheck(hwQueue[normImgId][whichNorm]);
					if(normErr)
						std::cout << "\n[ERROR] Norm Layer : " << whichNorm << " Image : " << normImgId << " Fail !" << std::endl;
					else
						std::cout << "\n[ERROR] Norm Layer : " << whichNorm << " Image : " << normImgId << " Pass !" << std::endl;
				}
#endif

#if LAYERWISE_PERFORMANCE
			hwQueue[normImgId][whichNorm].endclk = sds_clock_counter();
#endif
				layerDone[normImgId][normSeq[normCnt[normImgId]]] = true;
				normCnt[normImgId]++; 
				normInUse = false;
			}
		}
#endif//NEEDED_NORM

#if NEEDED_PERMUTE
		if(permuteInUse == true)
		{
			uint16_t whichPermute = permuteSeq[permuteCnt[permuteImgId]];
			permuteThreadDone = hwQueue[permuteImgId][whichPermute].layer_done[0];

			//# Check for thread completion
			if(permuteThreadDone)
			{
#if PTHREAD
				int permuteRet = pthread_join(permuteThread, NULL);
#else
				int permuteRet = 0;
#endif

#if ENABLE_CONSOLE_TEXT
				if(permuteRet != 0)
				{ std::cerr << "\n[ERROR] permuteThread Fail ! " << "Image : " << permuteImgId << ", Layer ID : " << permuteSeq[permuteCnt[permuteImgId]] << std::endl; }
				else
				{ std::cout << "** permuteForward : Done" << std::endl; }
#endif
				hwQueue[permuteImgId][whichPermute].layer_done[0] = 0;
				permuteThreadDone = 0;

#if ENABLE_ERROR_CHECKS
				if(permuteImgId == 0){
					int permuteErr = errorCheck(hwQueue[permuteImgId][whichPermute]);
					if(permuteErr)
						std::cout << "\n[ERROR] Permute Layer : " << whichPermute << " Image : " << permuteImgId << " Fail !" << std::endl;
					else
						std::cout << "\n[ERROR] Permute Layer : " << whichPermute << " Image : " << permuteImgId << " Pass !" << std::endl;
				}
#endif
#if LAYERWISE_PERFORMANCE
			hwQueue[permuteImgId][whichPermute].endclk = sds_clock_counter();
#endif
				layerDone[permuteImgId][permuteSeq[permuteCnt[permuteImgId]]] = true;
				permuteCnt[permuteImgId]++; 
				permuteInUse = false;
			}
		}
#endif//NEEDED_PERMUTE

#if NEEDED_SOFTMAX
		if(softmaxInUse == true)
		{
			uint16_t whichSoftmax = softmaxSeq[softmaxCnt[softmaxImgId]];
			softmaxThreadDone = hwQueue[softmaxImgId][whichSoftmax].layer_done[0];

			//# Check for thread completion
			if(softmaxThreadDone)
			{
#if PTHREAD
				int softmaxRet = pthread_join(softmaxThread, NULL);
#else
				int softmaxRet = 0;
#endif

#if ENABLE_CONSOLE_TEXT
				if(softmaxRet != 0)
				{ std::cerr << "\n[ERROR] softmaxThread Fail ! " << "Image : " << softmaxImgId << ", Layer ID : " << softmaxSeq[softmaxCnt[softmaxImgId]] << std::endl; }
				else
				{ std::cout << "** softmaxForward : Done" << std::endl; }
#endif
				hwQueue[softmaxImgId][whichSoftmax].layer_done[0] = 0;
				softmaxThreadDone = 0;

#if ENABLE_ERROR_CHECKS
				if(softmaxImgId == 0){
					int softmaxErr = errorCheck(hwQueue[softmaxImgId][whichSoftmax]);
					if(softmaxErr)
						std::cout << "\n[ERROR] Softmax Layer : " << whichSoftmax << " Image : " << softmaxImgId << " Fail !" << std::endl;
					else
						std::cout << "\n[ERROR] Softmax Layer : " << whichSoftmax << " Image : " << softmaxImgId << " Pass !" << std::endl;
				}
#endif
#if LAYERWISE_PERFORMANCE
			hwQueue[softmaxImgId][whichSoftmax].endclk = sds_clock_counter();
#endif
				layerDone[softmaxImgId][softmaxSeq[softmaxCnt[softmaxImgId]]] = true;
				softmaxCnt[softmaxImgId]++;
				softmaxInUse = false;
			}
		}
#endif//NEEDED_SOFTMAX

#if NEEDED_NMS
		if(nmsInUse == true)
		{
			uint16_t whichNms = nmsSeq[nmsCnt[nmsImgId]];
			nmsThreadDone = hwQueue[nmsImgId][whichNms].layer_done[0];

			//# Check for thread completion
			if(nmsThreadDone)
			{
#if PTHREAD
				int nmsRet = pthread_join(nmsThread, NULL);
#else
				int nmsRet = 0;
#endif

#if ENABLE_CONSOLE_TEXT
				if(nmsRet != 0)
				{ std::cerr << "\n[ERROR] nmsThread Fail ! " << "Image : " << nmsImgId << ", Layer ID : " << nmsSeq[nmsCnt[nmsImgId]] << std::endl; }
				else
				{ std::cout << "** nmsForward : Done" << std::endl; }
#endif
				hwQueue[nmsImgId][whichNms].layer_done[0] = 0;
				nmsThreadDone = 0;

#if ENABLE_ERROR_CHECKS
				if(nmsImgId == 0){
					int nmsErr = errorCheck(hwQueue[nmsImgId][whichNms]);
					if(nmsErr)
						std::cout << "\n[ERROR] Nms Layer : " << whichNms << " Image : " << nmsImgId << " Fail !" << std::endl;
					else
						std::cout << "\n[ERROR] Nms Layer : " << whichNms << " Image : " << nmsImgId << " Pass !" << std::endl;
				}
#endif

#if LAYERWISE_PERFORMANCE
			hwQueue[nmsImgId][whichNms].endclk = sds_clock_counter();
#endif

				layerDone[nmsImgId][nmsSeq[nmsCnt[nmsImgId]]] = true;
				nmsCnt[nmsImgId]++;
				nmsInUse = false;
			}
		}
#endif//NEEDED_NMS

#if NEEDED_CROP
		if(cropInUse == true)
		{
			//# Check for thread completion
			if(cropThreadDone)
			{
				//# Join thread
				int cropRet = pthread_join(cropThread, NULL);
				if(cropRet != 0)
				{ std::cerr << "\n[ERROR] cropThread Fail ! " << "Image : " << cropImgId << ", Layer ID : " << cropSeq[cropCnt[cropImgId]] << std::endl; }
#if ENABLE_ERROR_CHECKS
				if(cropImgId == 0){
					uint16_t whichCrop = cropSeq[cropCnt[cropImgId]];
					int cropErr = errorCheck(hwQueue[cropImgId][whichCrop]);
					if(cropErr)
						std::cout << "\n[ERROR] Crop Layer : " << whichCrop << " Image : " << cropImgId << " Fail !" << std::endl;
					else
						std::cout << "\n[ERROR] Crop Layer : " << whichCrop << " Image : " << cropImgId << " Pass !" << std::endl;
				}
#endif
				cropThreadDone = 0;
#if LAYERWISE_PERFORMANCE
			hwQueue[cropImgId][cropSeq[cropCnt[cropImgId]]].endclk = sds_clock_counter();
#endif				
				layerDone[cropImgId][cropSeq[cropCnt[cropImgId]]] = true;
				cropCnt[cropImgId]++; 
				cropInUse = false;
			}
		}
#endif//NEEDED_CROP

#if NEEDED_XCUSTOM
		if(xcustomInUse == true)
		{
			//# Check for thread completion
			if(xcustomThreadDone)
			{
				//# Join thread
				int xcustomRet = pthread_join(xcustomThread, NULL);
				if(xcustomRet != 0)
				{ std::cerr << "\n[ERROR] xcustomThread Fail ! " << "Image : " << xcustomImgId << ", Layer ID : " << xcustomSeq[xcustomCnt[xcustomImgId]] << std::endl; }
#if ENABLE_ERROR_CHECKS
				if(cropImgId == 0){
					uint16_t whichxcustom = xcustomSeq[xcustomCnt[xcustomImgId]];
					int cropErr = errorCheck(hwQueue[xcustomImgId][whichxcustom]);
					if(cropErr)
						std::cout << "\n[ERROR] xcustom Layer : " << whichxcustom << " Image : " << xcustomImgId << " Fail !" << std::endl;
					else
						std::cout << "\n[ERROR] xcustom Layer : " << whichxcustom << " Image : " << xcustomImgId << " Pass !" << std::endl;
				}
#endif
				xcustomThreadDone = 0;
#if LAYERWISE_PERFORMANCE
			hwQueue[xcustomImgId][xcustomSeq[xcustomCnt[xcustomImgId]]].endclk = sds_clock_counter();
#endif				
				layerDone[xcustomImgId][xcustomSeq[xcustomCnt[xcustomImgId]]] = true;
				xcustomCnt[xcustomImgId]++;
				xcustomInUse = false;
			}
		}
#endif//NEEDED_XCUSTOM

#if NEEDED_XPACK
		if(xpackInUse == true)
		{
			//# Check for thread completion
			if(xpackThreadDone)
			{
				//# Join thread
				int xpackRet = pthread_join(xpackThread, NULL);
				if(xpackRet != 0)
				{ std::cerr << "\n[ERROR] xpackThread Fail ! " << "Image : " << xpackImgId << ", Layer ID : " << xpackSeq[xpackCnt[xpackImgId]] << std::endl; }
				xpackThreadDone = 0;
				layerDone[xpackImgId][xpackSeq[xpackCnt[xpackImgId]]] = true;
				xpackCnt[xpackImgId]++;
				xpackInUse = false;
			}
		}
#endif//NEEDED_XPACK

#if RESET_DONE_FLAGS
		//# Check Last Layer : Done ?
		if(layerDone[0][lastLayerIdx] == true)
		{
			++ImageDoneCount;
			std::cout << "\n[DEBUG] Image Done Count : " << ImageDoneCount << std::endl;
			//# Re-initialize done flags
			for(uint16_t idx = 0; idx < totalLayers; ++idx)
			{
				layerDone[0][idx] = false;
			}
			fcCnt[0] = 0; softmaxCnt[0] = 0; 
			normCnt[0] = 0; nmsCnt[0] = 0;
			permuteCnt[0] = 0; cropCnt[0] = 0; eltwaddCnt[0] = 0;
		}
#endif//RESET_DONE_FLAGS

		//# Break scheduler loop based on number of images
		if(ImageDoneCount == totalImages)
			break;

	}//# while(1) ############################################################ 
    long long int freQ = sds_clock_frequency();
    float pipetime=0;
    float pipeStart,pipeEnd;

    bool pipeflag=0;
    float pooltime=0;
    float poolStart,poolEnd;
    bool poolflag=0;
    for(int i=0;i<timeStamp.size();i++)
    {

        float mid_time = (((double)(timeStamp[i] - totalStart)/(double)freQ*1000));

        std::cout.width(0);

        std::cout<< "timeStamp"<<mid_time <<std::endl;
    }

#endif//ENABLE_SCHEDULER

    //release arg memory
    releaseArgMems(newArgs);
    //releaseDummyMems(dummyPtrs, dummyPtrIdx);

	return;
}
