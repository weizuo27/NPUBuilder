This document describes how to use find_best_rowStep.py

Input: file pipelinedInfo.csv at same folder as find_best_rowStep.py
file content:
each line describes a round call, the line format is described below:
[RoundIdx][IsPipeline][layerInfo1][layerInfo2] ... [layerInfoN] ["END"]
Different items should be divided by comma( ,)

RoundIdx, the round index
IsPipeline, whether in the current round, all the layer are in a one-line pipeline. If not, the model shall directly choose the max rowStep.
layer Package info is specified in online excel


following is an example
4,1,Convolution,1,0,14,14,14,14,256,256,1,3,3,1,0,4,0,54,16,32,1024,1,Convolution,0,0,14,14,14,14,1024,256,1,1,1,0,0,4,0,51,8,32,1024,4,57,END

Output is rowStep.csv with the format of [layerID][optimal rowStep] in each line