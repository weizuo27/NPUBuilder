from math import ceil
def resource_estimate(iBufferSize, oBufferSize, wBufferSizei, ker_proc, pix_proc):
    inBrams = ceil(iBufferSize/1024.0) * 8 * 2 * ceil(32.0/18)
    outBrams = ceil(oBufferSize/1024.0) * 8 * ceil(72.0/18) * 2
    wBrams = ceil(wBufferSizei / 1024.0) * ker_proc * ceil(32.0/18) * 2
    feedingBrams = ceil(32.0/18) * pix_proc/2 * 2
    resulting = ker_proc * 2 * 2
    bias_scale = 24
    brams = inBrams + outBrams + wBrams + feedingBrams + resulting + bias_scale
    #This is given my the linear regression
    dsps = int(round(1 * ker_proc*pix_proc + 3.33928571*pix_proc + 22))
    return brams, dsps

def resource_estimate_batch(iBufferSize, oBufferSize, wBufferSizei, ker_proc, pix_proc):
    #need validation
    inBrams = 2*ceil(iBufferSize/1024.0) * 8 * 2 * ceil(32.0/18)
    outBrams = 2*ceil(oBufferSize/1024.0) * 8 * ceil(72.0/18) * 2
    wBrams = ceil(wBufferSizei / 1024.0) * ker_proc * ceil(32.0/18) * 2
    feedingBrams = 2*ceil(32.0/18) * pix_proc/2 * 2
    resulting = 2*ker_proc * 2 * 2
    bias_scale = 24
    brams = inBrams + outBrams + wBrams + feedingBrams + resulting + bias_scale
    #This is given my the linear regression
    dsps = int(round(1 * ker_proc*pix_proc*2 + 3.33928571*pix_proc + 22))
    return brams, dsps


def resource_estimate_conv_g_batch(iBufferSize, oBufferSize, wBufferSizei, ker_proc, pix_proc):
    #need validation
    inBrams = 2*ceil(iBufferSize*2/1024.0) * 8 * 2 * ceil(32.0/18)
    outBrams = 2*ceil(oBufferSize*2/1024.0) * 8 * ceil(72.0/18) * 2
    wBrams = ceil(wBufferSizei / 1024.0) * ker_proc * ceil(32.0/18) * 2
    feedingBrams = 2*ceil(32.0/18) * pix_proc/2 * 2
    resulting = 2*ker_proc * 2 * 2
    bias_scale = 24
    brams = inBrams + outBrams + wBrams + feedingBrams + resulting + bias_scale
    #This is given my the linear regression
    dsps = int(round(1 * ker_proc*pix_proc*2 + 3.33928571*pix_proc + 22))
    return brams, dsps


print resource_estimate_batch(2048,1024,1024,16,32)
