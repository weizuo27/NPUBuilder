import os
import sys
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path + "/../DSE");
from IP import IP
class MUX(IP):
    idx = 0
    def __init__(self, type_, in_degree, out_degree):
        name = "MUX"+ str(MUX.idx)
        IP.__init__(self, name, type_, None, None, None) 
#        self.args = []
        MUX.idx += 1
        self.in_degree = in_degree
        self.out_degree = out_degree

class Combiner(IP):
    idx = 0
    def __init__(self):
        name = "Combiner"+str(Combiner.idx)
        type_ = "Combiner"
        IP.__init__(self, name, type_, None, None, None)
        Combiner.idx += 1

class Divider(IP):
    idx = 0
    def __init__(self):
        name = "Divider"+str(Divider.idx)
        type_ = "Divider"
        IP.__init__(self, name, type_, None, None, None)
        Divider.idx += 1
