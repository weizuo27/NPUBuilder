class MUX:
    idx = 0
    def __init__(self, type_, in_degree, out_degree):
        self.name = "MUX"+ str(MUX.idx)
        MUX.idx += 1
        self.type = type_
        self.in_degree = in_degree
        self.out_degree = out_degree
