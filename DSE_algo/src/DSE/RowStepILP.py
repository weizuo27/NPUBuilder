from gurobipy import *
import numpy



index=0;
def RowStepILP(
    IB_gsrkn,    
    OB_gsrkn,  
    L_gsrk,  
    B,  
    ConvIPnum):

    Y_gs=[]
    X_gsrk=[]
    IB_n=[]
    IB_gsrn=[]
    OB_n=[]
    OB_gsrn=[]
        
    m=Model(name="SomeModel")
    m.setParam( 'OutputFlag', False )

    for g in range(len(L_gsrk)):
        Y_s=[];
        X_s=[]
        for s in range( len(L_gsrk[g]) ):
            y=m.addVar(vtype=GRB.BINARY, name="Y_"+str(g)+"_"+str(s) );
            Y_s.append(y);
            X_r=[]
            for r in  range(len( L_gsrk[g][s]) ):
                X_k=[]
                for k in range(len( L_gsrk[g][s][r]) ):
                    x=m.addVar(vtype=GRB.BINARY, name="X_"+str(g)+"_"+str(s)+"_"+str(r)+"_"+str(k));
                    X_k.append(x);
                X_r.append(X_k);
            X_s.append(X_r);
        Y_gs.append(Y_s)
        X_gsrk.append(X_s)
        
    for n in range(ConvIPnum):
        ib=m.addVar(vtype=GRB.INTEGER, name="IB_"+str(n) )
        IB_n.append(ib)
        ob=m.addVar(vtype=GRB.INTEGER, name="OB_"+str(n) )
        OB_n.append(ob)

    for g in range(len(L_gsrk)):
        I_g=[]
        O_g=[]
        for s in range( len(L_gsrk[g]) ):
            I_s=[]
            O_s=[]
            for r in  range(len( L_gsrk[g][s]) ):
                I_r=[]
                O_r=[]
                for n in range(ConvIPnum):
                    i=m.addVar(vtype=GRB.INTEGER, name="IB_"+str(g)+"_"+str(s)+"_"+str(r)+"_"+str(n) )
                    o=m.addVar(vtype=GRB.INTEGER, name="OB_"+str(g)+"_"+str(s)+"_"+str(r)+"_"+str(n) )
                    I_r.append(i)
                    O_r.append(o)
                I_s.append(I_r)
                O_s.append(O_r)
            I_g.append(I_s)
            O_g.append(O_s)
        IB_gsrn.append(I_g)
        OB_gsrn.append(O_g)

    m.update()

    for Y_g in Y_gs:
        expr=LinExpr();
        for s in Y_g:
            expr.add(s);
        m.addConstr(expr == 1);
    
    m.update()

    for g,X_g in enumerate(X_gsrk):
        for s,X_s in enumerate(X_g):
            for r in X_s:
                expr=LinExpr();
                for k in r:
                    expr.add(k)
                m.addConstr(expr == Y_gs[g][s]);
    m.update()

    for g,X_g in enumerate(X_gsrk):
        for s,X_s in enumerate(X_g):
            for r,X_r in enumerate(X_s):
                for n in range(ConvIPnum):
                    exprI=LinExpr();
                    exprO=LinExpr();
                    for k,X_k in enumerate(X_r):
                        exprI.addTerms(IB_gsrkn[g][s][r][k][n],X_k)
                        exprO.addTerms(OB_gsrkn[g][s][r][k][n],X_k)
                    m.addConstr(IB_gsrn[g][s][r][n]==exprI );
                    m.addConstr(OB_gsrn[g][s][r][n]==exprO );
    m.update()
    IB_flatten=[]
    OB_flatten=[]
    for n in range(ConvIPnum): 
        IB_flatten_n=[]
        OB_flatten_n=[]
        for g,I_g in enumerate(IB_gsrn):
            for s,I_s in enumerate(I_g):
                for r,I_r in enumerate(I_s):
                    IB_flatten_n.append(IB_gsrn[g][s][r][n]);
                    OB_flatten_n.append(OB_gsrn[g][s][r][n]);
        IB_flatten.append(IB_flatten_n)
        OB_flatten.append(OB_flatten_n)          
                
    m.update()

    # for n in range(ConvIPnum):
    #     for i in IB_flatten[n]:
    #         m.addConstr(IB_n[n]>= i );
    #     for i in OB_flatten[n]:
    #         m.addConstr(OB_n[n]>= i );


    for n in range(ConvIPnum):
        m.addConstr(IB_n[n]==max_(IB_flatten[n]) );
        m.addConstr(OB_n[n]==max_(OB_flatten[n]) );
    m.update()    

    expr=LinExpr();
    
    for n in range(ConvIPnum):
        expr.add( IB_n[n] )
        expr.add( OB_n[n] )
    m.addConstr(expr <= B)
    m.update()

    expr=LinExpr();
    for g,X_g in enumerate(X_gsrk):
        for s,X_s in enumerate(X_g):
            for r,X_r in enumerate(X_s):
                for k,X_k in enumerate(X_r):
                    expr.addTerms(L_gsrk[g][s][r][k],X_gsrk[g][s][r][k])

    m.setObjective(expr, GRB.MINIMIZE)
    
    m.update()
    m.optimize()
    global index

    m.write("ILP"+str(index)+".lp")

    print "SOlution "+str(index)
    index+=1

    if m.status == GRB.Status.INFEASIBLE:
        return None,None,None,None

    solutionChoice=[]

    for g,Y_g in enumerate(Y_gs):
        count=0;
        solutionIdx=None
        for s,Y_s in enumerate(Y_g):
            if Y_s.X==1:
                count+=1;
                rowStepList=[]
                for r,x_r in enumerate( X_gsrk[g][s] ):
                    for k,x_k in enumerate(x_r):
                        if x_k.X == 1:
                            rowStepList.append(k+1);
                solutionChoice.append( (s,rowStepList) )

        if count != 1:
            print "Group "+str(g) +"have illegeal solution"


    IBrst=[]
    OBrst=[]

    for n in range(ConvIPnum):
        IBrst.append(IB_n[n].X)
        OBrst.append(OB_n[n].X)
    

    return IBrst,OBrst,solutionChoice,m.objVal
    
