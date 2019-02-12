from resourceEstimation import resource_estimate_batch

ibufferArray=[1024, 2048, 4096, 8192]
obufferArray=[1024, 2048]
wbufferArray=[1024, 2048]
kersize = [8,16]
procsize = [8, 16,32]
fileTitle = ["ID", "TYPE", "BRAM", "DSP", "FF", "LUT", "XI_KER_PROC", "XI_PIX_PROC", "XI_IBUFF_DEPTH", "XI_OBUFF_DEPTH", "XI_WEIGHTBUFF_DEPTH"]
writeList =[fileTitle]

idx = 0

#For Convolution
for ibuffersize in ibufferArray:
    for obuffersize in obufferArray:
        for wbuffersize in wbufferArray:
            for ker in kersize:
                for proc in procsize:
                    idx += 1
                    ID = "IP"+ str(idx)
                    brams, dsps = resource_estimate_batch(ibuffersize, obuffersize, wbuffersize, ker, proc)
                    BRAM = str(int(brams) + 18 + 18 *(ker > 16))
                    DSP = str(int(dsps))
                    #FIXME: FF, LUT are fake
                    FF = LUT = str(1000)
                    writeList.append([ID, "Convolution", BRAM, str(int(DSP)), FF, LUT, str(ker), str(proc), str(ibuffersize), str(obuffersize), str(wbuffersize)])

#For Conolution_g
for ibuffersize in ibufferArray:
    for obuffersize in obufferArray:
        for wbuffersize in wbufferArray:
            for ker in kersize:
                for proc in procsize:
                    idx += 1
                    ID = "IP"+ str(idx)
                    brams, dsps = resource_estimate_batch(ibuffersize, obuffersize, wbuffersize, ker, proc)
                    BRAM = str(int(brams) + 18 + 18 *(ker > 16))
                    DSP = str(int(dsps))
                    #FIXME: FF, LUT are fake
                    FF = LUT = str(1000)
                    writeList.append([ID, "Convolution_g", str(int(BRAM)*2), str(int(DSP)*2), str(int(FF) * 2), str(int(LUT) * 2), str(ker), str(proc), str(ibuffersize), str(obuffersize), str(wbuffersize)])

fw = open("IP_config_w", 'w')
for l in writeList:
    fw.write(", ".join(l) + "\n")

#For pooling
l = ["IP"+str(idx+1), "Pooling", "51", "21", "6004", "4872", "1", "7533",  "1", "1", "1"]
fw.write(", ".join(l) + "\n")

#For Eltwise
l = ["IP"+str(idx+2), "Eltwise", "51", "21", "6004", "4872", "1", "7533",  "1", "1", "1"]
fw.write(", ".join(l) + "\n")
fw.close()


