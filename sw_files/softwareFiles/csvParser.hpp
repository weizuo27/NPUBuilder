#ifndef _CSVPARSER_H_
#define _CSVPARSER_H_

#include "utils_wei.hpp"
#include <vector>

int ParsePipeCSV(
        std::vector<void* > &newArgs, 
        std::vector< std::vector<void*> > & argsToFunction, 
        const std::vector<xChangeLayer> *hwQueue, 
        std::vector< int > & layerIds
        );
#endif
