def readRunctionArgs():
    f_wrapper = open("pipeSystemTemp.cpp", 'r')
    functionArgs = list()
    for l in f_wrapper:
       functionArgs.append(l.strip().split(","))
    f_wrapper.close()

    return functionArgs

def genSchedulerFile(functionArgs):
    f_scheduler = open('schedulerTmp.cpp', 'r')
    f_w_scheduler = open('./softwareFiles/xi_scheduler.cpp', 'w')

    for l in f_scheduler:
        if l != "//INSERT PIPE FUNCTION\n":
            f_w_scheduler.write(l)
        else:
            f_w_scheduler.write("\t\tPipeForward(\n")
            for i in range(len(functionArgs) - 1):
                f_w_scheduler.write("\t\t\targsToFunction[i]["+str(i)+"],\n")

            f_w_scheduler.write("\t\t\targsToFunction[i]["+str(i+1)+"]\n")
            f_w_scheduler.write("\t\t);\n")

    f_scheduler.close()
    f_w_scheduler.close()

def genXkernelH(functionArgs):
    f_r = open("kernelsTemp.h", "r")
    f_w = open("./softwareFiles/xi_kernels.h", "w")
    for l in f_r:
        if l != "//INSERT PIPE FUNCTION\n":
            f_w.write(l)
        else:
            length = len(functionArgs) - 1
            #generate PipeForward
            idx = 0
            f_w.write("void PipeForward(\n")
            for t, v in functionArgs:
                if idx == length:
                    break
                f_w.write("\tvoid* " + str(v)+",\n")
                idx += 1
            f_w.write("\tvoid* "+str(functionArgs[idx][1])+"\n")
            f_w.write(");\n")

    f_r.close()
    f_w.close()

def genXkernelCPP(functionArgs):
    f_r = open("kernelsTemp.cpp", "r")
    f_w = open("./softwareFiles/xi_kernels.cpp", "w")

    for l in f_r:
        if l != "//INSERT PIPE FUNCTION\n":
            f_w.write(l)
        else:
            #generate ConvolutionPipeWrapper
            f_w.write("int ConvolutionPipeWrapper(")
            idx = 0
            length = len(functionArgs) - 1
            for t,v in functionArgs:
                if idx == length:
                    break
                f_w.write("\t"+str(t)+" " + str(v)+",\n")
                idx += 1
            print "idx", idx, len(functionArgs)
            f_w.write("\t"+str(functionArgs[idx][0])+" " + str(functionArgs[idx][1])+"\n")
            f_w.write(");\n")

            #generate PipeForward
            idx = 0
            f_w.write("void PipeForward(\n")
            for t, v in functionArgs:
                if idx == length:
                    break
                f_w.write("\tvoid* " + str(v)+",\n")
                idx += 1
            f_w.write("\tvoid* "+str(functionArgs[idx][1])+"\n")
            f_w.write("){\n")
            f_w.write("\tlong long int start =sds_clock_counter();\n\
    long long int frequency = sds_clock_frequency();\n")
            f_w.write("\tConvolutionPipeWrapper(\n")
            idx = 0
            for t, v in functionArgs:
                if idx == length:
                    break
                f_w.write("\t\t(" + str(t) + ") " + str(v)+",\n")
                idx += 1

            f_w.write("\t\t("+str(functionArgs[idx][0])+") "+str(functionArgs[idx][1])+"\n")
            f_w.write(");\n")
            f_w.write("\tsds_wait(1);\n")
            f_w.write("\tlong long int end =sds_clock_counter();\n"\
                    "\tfloat mid_time = (((double)(end - start)/(double)frequency*1000));\n"\
                    "\tstd::cout<<\"hardware layer time:\"<<mid_time<<endl;\n")
            f_w.write("}\n")


    f_r.close()
    f_w.close()
    
functionArgs = readRunctionArgs()
genSchedulerFile(functionArgs)
genXkernelH(functionArgs)
genXkernelCPP(functionArgs)
