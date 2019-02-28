#include "stdlib.h"
#include <sstream>
#include "stdio.h"
#include <fstream>
#include <iostream>
#include <unordered_map>
#include "csvParser.hpp"
using namespace std;

int stringToInt(string in){
    stringstream ss(in);
    int ret = 0;
    ss >> ret;
    return ret;
}

int ParsePipeCSV(
        std::vector<void* > &newArgs, 
        std::vector< std::vector<void*> > & argsToFunction, 
        const std::vector<xChangeLayer> *hwQueue, 
        std::vector< int > & layerIds
        ){
    //Following should be configed
    //Key: The IP type. Value: The number of columns

    int rounds = 0;
    unordered_map<string, int> IPs;

    IPs["Convolution"] = 12;
    IPs["Pooling"] = 8;
//    IPs["Convolution_g"] = 9+8;
    IPs["Convolution_g"] = 12;
    IPs["Args"] = 2;

    fstream fs;
    fs.open("round2.csv");
    string line;

    while(getline(fs, line)){
        rounds += 1;
        istringstream ss(line);
        string col;
        vector<string> rowList;

        while(getline(ss, col, ',')){
            rowList.push_back(col);
        }

        std::vector<void*> args;

        vector<string>::iterator itr = rowList.begin();
        for(; itr!=rowList.end(); ++itr){
            if(IPs.find(*itr) == IPs.end())
                continue;
            cout << "type " << *itr << " index " << IPs[*itr] << "\n";
            vector<int> params ;

            int index = IPs[*itr];
            string ipType = *itr;
            for(int i = 0; i < index; ++i){
                itr ++;
                params.push_back(stringToInt(*itr));
            }

            setArgs(ipType, params, hwQueue, args, newArgs, layerIds);
        }
        cout << "length " << args.size() << endl;
        argsToFunction.push_back(args);
    }
    fs.close();
    return rounds;
}
