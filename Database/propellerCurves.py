#Used to determine propeller curves and thereby coefficients
#Eventually to store them to the component database
import sqlite3 as sql
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import os
from os import path
import polyFit as fit
import re


##############################################################################
#Set this bool to determine if the SQL database will be updated or not
updateDatabase = True
##############################################################################
#Other parameters
propDatabasePath = os.getcwd() + "/Props"

#Specify which group of props to analyze
wholeDatabase = os.listdir(path.join(propDatabasePath))
apcTestProps = ["apc_16x10", "apce_4x3.3", "apcr-rh_9x4.5"]
seligTestProps = ["kyosho_10x6", "ance_8.5x6", "grcp_9x4", "kavfk_11x7.75", "mit_5x4", "rusp_11x4"]
mixedProps = apcTestProps + seligTestProps
problemProps = ["da4022_9x6.75"]
propSet = wholeDatabase

thrustFitOrder = 2 #Order of polynomial fit to thrust vs advance ratio
powerFitOrder = 2 #Order of polynomial fit to power vs advance ratio

fitOfThrustFitOrder = 1 #Order of polynomial fit to thrust coefs vs rpm
fitOfPowerFitOrder = 1 #Order of polynomial fit to power coefs vs rpm

thrustZeroCoefs = [] #Which polynomial fit coefficients should be set to zero for Selig's props (for fitting coefs to RPM)
powerZeroCoefs = []

showPlots = False
###############################################################################

propCount = 0

if updateDatabase:
    db = sql.connect("components.db")
    dbcur = db.cursor()
    dbcur.execute("drop table Props") #The database is refreshed every time
    thrustCoefs = ["thrust"+str(x//(fitOfThrustFitOrder+1))+str(x%(fitOfThrustFitOrder+1))+" real," for x in range(((thrustFitOrder+1)*(fitOfThrustFitOrder+1)))]
    powerCoefs = ["power"+str(x//(fitOfPowerFitOrder+1))+str(x%(fitOfPowerFitOrder+1))+" real," for x in range(((powerFitOrder+1)*(fitOfPowerFitOrder+1)))]
    thrust = " ".join(thrustCoefs)
    power = " ".join(powerCoefs)[:-1]
    print(thrust)
    print(power)
    createTableCommand = """create table Props (id integer primary key, Name varchar, Diameter real, Pitch real, 
                            thrustFitOrder int default {tfo},
                            fitOfThrustFitOrder int default {fotfo},
                            powerFitOrder int default {pfo},
                            fitOfPowerFitOrder int default {fopfo},
                            """+thrust+" "+power+")"
    createTableCommand = createTableCommand.format(tfo = str(thrustFitOrder), fotfo = str(fitOfThrustFitOrder), pfo = str(powerFitOrder), fopfo = str(fitOfPowerFitOrder))
    print(createTableCommand)
    dbcur.execute(createTableCommand)

    dbcur.execute("select * from props")
    for columnName in dbcur.description:
        print(columnName)
    print(dbcur.fetchall())

for propFolder in propSet:
    
    if ".py" in str(propFolder):
        continue
    if ".xls" in str(propFolder):
        continue
    
    print("\n---", propFolder, "---")
  
    propFolderPath = propDatabasePath + "/" + propFolder
    dataType = None
    
    for filename in os.listdir(path.join(propFolderPath)):
        if "PER" in filename:
            if dataType is None: #Some props have both sets of data, of which Selig is superior
                dataType = "apc"
                dataFileName = filename
        if ("geom" in filename) or ("static" in filename):
            dataType = "selig"
                
    #print("Type: ", dataType)
    propCount += 1
    
    if dataType == "apc": #Data files from APC (manufacturer)
        #continue
        dataFile = open(propFolderPath + "/" + dataFileName)
        firstLine = dataFile.readline().split()
        diaPitch = firstLine[0].split("x")
        diameter = float(diaPitch[0])
        pitch = float(re.search(r'\d+', diaPitch[1]).group())
        
        #Read through the file to get how many sets of measurements were taken
        rpmCount = 0
        advRatioCount = []
        
        for line in dataFile:
            
            entries = line.split()
            if len(entries) != 0:
                if entries[0] == "PROP":
                    if float(entries[3]) > 10000.0:
                        break
                    rpmCount += 1
                    advRatioCount.append(0)
                elif entries[0][0].isdigit():
                    advRatioCount[rpmCount-1] += 1
        
        #Now read through the file to read in measurements
        dataFile.seek(0)
        print(rpmCount)
        firstLine = dataFile.readline().split() #Get rid of the first line
        rpmIndex = -1
        advRatioIndex = -1
        rpms = np.zeros(rpmCount)
        thrustFitArray = np.zeros((rpmCount, thrustFitOrder+1))
        powerFitArray = np.zeros((rpmCount, powerFitOrder+1))
        propCoefArray = None
        propCoefDict = {}
        
        #print("\nFit thrust and power to advance ratio.")
        
        for line in dataFile:
            
            line = line.replace("-", " ")
            entries = line.split()
            if len(entries) != 0:
                if entries[0] == "PROP":
                    if float(entries[3]) > 10000.0:
                        break
                    rpmIndex += 1
                    rpms[rpmIndex] = entries[3]
                    advRatioIndex = -1
                    propCoefArray = np.zeros((advRatioCount[rpmIndex], 4))
                    
                elif entries[0][0].isdigit():
                    advRatioIndex += 1
                    propCoefArray[advRatioIndex, 0] = entries[1] #Store advance ratio
                    propCoefArray[advRatioIndex, 1] = entries[2] #Store efficiency
                    propCoefArray[advRatioIndex, 2] = entries[3] #Store thrust coef
                    propCoefArray[advRatioIndex, 3] = entries[4] #Store power coef
                    
                    if advRatioIndex == advRatioCount[rpmIndex] - 1: #Determine polynomial fit for that rpm set
                        #print("RPM: ", rpms[rpmIndex])
                        thrustFitArray[rpmIndex], r = fit.poly_fit(thrustFitOrder+1, propCoefArray[:,0], propCoefArray[:,2])
                        #print("R2 for Ct:", r**2)
                        powerFitArray[rpmIndex], r = fit.poly_fit(powerFitOrder+1, propCoefArray[:,0], propCoefArray[:,3])
                        #print("R2 for Cp:", r**2)
                        propCoefDict[rpms[rpmIndex]] = propCoefArray
        
        dataFile.close()
        
        #print("\nFit thrust coefficients to rpm")
        fitOfThrustFit = np.zeros((thrustFitOrder+1, fitOfThrustFitOrder+1))
        
        for i in range(thrustFitOrder+1):
            fitOfThrustFit[i], r = fit.poly_fit(fitOfThrustFitOrder+1, rpms, thrustFitArray[:,i])
            #print(r**2)
        
        #print("\nFit power coefficients to rpm")
        fitOfPowerFit = np.zeros((powerFitOrder+1, fitOfPowerFitOrder+1))

        for i in range(powerFitOrder+1):
            fitOfPowerFit[i], r = fit.poly_fit(fitOfPowerFitOrder+1, rpms, powerFitArray[:,i])
            #print(r**2)
        
        #print("Max Error: ", maxError)
        
        print("Thrust Fit:\n", fitOfThrustFit)
        print("Power Fit:\n", fitOfPowerFit)        
    #----------------------------------END OF APC--------------------------------------------------
        
    elif dataType == "selig": #Data files from U of I U-C
        
        diaPitch = propFolder.split("_")[1].split("x")
        diameter = float(diaPitch[0])
        if "deg" in diaPitch[1]:
            pitch = 2*np.pi*0.525*diameter*np.tan(float(re.search(r'\d+', diaPitch[1]).group()))
        else:
            pitch = float(diaPitch[1])
        
        #Loop through files to count sets of measurements
        rpms = []
        rpmCount = 0
        staticRpmCount = 0
        advRatioCount = 0
        for dataFileName in os.listdir(path.join(propFolderPath)):
            if not ("static" in dataFileName or "geom" in dataFileName or "PER" in dataFileName):
                rpmCount += 1
                currAdvRatioCount = 0
                dataFile = open(propFolderPath + "/" + dataFileName)
                firstLine = dataFile.readline() #Throw away first line
                
                for line in dataFile:
                    currAdvRatioCount += 1
                    
                if currAdvRatioCount > advRatioCount:
                    advRatioCount = currAdvRatioCount
                    
                dataFile.close()
                
                
            elif "static" in dataFileName:
                dataFile = open(propFolderPath + "/" + dataFileName)
                firstLine = dataFile.readline() #Throw away first line
                for line in dataFile:
                    staticRpmCount += 1
                dataFile.close()
                
        
        #Loop thorugh files to read in measurements
        rpms = np.zeros(rpmCount)
        coefArray = np.zeros((rpmCount, advRatioCount, 4))
        staticArray = None
        rpmIndex = -1
        advRatioIndex = -1
        
        for dataFileName in os.listdir(path.join(propFolderPath)):
            #print(dataFileName)
            if not ("static" in dataFileName or "geom" in dataFileName or "PER" in dataFileName):
                rpmIndex += 1
                advRatioIndex = -1
                dataFileNameParts = dataFileName.split("_")#Pull apart the filename to extract the rpm value
                rpms[rpmIndex] = dataFileNameParts[-1].replace(".txt", "")
                dataFile = open(propFolderPath + "/" + dataFileName)
                firstLine = dataFile.readline() #Throw away first line
                
                for line in dataFile:
                    advRatioIndex += 1
                    entries = line.split()
                    coefArray[rpmIndex, advRatioIndex, 0] = entries[0] #Store advance ratio
                    coefArray[rpmIndex, advRatioIndex, 1] = entries[3] #Store efficiency
                    coefArray[rpmIndex, advRatioIndex, 2] = entries[1] #Store thrust coef
                    coefArray[rpmIndex, advRatioIndex, 3] = entries[2] #Store power coef
                    
                dataFile.close()
            elif "static" in dataFileName: #Static tests
                staticArray = np.zeros((staticRpmCount, 3))
                staticRpmIndex = -1
                dataFile = open(propFolderPath + "/" + dataFileName)
                firstLine = dataFile.readline() #Throw away first line
                
                for line in dataFile:
                    staticRpmIndex += 1
                    entries = line.split()
                    staticArray[staticRpmIndex,0] = entries[0] #Advance ratio
                    staticArray[staticRpmIndex,1] = entries[1] #Thrust coef
                    staticArray[staticRpmIndex,2] = entries[2] #Power coef
                    
                dataFile.close()
                
        print("Fit static coefficients to RPM")
        #Create polynomial fit of data
        staticThrustFitOrder = 3 #Order of polynomial to fit static thrust to
        staticPowerFitOrder = 3 #Order of polynomial to fit static power to
        
        #Fit curve to static thrust to give 0 advance ratio  results
        staticThrustFit, r = fit.poly_fit(staticThrustFitOrder, staticArray[:,0], staticArray[:,1])
        #print("R2 for Ct: ", r**2)
        staticPowerFit,r  = fit.poly_fit(staticPowerFitOrder, staticArray[:,0], staticArray[:,2])
        #print("R2 for Cp: ", r**2, "\n")
        
        plt.subplot(1,2,1)
        plt.plot(staticArray[:,0], staticArray[:,1])
        plt.xlabel("RPM")
        plt.ylabel("Thrust Coef")
        
        plt.subplot(1,2,2)
        plt.plot(staticArray[:,0], staticArray[:,2])
        plt.xlabel("RPM")
        plt.ylabel("Power Coef")
        plt.suptitle("Static data for "+propFolder)
        if showPlots:
            plt.show()
        
        #Fit dynamic data        
        thrustFitArray = np.zeros((rpmCount, thrustFitOrder+1))
        powerFitArray = np.zeros((rpmCount, powerFitOrder+1))
        
        #print("\nFitting thrust and power to advance ratio")
        
        propCoefDict = {}
        
        for rpmIndex in range(rpmCount):
            #print("RPM: ", rpms[rpmIndex])
            
            staticThrust = fit.poly_func(staticThrustFit, rpms[rpmIndex])
            staticPower = fit.poly_func(staticPowerFit, rpms[rpmIndex])
            
            advRatioInit = np.append(0, coefArray[rpmIndex,:,0])
            thrustInit = np.append(staticThrust, coefArray[rpmIndex,:,2])
            powerInit = np.append(staticPower, coefArray[rpmIndex,:,3])
            
            good = np.where((thrustInit != 0.) & (powerInit != 0.))
            
            advRatio = advRatioInit[good]
            thrust = thrustInit[good]
            power = powerInit[good]
            
            propCoefDict[rpms[rpmIndex]] = np.asarray([advRatio, np.zeros(len(advRatio)), thrust, power]).T
            
            thrustFitArray[rpmIndex], r = fit.poly_fit(thrustFitOrder+1, advRatio, thrust)
            #print("R2 for Ct: ", r**2)
            powerFitArray[rpmIndex], r = fit.poly_fit(powerFitOrder+1, advRatio, power, forcezero=[])
            #print("R2 for Cp: ", r**2)
            
        #Fit thrust and power fit coefficients to rpm
        #print("\nFit thrust coefficients to rpm")
        fitOfThrustFit = np.zeros((thrustFitOrder+1, fitOfThrustFitOrder+1))
        
        for i in range(thrustFitOrder+1):
            fitOfThrustFit[i], r = fit.poly_fit(fitOfThrustFitOrder+1, rpms, thrustFitArray[:,i], forcezero=thrustZeroCoefs)
            #print(r**2)
        
        #print("\nFit power coefficients to rpm")
        fitOfPowerFit = np.zeros((powerFitOrder+1, fitOfPowerFitOrder+1))

        for i in range(powerFitOrder+1):
            fitOfPowerFit[i], r = fit.poly_fit(fitOfPowerFitOrder+1, rpms, powerFitArray[:,i], forcezero=powerZeroCoefs)
            #print(r**2)
    #-----------------------END OF SELIG/UIUC---------------------------------------------
        
    #Predict thrust and power based off of fits
    #ALL FOLLOWING CODE IS EXECUTED FOR BOTH TYPES OF PROPS
    #print("\nThrust Prediction")
    maxError = 0
    fig = plt.figure(figsize=plt.figaspect(1.))
    fig.suptitle(propFolder)

    #Fits of fits
    rpmSpace = np.linspace(0,max(rpms),100)
    ax = fig.add_subplot(2, 2, 1)
    for i in range(thrustFitOrder+1):
        ax.plot(rpms, thrustFitArray[:,i], "o", markersize=4)
        ax.plot(rpmSpace, fit.poly_func(fitOfThrustFit[i], rpmSpace), "-")
    ax.set_title("Thrust " + str(thrustFitOrder) + "th Order Fit Coefficients")
    ax.set_xlabel("RPM")
    ax.set_ylabel("Magnitude of Coefficients")
    ax.legend([b for a in (str(coef) for coef in range(thrustFitOrder+1)) for b in [a, a]])


    ax = fig.add_subplot(2, 2, 2)
    for i in range(powerFitOrder+1):
        ax.plot(rpms, powerFitArray[:,i], "o", markersize=4)
        ax.plot(rpmSpace, fit.poly_func(fitOfPowerFit[i], rpmSpace), "-")
    ax.set_title("Power " + str(powerFitOrder) + "th Order Fit Coefficients")
    ax.set_xlabel("RPM")
    ax.set_ylabel("Magnitude of Coefficients")
    ax.legend([b for a in (str(coef) for coef in range(thrustFitOrder+1)) for b in [a, a]])

    #Fits
    ax = fig.add_subplot(2,2,3, projection='3d')

    for rpm in rpms:
        rpmExp = np.full(len(propCoefDict[rpm][:,0]), rpm)
        ax.plot(propCoefDict[rpm][:,0], rpmExp, propCoefDict[rpm][:,2], "bo", markersize=4)

        a = fit.poly_func(fitOfThrustFit.T, rpm)
        advRatioSpace = np.linspace(0, 1.8, 100)
        thrust = fit.poly_func(a, advRatioSpace)
        rpmTheo = np.full(len(thrust), rpm)
        ax.plot(advRatioSpace, rpmTheo, thrust, "r-")
     
        SSE = 0
       
        for exp, theo in zip(propCoefDict[rpm][:,2], thrust):
            SSE += (exp - theo)**2
            if abs(exp - theo) > maxError:
                maxError = abs(exp - theo)
            
        RMSerror = np.sqrt(SSE/len(thrust))
        #print("RMS error: ", RMSerror)
           
        a = fit.poly_func(fitOfThrustFit.T, rpm+500)
        thrust = fit.poly_func(a, advRatioSpace)
        plt.plot(advRatioSpace, rpmTheo+500, thrust, "r-")

    for rpm in np.linspace(0,min(rpms),10): #Plot fits down to 0 RPMs to examine end behavior
        rpmTheo = np.full(len(thrust), rpm)
        a = fit.poly_func(fitOfThrustFit.T, rpm)
        thrust = fit.poly_func(a, advRatioSpace)
        plt.plot(advRatioSpace, rpmTheo, thrust, "g-")
            
    ax.set_title("Predicted thrust from " + str(fitOfThrustFitOrder) + "th order fit of " + str(thrustFitOrder) + "th order fit")
    ax.set_xlabel("Advance Ratio")
    ax.set_ylabel("RPM")
    ax.set_zlabel("Thrust Coefficient")
    #print("Max Error: ", maxError)
        
    #print("\nPower Prediction")
    maxError = 0
    ax = fig.add_subplot(2,2,4, projection='3d')
    
    for rpm in rpms:
        a = fit.poly_func(fitOfPowerFit.T, rpm)
        advRatioSpace = np.linspace(0, 1.2, 100)
        power = fit.poly_func(a, advRatioSpace)
        rpmExp = np.full(len(propCoefDict[rpm][:,0]), rpm)
        rpmTheo = np.full(len(power), rpm)
        ax.plot(propCoefDict[rpm][:,0], rpmExp, propCoefDict[rpm][:,3], "bo", markersize=4)
        ax.plot(advRatioSpace, rpmTheo, power, "r-")
         
        SSE = 0
       
        for exp, theo in zip(propCoefDict[rpm][:,3], power):
            SSE += (exp - theo)**2
            if abs(exp - theo) > maxError:
                maxError = abs(exp - theo)
            
        RMSerror = np.sqrt(SSE/len(power))
        #print("RMS Error: ", RMSerror)
        
        a = fit.poly_func(fitOfPowerFit.T, rpm+500)
        power = fit.poly_func(a, advRatioSpace)
        ax.plot(advRatioSpace, rpmTheo+500, power, "r-")

    for rpm in np.linspace(0,min(rpms),10): #Plot fits down to 0 RPMs to examine end behavior
        rpmTheo = np.full(len(power), rpm)
        a = fit.poly_func(fitOfPowerFit.T, rpm)
        power = fit.poly_func(a, advRatioSpace)
        ax.plot(advRatioSpace, rpmTheo, power, "g-")
        
            
    ax.set_title("Predicted Power from " + str(fitOfPowerFitOrder) + "th order fit of " + str(powerFitOrder) + "th order fit")
    ax.set_xlabel("Advance Ratio")
    ax.set_ylabel("RPM")
    ax.set_zlabel("Power Coefficient")
    #print("Max Error: ", maxError)
    if showPlots:
        plt.show()
           
    print("Thrust Fit:\n", fitOfThrustFit)
    print("Power Fit:\n", fitOfPowerFit)

    if updateDatabase:
    
        #Store coefficients and geometry in the components.db database
        insertCommand = "insert into props (Name, Diameter, Pitch) values (\""+str(propFolder)+"\","+str(diameter)+","+str(pitch)+")"
        print(insertCommand)
        dbcur.execute(insertCommand)

        for i in range(thrustFitOrder+1):
            for j in range(fitOfThrustFitOrder+1):
                insertCommand = "update props set thrust"+str(i)+str(j)+"="+str(fitOfThrustFit[i,j])+" where name = \""+str(propFolder)+"\""
                print(insertCommand)
                dbcur.execute(insertCommand)

        for i in range(powerFitOrder+1):
            for j in range(fitOfPowerFitOrder+1):
                insertCommand = "update props set power"+str(i)+str(j)+"="+str(fitOfPowerFit[i,j])+" where name = \""+str(propFolder)+"\""
                print(insertCommand)
                dbcur.execute(insertCommand)

if updateDatabase:
    dbcur.execute("select * from props")
    print(dbcur.fetchall())
    print("Successfully stored ", propCount, " props.")
    db.commit()
    db.close()

print("Successfully analyzed ", propCount, " props.")
