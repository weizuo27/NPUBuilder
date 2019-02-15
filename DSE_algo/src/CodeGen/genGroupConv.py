

def genGroupConv(
    infoDict
):
    """
        input infoDict:
        the Dict input should contain following information if required
        IPName={IPName}: the IPname, for example "IP78"
        IPArgs={IPArgs0,IPArgs1}: the IPname, for example "IP78"
        HasMemIn={M_in_0, M_in_1, ... M_in_3}: the input mem port name, split into 2 part for group0 and group1
        HasMemOut = {...}, the Output mem port name, split into 2 part for group0 and group1
        HasStreamIn ={Stream ports}.  The stream in ports to dividor
        HasStreamOut = {streamPorts}. The stream out ports to COmbiner
        Weights = {w0, w1,  ...w7} the weight port name, split into 2 part for group0 and group1
        HasDiv = {DivArgName}
        HasComb = {CombArgName}
    """

    ipName=(infoDict['IPName'])[0];

    divToConvStream="\thls::stream< ap_uint<128> > divTo"+ipName+"Group0;\n"+\
            "\thls::stream< ap_uint<128> > divTo"+ipName+"Group0;\n"

    divToConvStreamdeclare= "\thls::stream< ap_uint<128> > divTo"+ipName+"Group0A;\n"+\
                            "\thls::stream< ap_uint<128> > divTo"+ipName+"Group0B;\n"+\
                            "\thls::stream< ap_uint<128> > divTo"+ipName+"Group1A;\n"+\
                            "\thls::stream< ap_uint<128> > divTo"+ipName+"Group1B;\n";
    

    convToCombStreamDeclare= "\thls::stream< ap_uint<128> > "+ipName+"toCombGroup0A;\n"+\
                            "\thls::stream< ap_uint<128> > "+ipName+"toCombGroup0B;\n"+\
                            "\thls::stream< ap_uint<128> > "+ipName+"toCombGroup1A;\n"+\
                            "\thls::stream< ap_uint<128> > "+ipName+"toCombGroup1B;\n";


    streamDeclare=""        

    if( 'HasDiv' in infoDict and 'HasStreamIn' in infoDict ):
        streamDeclare+=divToConvStreamdeclare;
    if( 'HasComb' in infoDict and 'HasStreamOut' in infoDict ):
        streamDeclare+=convToCombStreamDeclare;

    divCall=""
    if( 'HasDiv' in infoDict and 'HasStreamIn' in infoDict ):

        divCall+="\tdivider(\n\t\t"
        divCall+=infoDict["HasDiv"][0]+",\n\t\t"
        divCall+=infoDict["HasStreamIn"][0]+",\n\t\t"
        divCall+=infoDict["HasStreamIn"][1]+",\n\t\t"
        divCall+="divTo"+ipName+"Group0A,\n\t\t"+\
                    "divTo"+ipName+"Group0B,\n\t\t"+\
                    "divTo"+ipName+"Group1A,\n\t\t"+\
                    "divTo"+ipName+"Group1B\n\t";
        divCall+=");\n"

    ipCallGroup0=""
    ipCallGroup1=""

    ipCallGroup0+="\t"+ipName+"::Convolution(\n\t\t"
    ipCallGroup1+="\t"+ipName+"::Convolution(\n\t\t"
    
    # ipCallGroup1+=infoDict["IPArgs"][1]+",\n\t\t"  
    if( "HasMemIn" in infoDict):
        ipCallGroup0+=infoDict["HasMemIn"][0]+",\n\t\t"
        ipCallGroup0+=infoDict["HasMemIn"][1]+",\n\t\t"
        ipCallGroup1+=infoDict["HasMemIn"][2]+",\n\t\t"
        ipCallGroup1+=infoDict["HasMemIn"][3]+",\n\t\t"

    if( "HasMemOut" in infoDict):
        ipCallGroup0+=infoDict["HasMemOut"][0]+",\n\t\t"
        ipCallGroup0+=infoDict["HasMemOut"][1]+",\n\t\t"
        ipCallGroup1+=infoDict["HasMemOut"][2]+",\n\t\t"
        ipCallGroup1+=infoDict["HasMemOut"][3]+",\n\t\t"

    if( "HasStreamIn" in infoDict):
        ipCallGroup0+="divTo"+ipName+"Group0A,\n\t\t"                        
        ipCallGroup0+="divTo"+ipName+"Group0B,\n\t\t"
        ipCallGroup1+="divTo"+ipName+"Group1A,\n\t\t"                        
        ipCallGroup1+="divTo"+ipName+"Group1B,\n\t\t"
    
    if( "HasStreamOut" in infoDict):
        ipCallGroup0+=ipName+"toCombGroup0A,\n\t\t"                        
        ipCallGroup0+=ipName+"toCombGroup0B,\n\t\t"
        ipCallGroup1+=ipName+"toCombGroup1A,\n\t\t"                        
        ipCallGroup1+=ipName+"toCombGroup1A,\n\t\t"
    
    if( "Weights" in infoDict):
        if(len( infoDict["Weights"]) == 4):
            ipCallGroup0+=infoDict["Weights"][0]+",\n\t\t"
            ipCallGroup0+=infoDict["Weights"][1]+",\n\t\t"
            ipCallGroup0+=infoDict["IPArgs"][0]+"\n\t\t"
            ipCallGroup0+="\n#ifdef __SDSVHLS__ \n\t\t, ap_clk_div2\n#else\n\t\t, 0\n#endif\n\t\t"
            ipCallGroup1+=infoDict["Weights"][2]+",\n\t\t"
            ipCallGroup1+=infoDict["Weights"][3]+",\n\t\t"
            ipCallGroup1+="\n#ifdef __SDSVHLS__ \n\t\t, ap_clk_div2\n#else\n\t\t, 0\n#endif\n\t\t"   
        else:
            ipCallGroup0+=infoDict["Weights"][0]+",\n\t\t"
            ipCallGroup0+=infoDict["Weights"][1]+",\n\t\t"
            ipCallGroup0+=infoDict["Weights"][2]+",\n\t\t"
            ipCallGroup0+=infoDict["Weights"][3]+",\n\t\t"
            ipCallGroup0+=infoDict["IPArgs"][0]+"\n\t\t"
            ipCallGroup0+="\n#ifdef __SDSVHLS__ \n\t\t, ap_clk_div2\n#else\n\t\t, 0\n#endif\n\t\t"
            ipCallGroup1+=infoDict["Weights"][4]+",\n\t\t"
            ipCallGroup1+=infoDict["Weights"][5]+",\n\t\t"
            ipCallGroup1+=infoDict["Weights"][6]+",\n\t\t"
            ipCallGroup1+=infoDict["Weights"][7]+",\n\t\t"
            ipCallGroup1+=infoDict["IPArgs"][1]+"\n\t\t"
            ipCallGroup1+="\n#ifdef __SDSVHLS__ \n\t\t, ap_clk_div2\n#else\n\t\t, 0\n#endif\n\t\t"

    ipCallGroup0+="\t);\n"
    ipCallGroup1+="\t);\n"
    
    combCall=""
    if( 'HasComb' in infoDict and 'HasStreamOut' in infoDict ):
    
        combCall+="\tcombiner(\n\t\t"
        combCall+=infoDict["HasComb"][0]+",\n\t\t"
        combCall+=infoDict["HasStreamOut"][0]+",\n\t\t"
        combCall+=infoDict["HasStreamOut"][1]+",\n\t\t"
        combCall+=  ipName+"toCombGroup0A,\n\t\t"+\
                    ipName+"toCombGroup0B,\n\t\t"+\
                    ipName+"toCombGroup1A,\n\t\t"+\
                    ipName+"toCombGroup1B\n\t";
        combCall+=");\n"
    
    return streamDeclare+divCall+ipCallGroup0+ipCallGroup1+combCall
            

if __name__ == '__main__':
    groupDict={'IPName':["PI78"], \
        'IPArgs':['IPArgs0','IPArgs1'],\
        'HasMemIn':['M_in_0', 'M_in_1', 'M_in_2','M_in_3'],\
        'HasStreamIn':['s0','s1'],\
        'HasStreamOut':['s2','s3'],\
        'Weights':['w0', 'w1','w2', 'w3'],\
        'HasDiv':['DivArgs'],\
        'HasComb':['CombArgs']}


    string2=genGroupConv(groupDict)
    print string2
