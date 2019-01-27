from codeGen import *

def drawGraph(g, mapping):
    h = nx.relabel_nodes(g, mapping)
    nx.draw(h, with_labels=True, font_weight = 'bold')
    plt.show()

g = nx.DiGraph()

ipDDR = ip("DDR", "DDR")
ipA = ip("A", "Convolution")
ipB = ip("B", "Convolution")
ipC = ip("C", "Convolution")
ipD = ip("D", "Convolution")

mapping = dict()

mapping[ipA] =  "A"
mapping[ipB] = "B"
mapping[ipC] = "C"
mapping[ipD] = "D"
mapping[ipDDR] = "DDR"

#g.add_nodes_from(["DDR", "A", "B", "C", "D"]);
#g.add_edges_from([ ("DDR", "A"), ("B", "DDR"), ("C", "DDR"), ("D", "DDR"),
#        ("A", "B"), ("A", "D"), ("D", "B"), ("B", "C"), ("C", "D")])

g.add_nodes_from([ipDDR, ipA, ipB, ipC, ipD])
g.add_edges_from([(ipDDR, ipA), (ipB, ipDDR), (ipC, ipDDR), (ipD, ipDDR), 
        (ipA, ipB), (ipA, ipD), (ipD, ipB), (ipB, ipC), (ipC, ipD)])

#g.add_nodes_from(["A", "B", "C", "D"]);
#g.add_edges_from([("A", "B"), ("A", "D"), ("D", "B"), ("B", "C"), ("C", "D")])

expandGraph(g)
assignStreamPorts(g, 2, 2, 2) #FIXME Hardcode 2??
genTop(g)


#drawGraph(g, mapping)
