from gurobipy import *


def roundScheduling(
    depencyPairSet, # a list of tuple [i,j] specifying depedency relationship, with 
    noStreamEle,
    loneLayerDeps,
    loneLayerArray,
    loneLayerLatencyList,
    layerType,
    layerArray,
    layerPerIPlatencyList,
    ConvIPnum,
    PoolIPnum,
    EleIPnum,
    MaxRound
):
    candidateNum=20;

    m=Model("roundScheduling");
    m.setParam( 'OutputFlag', False )
    m.setParam(GRB.Param.PoolSearchMode, 2)
    m.setParam(GRB.Param.PoolSolutions, candidateNum)
    X_irn=[]
    layerNum= len(layerPerIPlatencyList);
    loneLayerNum=len(loneLayerArray);
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
    
    L_ri=[]
    for r in range(MaxRound):
        L_i=[]
        for i in range( layerNum):

            l=m.addVar(vtype=GRB.INTEGER,name="X_"+str(i)+"_"+str(r)+"_"+str(n));
            L_i.append(l)
        L_ri.append(L_i);
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
        MI_ir.append(MI_r)
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
            exprI=LinExpr();
            exprI.addTerms(r,Y_ir[i][r])
            m.addConstr(exprI+1 <= exprJ);
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
                expr.addTerms(int(layerPerIPlatencyList[i][n][1]), X_irn[i][r][n]);
            m.addConstr( L_ri[r][i] == expr);
    
    for r in range(MaxRound):
        m.addConstr(M_r[r] == max_(L_ri[r]) );


    m.update();
    
  

    BC=100000000
    for i in range(loneLayerNum):
        for r in range(MaxRound):
            m.addConstr(-BC*Y_ir[i][r] <= MI_ir[i][r]);
            m.addConstr(MI_ir[i][r]  <=  BC*Y_ir[i][r]);       
            m.addConstr(MI_ir[i][r]  <=  BC*(1-Y_ir[i][r])+M_r[r]); 
            m.addConstr(MI_ir[i][r]  >=  -BC*(1-Y_ir[i][r])+M_r[r]); 

    for i in range(loneLayerNum):
        expr=LinExpr();
        for r in range(MaxRound):
            expr.addTerms(1, MI_ir[i][r]);
        m.addConstr( expr >= loneLayerLatencyList[i][0][1]) 

    expr=LinExpr();

    for r in range(MaxRound):
        expr.add(M_r[r])

    m.setObjective(expr,GRB.MINIMIZE);
    m.update();

    expr=LinExpr();
    for r in range(MaxRound):
        expr.addTerms(r,M_r[r])

    m.setObjectiveN(expr=expr,index=1,priority=-1,abstol=10);

    m.update();
    m.write("out.lp")
    m.optimize();

    roundMapping=[]
    roundDict={}
    
    

    print "indepedent latency", 
    if loneLayerLatencyList:
        print loneLayerLatencyList[0][0][1]
    else:
        print "[]"



    roundMappingCandidates=[]
    roundDictCandidates=[]
    latencyList=[]
    candidateNum=min(m.SolCount, candidateNum)
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
    roundMappingCandidates.append(roundMapping);
    roundDictCandidates.append(roundDict)
    latencyList.append(m.PoolObjVal)

    for candidateIdx in range(candidateNum):
        m.setParam(GRB.Param.SolutionNumber, candidateIdx)
        roundIdx=0;
        for r in range(MaxRound):
            layerMapping=[]
            for i in range(layerNum):
                for n,var in enumerate(X_irn[i][r]):
                    if var.Xn:
                        layerMapping.append( (roundIdx,layerArray[i],layerPerIPlatencyList[i][n][0]) );
                        roundDict[i]=roundIdx
            if layerMapping:
                roundMapping.append(layerMapping)            
                roundIdx+=1;
        roundMappingCandidates.append(roundMapping);
        roundDictCandidates.append(roundDict)
        latencyList.append(m.PoolObjVal)

    print m.objVal,latencyList
    if MI_ir:
        for r in range(MaxRound): 
            print MI_ir[0][r].X,
    print ""
    return roundMappingCandidates,roundDictCandidates,latencyList;

        
            