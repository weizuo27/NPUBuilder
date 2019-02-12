
def dispatcherDeclare( fileName, infoList):
    """
    infoList: list of tuple ( streamName, layerType)
            example:
            listINFO=[ ("S0","Convolution"), ("S1","Convolution"),("S2","Convolution"), ("S3","Pooling"),("S4","Mux"),("S5","Mux")];

    return: string of function declaration and defintion of dispatcher
    """
    cmd="void dispatcher(\n"
    cmd+="\tint* argsMem,\n"

    readlength=0;
    offsetlist=[0]

    f = open(fileName, "a")

    for i in range( len(infoList)):
        [streamName, layerType]=infoList[i]
        cmd+="\thls::stream< int > & "+streamName+",\n"
        print layerType
        if(layerType=="Convolution" or layerType=="Convolution_g"):
            readlength+=128;  
        elif(layerType=="Pooling"):
            readlength+=32;
        elif("MUX" in layerType):
            readlength+=2
        elif(layerType=="Divider" or layerType=="Combiner"):
            readlength+=3;
        elif(layerType=="Eltwise"):
            readlength+=8;
        else:
            print "ILLEGAL LAYER NAME!";
            return "ILLEGAL LAYER NAME!\n";
    
        offsetlist.append(readlength);
    cmd = cmd[:-2]
    cmd+=")\n{\n"
    cmd+="\tint argsBuff[1024];\n"

    cmd+= "\tfor(int i = 0; i < " + str(readlength) + "; i++)\n"
    cmd+="\t{\n"  
    cmd+="\t#pragma HLS pipeline\n"
    cmd+="\t\targsBuff[i]=argsMem[i];\n"
    cmd+="\t}\n"

    for i in range( len(infoList)):
        [streamName, layerType]=infoList[i]
        cmd+="\tfor(int i ="+str(offsetlist[i])+";i<"+str(offsetlist[i+1])+";i++)\n"
        cmd+="\t{\n"  
        cmd+="\t\t"+streamName+"<<argsBuff[i];\n"
        cmd+="\t}\n"
    cmd+="}\n"
    f.write(cmd)
    f.close()


def dispatcherCall( fileName, memName, infoList ):
    """
    memName: the name of memory port where dispatcher read arguments
    infoList: list of tuple ( streamName, layerType)
            example:
            listINFO=[ ("S0","Convolution"), ("S1","Convolution"),("S2","Convolution"), ("S3","Pooling"),("S4","Mux"),("S5","Mux")];

    return: string of function call of dispatcher
    """
    f = open(fileName, "a")
    cmd="\t\tdispatcher(\n"
    cmd+="\t\t"+memName+",\n"

    for i in range( len(infoList)):
        [streamName, layerType]=infoList[i]
        cmd+="\t\t\t"+streamName+",\n"
    cmd = cmd[:-2]
    cmd+=");\n"
    cmd += "#ifdef __CSIM___\n"
    cmd += "goto LABEL_DISPATCHER_NEXT;\n"
    cmd += "#endif\n"
    f.write(cmd)
    f.close()

#listINFO=[ ("S0","Convolution"), ("S1","Convolution"),("S2","Convolution"), ("S3","Pooling"),("S4","Mux"),("S5","Mux")];
#
#dispatcherDeclare(listINFO);
#
#dispatcherCall("memory",listINFO );
    
    

    


