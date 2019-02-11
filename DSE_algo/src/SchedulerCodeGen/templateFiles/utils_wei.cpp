#include "utils_wei.hpp"

std::string tostring(int Number)
{
    std::ostringstream ss;
    ss << Number;
    return ss.str();
}

void setArgs(
        const string ipType, 
        const vector<int> params, 
        const std::vector<xChangeLayer> *hwQueue, 
        std::vector<void*>& argumentstoFunction, 
        std::vector<void*> & newArgs, 
        std::vector< int > & layerIds
        ){

    int imageId = 0;

    //genArguments
    if(ipType == "Args"){
        int length = params[1];
        int roundIdx = params[0];
        int* newArg =  (int*)sds_alloc_non_cacheable(length * sizeof(char));
        load_file<char>(("args/args_"+tostring(roundIdx)).c_str(), (void*)newArg, length);
        newArgs.push_back((void*)newArg);
        argumentstoFunction.push_back(newArg);
    }
    
    //Convolution
    if(ipType == "Convolution"){
        int layerId = params[11];
        bool idle = (params[0] == 1);
        bool stream_in = (params[1] == 1);
        bool stream_out = (params[2] == 1);

        if(not idle){
            layerIds.push_back(layerId);
        }

        //The inputs
        int inMemIdx = 2 * (params[5] == 1);
        for(int i = 0; i < inMemIdx; ++i){
            if(idle){
                int *newArg = (int*)sds_alloc_non_cacheable(1 * sizeof(char));
                newArgs.push_back((void*)newArg);
                argumentstoFunction.push_back(newArg);
            }
            else{
                argumentstoFunction.push_back(hwQueue[imageId][layerId].in_ptrs[i]);
            }
        }

        //The outputs
        int outMemIdx = 2*(params[4] == 1);
        for(int i = 0; i < outMemIdx; ++i){
            if(idle){
                int *newArg = (int*)sds_alloc_non_cacheable(1 * sizeof(char));
                newArgs.push_back((void*)newArg);
                argumentstoFunction.push_back(newArg);
            }
            else{
                argumentstoFunction.push_back(hwQueue[imageId][layerId].out_ptrs[i]);
            }
        }

        //The weights
        int weightIdx = 2 + 2*(params[3] == 1); //FIXME: Verify with XH

        for(int i = 0; i < weightIdx; ++i){
            int *newArg;
            if(idle){
                newArg = (int*)sds_alloc_non_cacheable(1 * sizeof(char));
            }
            else{
                int weightlen = params[i+7];
                newArg = (int*)sds_alloc_non_cacheable(weightlen * sizeof(char));
                load_file<char>(("weight/weight_"+tostring(layerId)+"_"+tostring(i+1)).c_str(), (void*)newArg, weightlen);
            }
            newArgs.push_back((void*)newArg);
            argumentstoFunction.push_back(newArg);
        }


        //1st inputs
        if(params[6] == 1){
            if(idle){
                int *newArg = (int*)sds_alloc_non_cacheable(1 * sizeof(char));
                newArgs.push_back((void*)newArg);
                argumentstoFunction.push_back(newArg);
            }
            else
                argumentstoFunction.push_back(hwQueue[imageId][layerId].in_ptrs[2]);
        }
    }
    else if(ipType == "Pooling"){
        int layerId = params[7];

        bool idle = (params[0] == 1);
        bool bypass = false;
        int* prev_args = NULL;
        bool stream_in =(params[2]);
        bool stream_out = (params[3]);

        if(not idle){
            layerIds.push_back(layerId);
        }

        //input
        if(params[4] == 1){
            if(idle){
                int *newArg = (int*)sds_alloc_non_cacheable(1 * sizeof(char));
                newArgs.push_back((void*)newArg);
                argumentstoFunction.push_back(newArg);

                newArg = (int*)sds_alloc_non_cacheable(1 * sizeof(char));
                newArgs.push_back((void*)newArg);
                argumentstoFunction.push_back(newArg);
            }
            else{
                argumentstoFunction.push_back(hwQueue[imageId][layerId].in_ptrs[0]);
                argumentstoFunction.push_back(hwQueue[imageId][layerId].in_ptrs[1]);
            }
        }
        //Output
        if(params[5] == 1){
            if(idle){
                int *newArg = (int*)sds_alloc_non_cacheable(1 * sizeof(char));
                newArgs.push_back((void*)newArg);
                argumentstoFunction.push_back(newArg);

                newArg = (int*)sds_alloc_non_cacheable(1 * sizeof(char));
                newArgs.push_back((void*)newArg);
                argumentstoFunction.push_back(newArg);
            }
            else{
                argumentstoFunction.push_back(hwQueue[imageId][layerId].out_ptrs[0]);
                argumentstoFunction.push_back(hwQueue[imageId][layerId].out_ptrs[1]);
            }
        }
    }

    else if(ipType == "Convolution_g"){
        int layerId = params[15];
        bool idle = (params[0] == 1);
        bool stream_in = (params[1] == 1);
        bool stream_out = (params[2] == 1);
        int groupNums = params[16];

        if(not idle){
            layerIds.push_back(layerId);
        }

        int weightIdx = 2 + 2*(params[3] == 1); //FIXME: Verify with XH
        for (int j = 0; j < groupNums; ++j){
            //The inputs
            int inMemIdx = 2 * (params[5] == 1);
            for(int i = 0; i < inMemIdx; ++i){
                if(idle){
                    int *newArg = (int*)sds_alloc_non_cacheable(1 * sizeof(char));
                    newArgs.push_back((void*)newArg);
                    argumentstoFunction.push_back(newArg);
                }
                else{
                    argumentstoFunction.push_back(hwQueue[imageId][layerId].in_ptrs[i]);
                }
            }

            //The outputs
            int outMemIdx = 2*(params[4] == 1);
            for(int i = 0; i < outMemIdx; ++i){
                if(idle){
                    int *newArg = (int*)sds_alloc_non_cacheable(1 * sizeof(char));
                    newArgs.push_back((void*)newArg);
                    argumentstoFunction.push_back(newArg);
                }
                else{
                    argumentstoFunction.push_back(hwQueue[imageId][layerId].out_ptrs[i]);
                }
            }

            //The weights
            for(int i = 0; i < weightIdx; ++i){
                int *newArg;
                if(idle){
                    newArg = (int*)sds_alloc_non_cacheable(1 * sizeof(char));
                }
                else{
                    int weightlen = params[i+7+j*4];
                    newArg = (int*)sds_alloc_non_cacheable(weightlen * sizeof(char));
                    load_file<char>(("weight/weight_"+tostring(layerId)+"_"\
                                +tostring(j) + "_" +tostring(i+1)).c_str(), (void*)newArg, weightlen);
                }
                newArgs.push_back((void*)newArg);
                argumentstoFunction.push_back(newArg);
            }


            //1st inputs
            if(params[6] == 1){
                if(idle){
                    int *newArg = (int*)sds_alloc_non_cacheable(1 * sizeof(char));
                    newArgs.push_back((void*)newArg);
                    argumentstoFunction.push_back(newArg);
                }
                else
                    argumentstoFunction.push_back(hwQueue[imageId][layerId].in_ptrs[2]);
            }
        }
    }
    cout << "number of args " << argumentstoFunction.size() << "\n";
    return;
}

void releaseArgMems(std::vector<void*> newArgs){
    std::vector<void*>::iterator itr = newArgs.begin();
    for(; itr != newArgs.end(); ++itr){
        sds_free(*itr);
    }
}

template<typename T>
void load_file(const char* filename, void *arr, size_t count){
    printf("load %s\n", filename);
    FILE* fd = fopen(filename, "r");
    if(fd==NULL) { 
        printf("%s not found\n", filename);
        return;
    }
    int a = fread(arr, sizeof(T), count, fd);
    printf("%d bytes are loaded\n", a);

    fclose(fd);
}


