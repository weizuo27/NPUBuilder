from gurobipy import *


def roundScheduling(
    depencyPairSet, # a list of tuple [i,j] specifying depedency relationship, with 
    noStreamEle,
    loneLayerDeps,
    loneLayer,
    loneLayerArray,
    loneLayerlatencyList,
    layerType,
    layerArray,
    layerPerIPlatencyList,
    ConvIPnum,
    PoolIPnum,
    EleIPnum,
    MaxRound
):

    m=Model("roundScheduling");
    m.setParam( 'OutputFlag', False )
    X_irn=[]
    layerNum= len(layerPerIPlatencyList);
    loneLayerNum=len(loneLayer);
    M_r=[]
    MI_ir=[]
    Y_ir=[]
    #Add variable X_irn
    for i in range( layerNum):
        X_rn=[]
        for r in range(MaxRound):
            X_n=[]
            for n in range(len( layerPerIPlatencyList[i]) ):
                x=m.addVar(vtype=GRB.BINARY,name="X_"+str(i)+"_"+str(r)+"_"+str(n));
                X_n.append(x);
            X_rn.append(X_n);
        X_irn.append(X_rn);
    m.update();


    for i in range( loneLayerNum):
        Y_r=[]
        for r in range(MaxRound):
            x=m.addVar(vtype=GRB.BINARY,name="Y_"+str(i)+"_"+str(r));
            Y_r.append(x);
        Y_ir.append(Y_r);
    m.update()



    for i in range(loneLayerNum):
        MI_r=[]
        for r in range(MaxRound):
            x=m.addVar(vtype=GRB.INTEGER,name="MI_"+str(i)+"_"+str(r));
            MI_r.append(x);
        MI_ir.append()
    m.update();

    for r in range( MaxRound):
        x=m.addVar(vtype=GRB.INTEGER,name="M_"+str(r));
        M_r.append(x);
    m.update();


    # all the layer can only be scheduled once with I ip
    for layersChoice in X_irn:
        expr=LinExpr();
        for roundsChoice in layersChoice:
            for IPchoice in roundsChoice:
                expr.add(IPchoice);
        m.addConstr(expr == 1);  
    m.update();



#layer dependency constraint
    for pair in loneLayerDeps:
        i,j = pair;
        exprJ=LinExpr();
        for r in range(MaxRound):
            for n in range( len(X_irn[j][r]) ):
                exprJ.addTerms(r,X_irn[j][r][n]);
        for r in range(MaxRound):
            m.addConstr(r*Y_ir[i][r] < exprJ);
    m.update();


    for pair in depencyPairSet:
        i,j = pair;
        exprI=LinExpr();
        exprJ=LinExpr();
        for r in range(MaxRound):
            for n in range( len(X_irn[i][r]) ):
                exprI.addTerms(r,X_irn[i][r][n]);
            for n in range( len(X_irn[j][r]) ):
                exprJ.addTerms(r,X_irn[j][r][n]);
        m.addConstr(exprI <= exprJ);
    m.update();

    for r in range(MaxRound):
        expConvIP=[]
        for i in range(ConvIPnum):
            expr=LinExpr();
            expConvIP.append(expr)
        expPoolIP=[]
        for i in range(PoolIPnum):
            expr=LinExpr();
            expPoolIP.append(expr)
        expEleIP=[]
        for i in range(EleIPnum):
            expr=LinExpr();
            expEleIP.append(expr)
        
        for i in range( layerNum ):
            for n,var in enumerate(X_irn[i][r]):
                if layerType[i]=="Convolution":
                    expConvIP[n].add(var);
                if layerType[i]=="Pooling":
                    expPoolIP[n].add(var);
                if layerType[i]=="Eltwise":
                    expEleIP[n].add(var);
        for expr in expConvIP:
            m.addConstr(expr <= 1)
        for expr in expPoolIP:
            m.addConstr(expr <= 1)
        for expr in expEleIP:
            m.addConstr(expr <= 1)
    m.update();
    

    #add constraint to that 
    for pair in noStreamEle:
        i,j = pair;
        for r in range(MaxRound):
            exprI=LinExpr();
            exprJ=LinExpr();
            for n in range( len(X_irn[i][r]) ):
                exprI.add(X_irn[i][r][n]);
            for n in range( len(X_irn[j][r]) ):
                exprJ.add(X_irn[j][r][n]);
            m.addConstr(exprI + exprJ <=1);
    m.update();



    #Aconstraint of latency of each round
    for r in range(MaxRound):
        for i in range(layerNum):
            expr=LinExpr();
            for n in range( len( layerPerIPlatencyList[i] ) ):
                expr.addTerms(layerPerIPlatencyList[i][n][1], X_irn[i][r][n]);
            m.addConstr(expr <= M_r[r]);
    expr=LinExpr();
    m.update();
    

    BC=100000000
    for i in range(loneLayerNum):
        expr=LinExpr();
        for r in range(MaxRound):
            expr.addTerms(1, MI_ir[i]);
        m.addConstr( expr <=loneLayerLatencyList[i][r];) 


    for r in range(MaxRound):
        expr.add(M_r[r])
    m.update();
    m.setObjective(expr,GRB.MINIMIZE);
    m.update();
    m.write("out.lp")
    m.optimize();

    roundMapping=[]
    roundDict={}
    roundIdx=0;
    for r in range(MaxRound):
        layerMapping=[]
        for i in range(layerNum):
            for n,var in enumerate(X_irn[i][r]):
                if var.X:
                    layerMapping.append( (roundIdx,layerArray[i],layerPerIPlatencyList[i][n][0]) );
                    roundDict[i]=roundIdx
        if layerMapping:
            roundMapping.append(layerMapping)
            roundIdx+=1;
            
    

    return roundMapping,roundDict,m.objVal;

        
            
# depSet= [[0,1],[1,4],[2,3],[3,4]]
# nostream=[[3,4]]

# layerType=["Convolution","Convolution", "Pooling","Convolution","ELtwise"];



# layerPerIPlatencyList=[ [338688,677376], [940800,1881600], [802816], [602112,1204224],[200704]];

# roundScheduling(
#     depencyPairSet=depSet, # a list of tuple specifying depedency relationship
#     noStreamEle=nostream,
#     layerType=layerType,
#     layerPerIPlatencyList=layerPerIPlatencyList, #the layer need to be topologically sorted
#     ConvIPnum=2,
#     PoolIPnum=1,
#     EleIPnum=1,
#     MaxRound=5
# );