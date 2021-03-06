#ifndef _UTILS_WEI_HPP_
#define _UTILS_WEI_HPP_

#include <string>
#include <vector>
#include "xi_scheduler.hpp"
#include <sstream>

using namespace std;


void setArgs(
        const string ipType, 
        const vector<int> params, 
        const std::vector<xChangeLayer> *hwQueue, 
        std::vector<void*>& argumentstoFunction, 
        std::vector<void*> & newArgs, 
        std::vector< int > & layerIds
        );

void releaseArgMems(std::vector<void*> newArgs);
std::string tostring(int Number);

template<typename T>
void load_file(const char* filename, void *arr, size_t count);
#endif

