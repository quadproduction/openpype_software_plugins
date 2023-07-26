# -----------------------------------------------------------------------------------------------maya-
# file: ark_instToGeo.py
# version: 2.0
# date: 2016.12.17
# author: Arkadiy Demchenko (sagroth@sigillarium.com)
# ----------------------------------------------------------------------------------------------------
# Converts instancer into keyframed objects:
# Put the file into maya scripts dir and run:
#
# from ark_instToGeo import *; ark_instToGeo()
# ----------------------------------------------------------------------------------------------------
# 2016.12.17 (v2.0) - works with instancer aim modes
#                   - suspends viewport refresh for speedup and stability
#                   - reworked the grouping method for great increase in
# instances creation
#                   - added progress bars (per particle and per frame) and
# final statistics
#                   - added hybrid mode (duplicates follow original geo via
# outMesh->inMesh link)
#                   - doesn't set keyframes for single frame conversion
#
# 2016.09.21 (v1.5) - now works with namespaced instances
#
# 2012.05.05 (v1.4) - corrected GUI for older maya versions
#
# 2012.04.06 (v1.3) - doesn't set visibility to off prior to the starting
# frame of conversion
#                   - doesn't pay attention to 'start from current frame' if
# custom range is defined
#
# 2011.06.19 (v1.2) - reworked GUI
#                   - uses long names correctly (no problems with objects of
# the same name anymore)
#                   - doesn't freeze source objects' rotations or error if
# channels have keyframes
#                   - keeps input connections for instances also
#                   - works with different rotation orders of source objects
# and instancer itself
#                   - each baked object is inside it's own group which actually
# gets all keyframes
#                   - works with any linear units of the scene (switches to cm
# and back, actually)
#
# 2010.06.11 (v1.1) - duplicates now maintain original input connections
#                   - only translate, rotate, scale and visibility are
# keyframed now
#
# 2009.11.14 (v1.0) - main release
# ----------------------------------------------------------------------------------------------------
from maya import cmds
import time


# GUI
def ark_instToGeo():
    win = "ark_instToGeo_win"
    if cmds.window(win, exists=True):
        cmds.deleteUI(win)

    cmds.window(win, title="Inst to Geo", sizeable=False)

    cmds.columnLayout(adj=True, columnAttach=["both", 1])

    cmds.radioButtonGrp(
        win + "__dupOrInst_RBG",
        columnWidth3=[78, 70, 70],
        labelArray3=["Duplicate", "Hybrid", "Instance"],
        numberOfRadioButtons=3,
        select=3,
    )

    cmds.separator(style="in")

    cmds.checkBox(
        win + "__fromCurFrame_ChB",
        align="left",
        label="Start from Current Frame",
        value=0,
    )

    cmds.radioButtonGrp(
        win + "__range_RBG",
        labelArray2=["Playback Range", "Custom Range"],
        numberOfRadioButtons=2,
        select=1,
        onCommand1='intFieldGrp("'
        + win
        + '__range_IFG", edit=True, \
enable1=False, enable2=False)',
        onCommand2='intFieldGrp("'
        + win
        + '__range_IFG", edit=True, \
enable1=True, enable2=True)',
    )

    cmds.intFieldGrp(
        win + "__range_IFG",
        label="",
        numberOfFields=2,
        columnWidth=(1, 24),
        value1=cmds.playbackOptions(q=True, min=True),
        value2=cmds.playbackOptions(q=True, max=True),
        enable1=False,
        enable2=False,
    )

    cmds.separator(style="in")

    cmds.rowLayout(
        numberOfColumns=2,
        columnWidth2=[172, 40],
        columnAlign2=["center", "center"]
    )

    cmds.button(label="Convert", width=172, command="ark_instToGeo_cmd()")

    cmds.button(
        label="Help",
        width=48,
        command='showHelp("http://www.sigillarium.com/blog/lang/en/1188/", \
absolute=True)',
    )

    cmds.setParent("..")

    # PROGRESS BAR
    cmds.progressBar(
        "ark_instToGeo_progBar1", width=220, height=15, isInterruptable=True
    )
    cmds.progressBar(
        "ark_instToGeo_progBar2", width=220, height=15, isInterruptable=True
    )

    cmds.showWindow(win)
    cmds.window(win, edit=True, width=228, height=143)


# FEEDBACK FORM
def ark_instToGeo_feedback(*msg):
    feedback = " " + msg[0]
    feedLen = len(feedback)
    for each in msg[1:]:
        feedback += "\r\n " + each
        feedLen = max(feedLen, len(each))

    liner = "#"
    for i in xrange(0, feedLen + 1):
        liner += "#"

    print("")
    print(liner)
    print(feedback)
    print(liner)


# RUN MAIN PROCEDURE WITH SETTINGS FROM GUI
def ark_instToGeo_cmd():
    win = "ark_instToGeo_win"
    dupOrInst = cmds.radioButtonGrp(
        win + "__dupOrInst_RBG",
        q=True, select=True
    ) - 1
    fromCurFrame = cmds.checkBox(
        win + "__fromCurFrame_ChB",
        q=True,
        value=True
    )
    rangeSpecified = cmds.radioButtonGrp(
        win + "__range_RBG",
        q=True,
        select=True
    ) - 1
    start = cmds.intFieldGrp(win + "__range_IFG", q=True, value1=True)
    end = cmds.intFieldGrp(win + "__range_IFG", q=True, value2=True)

    ark_instToGeo_do(dupOrInst, fromCurFrame, rangeSpecified, start, end)


# MAIN PROCEDURE
def ark_instToGeo_do(dupOrInst, fromCurFrame, rangeSpecified, start, end):
    # START TIMER
    startTime = time.clock()

    # SUSPEND REFRESH
    cmds.refresh(suspend=True)

    # RANGE OPTIONS
    currentFrame = cmds.currentTime(q=True)
    startFrame = cmds.playbackOptions(q=True, min=True)
    endFrame = cmds.playbackOptions(q=True, max=True)

    if rangeSpecified > 0:
        startFrame = start
        endFrame = end
    elif fromCurFrame > 0:
        startFrame = currentFrame

    # TURN OFF ANIMATION DETECTION FOR SINGLE FRAME BAKING
    anim = 1
    if startFrame == endFrame:
        anim = 0

    # MAKE A LIST OF ALL SELECTED INSTANCERS
    instList = []

    selList = cmds.ls(selection=True)

    for each in selList:
        if cmds.objectType(each) == "instancer":
            instList.append(each)

    if instList == []:
        print("No instancers selected!")
        return

    # LIST OF TEMPORARY GROUPS
    instGrps = []

    # FIND GEOMETRY, PARTICLE OBJECTS AND MAPPED ATTRIBUTES FOR INSTANCERS
    geoList = []
    ptList = []
    iamList = []

    blankInsts = []
    for each in instList:
        # MAKE A LIST OF INPUT OBJECTS
        instGeo = cmds.listConnections(
            each + ".inputHierarchy",
            source=True,
            destination=False,
            connections=False,
            plugs=False,
        )

        if instGeo is None:
            print("No geometry connected to instancer " + each + "!")
            blankInsts.append(each)

        else:
            # MAKE A LIST OF PARTICLE OBJECTS AND THEIR INSTANCER
            # MAPPED ATTRIBUTES
            conn = cmds.listConnections(
                each + ".inputPoints",
                source=True,
                destination=False,
                connections=False,
                plugs=True,
            )

            if conn is None:
                print("No particles connected to instancer " + each + "!")
                blankInsts.append(each)
            else:
                geoList.append(instGeo)
                ptList.append(conn[0][: conn[0].find(".")])
                iamList.append(cmds.getAttr(
                    conn[0][: conn[0].rfind(".")] + ".instanceAttributeMapping"
                    ))

    # REMOVE INSTANCERS WITH NO GEOMETRY OR PARTICLES ATTACHED FROM THE LIST
    for each in blankInsts:
        instList.remove(each)

    # QUIT IF NO REASONABLE INSTANCERS LEFT
    if instList == []:
        return

    # SET UNITS TO CM (SINCE THAT'S WHAT PARTICLE VALUES USING NO MATTER WHAT)
    origUnits = cmds.currentUnit(query=True, linear=True)
    cmds.currentUnit(linear="cm")

    # LISTS FOR STORING CONVERTED IDS AND CREATED DUPLICATES
    pids = []
    dups = []
    for inst in instList:
        pids.append([])
        dups.append([])

    # CREATE LOCATORS FOR AIM CALCULATION
    locTgt = cmds.spaceLocator()[0]
    locOgn = cmds.spaceLocator()[0]
    aimConstr = cmds.aimConstraint(locTgt, locOgn)[0]

    # ENABLE FRAME PROGRESS BAR UPDATE
    cmds.progressBar(
        "ark_instToGeo_progBar2",
        edit=True,
        maxValue=endFrame - startFrame + 1,
        progress=0,
    )

    allInstCount = 0
    # MAIN CONVERSION LOOP
    for t in xrange(int(startFrame), int(endFrame) + 1):
        cmds.currentTime(t, update=True)
        cmds.progressBar("ark_instToGeo_progBar2", edit=True, step=1)

        for inst in instList:
            instInd = instList.index(inst)
            instGeo = geoList[instInd]
            instPt = ptList[instInd]
            instIam = iamList[instInd]

            # GET INSTANCER ROTATION ORDER AND CONVERT IT INTO
            # GEOMETRY ROTATION ORDER
            instRodOrig = cmds.getAttr(inst + ".rotationOrder")
            instRodConv = {0: 0, 1: 3, 2: 4, 3: 1, 4: 2, 5: 5}
            instRod = instRodConv[instRodOrig]

            deadPids = pids[instList.index(inst)][:]
            instNum = cmds.getAttr(inst + ".instanceCount")

            # ENABLE INSTANCE PROGRESS BAR UPDATE
            cmds.progressBar(
                "ark_instToGeo_progBar1",
                edit=True,
                maxValue=instNum + 1,
                progress=0
            )

            for i in xrange(0, instNum):
                cmds.progressBar("ark_instToGeo_progBar1", edit=True, step=1)

                # GET GENERAL OPTIONS VALUES
                pid = int(cmds.particle(
                    instPt,
                    q=True,
                    at="particleId",
                    order=i
                )[0])
                pos = cmds.particle(
                    instPt,
                    q=True,
                    at="worldPosition",
                    order=i
                )
                scl = (1, 1, 1)
                vis = 1.0
                idx = 0.0
                if "scale" in instIam:
                    scl = cmds.particle(
                        instPt,
                        q=True,
                        at=instIam[instIam.index("scale") + 1],
                        order=i
                    )
                if "shear" in instIam:
                    cmds.particle(
                        instPt,
                        q=True,
                        at=instIam[instIam.index("shear") + 1],
                        order=i
                    )
                if "visibility" in instIam:
                    vis = cmds.particle(
                        instPt,
                        q=True,
                        at=instIam[instIam.index("visibility") + 1],
                        order=i,
                    )[0]
                if "objectIndex" in instIam:
                    idx = cmds.particle(
                        instPt,
                        q=True,
                        at=instIam[instIam.index("objectIndex") + 1],
                        order=i,
                    )[0]

                # IF OBJECT INDEX IS HIGHER OR LOWER THAN AVAILABLE
                # NUMBER OF INSTANCE OBJECTS - CLAMP TO THE CLOSEST
                # POSSIBLE VALUE
                if idx > (len(instGeo) - 1):
                    idx = len(instGeo) - 1
                elif idx < 0:
                    idx = 0

                # IF SCALE ATTRIBUTE IS FLOAT INSTEAD OF VECTOR - FORCE VECTOR
                if len(scl) < 3:
                    scl = [scl[0], scl[0], scl[0]]

                # GET ROTATION TYPE AND CALCULATE CORRESPONDING EULER ANGLES
                rotType = 0
                if "rotationType" in instIam:
                    rotType = int(
                        cmds.particle(
                            instPt,
                            q=True,
                            at=instIam[instIam.index("rotationType") + 1],
                            order=i,
                        )[0]
                    )
                else:
                    if "rotation" in instIam:
                        rotType = 0
                    elif "aimDirection" in instIam:
                        rotType = 1
                    elif "aimPosition" in instIam:
                        rotType = 2

                aimAxis = (1, 0, 0)
                if "aimAxis" in instIam:
                    if instIam[instIam.index("aimAxis") + 1] != "":
                        aimAxis = cmds.particle(
                            instPt,
                            q=True,
                            at=instIam[instIam.index("aimAxis") + 1],
                            order=i,
                        )

                aimUpAxis = (0, 1, 0)
                if "aimUpAxis" in instIam:
                    if instIam[instIam.index("aimUpAxis") + 1] != "":
                        aimUpAxis = cmds.particle(
                            instPt,
                            q=True,
                            at=instIam[instIam.index("aimUpAxis") + 1],
                            order=i,
                        )

                aimWorldUp = (0, 1, 0)
                if "aimWorldUp" in instIam:
                    if instIam[instIam.index("aimWorldUp") + 1] != "":
                        aimWorldUp = cmds.particle(
                            instPt,
                            q=True,
                            at=instIam[instIam.index("aimWorldUp") + 1],
                            order=i,
                        )

                rot = (0, 0, 0)
                if rotType == 0:
                    if "rotation" in instIam:
                        rot = cmds.particle(
                            instPt,
                            q=True,
                            at=instIam[instIam.index("rotation") + 1],
                            order=i,
                        )
                elif rotType == 1:
                    if "aimDirection" in instIam:
                        vec = cmds.particle(
                            instPt,
                            q=True,
                            at=instIam[instIam.index("aimDirection") + 1],
                            order=i,
                        )
                        cmds.setAttr(
                            locTgt + ".t",
                            vec[0],
                            vec[1],
                            vec[2],
                            type="double3"
                        )
                        cmds.setAttr(
                            aimConstr + ".aimVector",
                            aimAxis[0],
                            aimAxis[1],
                            aimAxis[2],
                            type="double3",
                        )
                        cmds.setAttr(
                            aimConstr + ".upVector",
                            aimUpAxis[0],
                            aimUpAxis[1],
                            aimUpAxis[2],
                            type="double3",
                        )
                        cmds.setAttr(
                            aimConstr + ".worldUpVector",
                            aimWorldUp[0],
                            aimWorldUp[1],
                            aimWorldUp[2],
                            type="double3",
                        )
                        rot = cmds.getAttr(locOgn + ".r")[0]
                elif rotType == 2:
                    if "aimPosition" in instIam:
                        vec = cmds.particle(
                            instPt,
                            q=True,
                            at=instIam[instIam.index("aimPosition") + 1],
                            order=i,
                        )
                        cmds.setAttr(
                            locTgt + ".t",
                            vec[0],
                            vec[1],
                            vec[2],
                            type="double3"
                        )
                        cmds.setAttr(
                            locOgn + ".t",
                            pos[0],
                            pos[1],
                            pos[2],
                            type="double3"
                        )
                        cmds.setAttr(
                            aimConstr + ".aimVector",
                            aimAxis[0],
                            aimAxis[1],
                            aimAxis[2],
                            type="double3",
                        )
                        cmds.setAttr(
                            aimConstr + ".upVector",
                            aimUpAxis[0],
                            aimUpAxis[1],
                            aimUpAxis[2],
                            type="double3",
                        )
                        cmds.setAttr(
                            aimConstr + ".worldUpVector",
                            aimWorldUp[0],
                            aimWorldUp[1],
                            aimWorldUp[2],
                            type="double3",
                        )
                        rot = cmds.getAttr(locOgn + ".r")[0]

                # IF THE PARTICLE IS NEWBORN MAKE A DUPLICATE
                newBorn = 0

                dupName = (
                    inst.replace("|", "_")
                    + "_"
                    + instGeo[int(idx)].replace("|", "_").replace(":", "_")
                    + "_id_"
                    + str(pid)
                )

                if pid not in pids[instList.index(inst)]:
                    pids[instList.index(inst)].append(pid)
                    allInstCount += 1

                    # IF OBJECT WITH THE SAME NAME ALREADY EXISTS,
                    # ADD _# SUFFIX
                    if cmds.objExists(dupName):
                        z = 1
                        dupName += "_" + str(z)
                        while cmds.objExists(dupName):
                            z += 1
                            dupName = dupName[: dupName.rfind("_") + 1] + str(z)  # noqa E501

                    # CREATE A GROUP WITH THE OBJECT TO DUPLICATE
                    instGrp = instGeo[int(idx)] + "_instToGeo_instGrp"

                    if not cmds.objExists(instGrp):
                        instGrp = cmds.group(em=True, name=instGrp)
                        instPos = cmds.getAttr(
                            instGeo[int(idx)] + ".translate"
                        )[0]
                        cmds.setAttr(
                            instGrp + ".translate",
                            instPos[0],
                            instPos[1],
                            instPos[2],
                            type="double3",
                        )
                        instGrps.append(instGrp)

                        if dupOrInst == 2:
                            dup = cmds.instance(
                                instGeo[int(idx)],
                                name=instGeo[int(idx)] + "_instToGeo_instObj",
                            )[0]
                        else:
                            dup = cmds.duplicate(
                                instGeo[int(idx)],
                                name=instGeo[int(idx)] + "_instToGeo_instObj",
                            )[0]
                        cmds.parent(dup, instGrp)
                        trsConns = cmds.listConnections(
                            instGeo[int(idx)], s=True, d=False, c=True, p=True
                        )
                        if trsConns is not None:
                            for y in xrange(0, len(trsConns), 2):
                                if not cmds.isConnected(
                                    trsConns[y + 1],
                                    dup + trsConns[y][trsConns[y].rfind("."):],
                                ):
                                    cmds.connectAttr(
                                        trsConns[y + 1],
                                        dup + trsConns[y][trsConns[y].rfind("."):],  # noqa E501
                                    )

                    # CREATE A DUPLICATE
                    if dupOrInst == 2:
                        dupGrp = cmds.duplicate(
                            instGrp,
                            name=dupName + "_grp",
                            inputConnections=True,
                            instanceLeaf=True,
                        )[0]
                        dup = cmds.rename(cmds.listRelatives(
                            dupGrp, children=True, fullPath=True
                        )[0], dupName,)
                    else:
                        dupGrp = cmds.duplicate(
                            instGrp,
                            name=dupName + "_grp",
                            inputConnections=True,
                            instanceLeaf=False,
                        )[0]
                        dup = cmds.rename(cmds.listRelatives(
                            dupGrp, children=True, fullPath=True
                        )[0], dupName,)
                        if dupOrInst == 1:
                            cmds.connectAttr(
                                instGeo[int(idx)] + ".outMesh",
                                dup + ".inMesh",
                                force=True,
                            )

                    dup = dupGrp
                    dups[instList.index(inst)].append(dup)

                    if t != int(startFrame):
                        newBorn = 1
                else:
                    # IF OBJECT WITH THE SAME NAME EXISTS FROM PREVIOUS BAKE,
                    # FIND THE SUFFIXED NAME FROM THIS BAKE
                    if not dupName + "_grp" in dups[instList.index(inst)]:
                        z = 1
                        dupName += "_" + str(z)
                        while not dupName + "_grp" in dups[instList.index(inst)]:  # noqa E501
                            z += 1
                            dupName = dupName[: dupName.rfind("_") + 1] + str(z)  # noqa E501

                    dup = dupName + "_grp"
                    if pid in deadPids:
                        deadPids.remove(pid)

                # TRANSFORM THE DUPLICATE
                cmds.setAttr(
                    dup + ".translate", pos[0], pos[1], pos[2], type="double3"
                )
                cmds.setAttr(
                    dup + ".scale", scl[0], scl[1], scl[2], type="double3"
                )
                cmds.setAttr(dup + ".visibility", vis)

                cmds.setAttr(dup + ".rotateOrder", instRod)
                cmds.setAttr(
                    dup + ".rotate", rot[0], rot[1], rot[2], type="double3"
                )

                # SET KEYFRAMES
                if anim:
                    cmds.setKeyframe(
                        dup,
                        inTangentType="linear",
                        outTangentType="linear",
                        attribute=(
                            "translate", "rotate", "scale", "visibility"
                        ),
                    )
                    if newBorn > 0:
                        cmds.setKeyframe(
                            dup + ".visibility",
                            time=cmds.currentTime(q=True) - 1,
                            value=0
                        )

            # MAKE DEAD INSTANCES INVISIBLE
            for dead in deadPids:
                cmds.setKeyframe(
                    dups[instList.index(inst)][pids[instList.index(inst)].index(dead)]  # noqa E501
                    + ".visibility",
                    value=0,
                )

    # DELETE AIM LOCATORS
    cmds.delete([aimConstr, locTgt, locOgn])

    # DELETE TEMPORARY GROUPS
    cmds.delete(instGrps)

    # GROUP DUPLICATES, DELETE STATIC CHANNELS AND APPLY EULER FILTER
    for inst in instList:
        cmds.group(
            dups[instList.index(inst)], name=inst + "_geo_grp", world=True
        )
        for obj in dups[instList.index(inst)]:
            cmds.delete(
                obj,
                staticChannels=True,
                unitlessAnimationCurves=False,
                hierarchy="none",
                controlPoints=False,
                shape=False,
            )
            animCurves = cmds.listConnections(
                obj,
                source=True,
                destination=False,
                connections=False,
                plugs=False
            )
            cmds.filterCurve(animCurves)

    # RESTORING ORIGINAL UNITS
    cmds.currentUnit(linear=origUnits)

    # ENABLE REFRESH
    cmds.refresh(suspend=False)
    cmds.refresh()

    # RESET PROGRESS BARS
    cmds.progressBar(
        "ark_instToGeo_progBar1", edit=True, minValue=-1, progress=-1
    )
    cmds.progressBar("ark_instToGeo_progBar1", edit=True, minValue=0)
    cmds.progressBar(
        "ark_instToGeo_progBar2", edit=True, minValue=-1, progress=-1
    )
    cmds.progressBar("ark_instToGeo_progBar2", edit=True, minValue=0)

    # CALCULATE DURATION
    endTime = time.clock()
    secs = int((endTime - startTime) % 60)
    hours = int((endTime - startTime - secs) / 3600)
    mins = int((endTime - startTime - secs - hours * 3600) / 60)
    exportTime = (
        zfill(
            str(hours), 2
        ) + ":" + zfill(
            str(mins), 2
        ) + ":" + zfill(
            str(secs), 2
        )
    )

    # FEEDBACK
    ark_instToGeo_feedback(
        "INST TO GEO STATISTICS",
        "Conversion done in: " + exportTime,
        "Instances created: " + str(allInstCount),
    )
