#ifndef _UTILS_WEI_HPP_
#define _UTILS_WEI_HPP_

#include <string>
#include <vector>
#include "xi_scheduler.hpp"
#include <sstream>

using namespace std;


void setArgs(
        const string ipType, 
        vector<int> params, 
        std::vector<xChangeLayer> *hwQueue, 
        std::vector<void*>& argumentstoFunction, 
        std::vector<void*> & newArgs);

void releaseArgMems(std::vector<void*> newArgs);
std::string tostring(int Number);

template<typename T>
void load_file(const char* filename, void *arr, size_t count);
#endif

