from gurobipy import *

import numpy


def updateCombineCounter(counter,counterNum ):
    idx=0;
    while(1):
        if( idx == len(counterNum) ): return True;
        counter[idx]+=1;
        if(counter[idx]==counterNum[idx]):
            counter[idx]=0;
            idx+=1;
        else:
            break;
    return False


def rowStepILP(
    BRAMbudget,
    IB_nij, # numpy array
    OB_nij, # numpy array
    L_ij,
    N,
    I,
    J
):

    m=Model(name="SomeModel")
    m.setParam( 'OutputFlag', False )
    X_ij=[]
    expr=LinExpr();
    for i in range(0,I):
        X_j=[]
        for j in range(0,J):
            x=m.addVar(vtype=GRB.BINARY, name="X_"+str(i)+"_"+str(j) );
            X_j.append(x);
            expr.addTerms(L_ij[i][j],x)
        X_ij.append(X_j);
    m.setObjective(expr, GRB.MINIMIZE)
    m.update()
    #add constraint for any i, Sum_i(X_ij)=1
    for i in range(0,I):
        expr=LinExpr();
        for j in range(0,J):
            expr.add(X_ij[i][j]);
        m.addConstr(expr == 1);
    m.update()

    IBmax_n=[]
    OBmax_n=[]
    for n in range(N):
        ib=m.addVar(vtype=GRB.CONTINUOUS, name="IBmax_"+str(n) );
        ob=m.addVar(vtype=GRB.CONTINUOUS, name="OBmax_"+str(n) );
        # m.addConstr( ib >=0)
        # m.addConstr( ob >=0)
        m.addConstr(  ib <= numpy.max(IB_nij[n]))
        m.addConstr(  ob <= numpy.max(OB_nij[n]))
        IBmax_n.append(ib);
        OBmax_n.append(ob);
    m.update()
    for n in range(N):
        for i in range(I):
            expr=LinExpr();
            for j in range(J):
                expr.addTerms(IB_nij[n][i][j],X_ij[i][j])
            m.addConstr(expr <=IBmax_n[n]); 
            expr=LinExpr();   
            for j in range(J):
                expr.addTerms(OB_nij[n][i][j],X_ij[i][j])
            m.addConstr(expr <=OBmax_n[n]);           
    m.update()
    expr=LinExpr();
    for n in range(N):
        expr.add(OBmax_n[n]);
        expr.add(IBmax_n[n]);
    m.addConstr(expr <=BRAMbudget); 
    m.update()
    m.optimize()

    if m.status == GRB.Status.INFEASIBLE:
        m.write("file.lp")
        return None,None,None,None

    rowStepChoice=[0]*I;
    IB=[0]*N
    OB=[0]*N
    InIdx=[[0,0]]*N
    OutIdx=[[0,0]]*N

    for i in range(I):
        idx=0;
        for j in range(0,J):
            if(X_ij[i][j].X !=0):
                idx=j;
                rowStepChoice[i]=idx+1;
        for n in range(N):
            if IB_nij[n][i][idx]>IB[n]: 
                IB[n]=IB_nij[n][i][idx]; 
                InIdx[n]=[i,idx];
            if OB_nij[n][i][idx]>OB[n]: 
                OB[n]=OB_nij[n][i][idx]; 
                OutIdx[n]=[i,idx];
    
   

    m.write("file.lp")
    return rowStepChoice,InIdx,OutIdx,m.objVal







N=2
I=8
P=5
   
# numpy.random.seed(seed=)
IB_nij=numpy.random.rand(N,I,P)
OB_nij=numpy.random.rand(N,I,P)
L_ij=numpy.random.rand(I,P)

rowStepILP(5.5,IB_nij,OB_nij,L_ij,N,I,P)