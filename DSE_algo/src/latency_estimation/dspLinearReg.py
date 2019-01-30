import matplotlib.pyplot as plt
import numpy as np


def getKerPixDSPs(fileName):
    Kers = []
    Pixs = []
    DSPs = []

    f = open(fileName, "r")
    next(f)
    for l in f:
        l = l.replace(" ","").strip().split(",")
        Kers.append(int(l[0]))
        Pixs.append(int(l[1]))
        DSPs.append(int(l[3]))
    f.close()

    Kers_np = np.array(Kers)
    Pixs_np = np.array(Pixs)
    DSPs_np = np.array(DSPs)

    A = np.vstack([np.multiply(Kers_np, Pixs_np), Pixs_np, np.ones(len(Kers_np))]).T
    m = np.linalg.lstsq(A, DSPs_np)

    DSP_est = np.matmul(A, m[0])
    print DSP_est
    print m

getKerPixDSPs("IP_config_w")
