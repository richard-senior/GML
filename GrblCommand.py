# pip3 install svg-to-gcode
from typing import TypeVar, List
import re
import os
import math
from svg_to_gcode.svg_parser import parse_file
from svg_to_gcode.compiler import Compiler, interfaces


class GrblCommand:
    """
        Class holding information about GCODE commands.
        Functionality:
            * Parsing, validation and rendering of string representation of GCODE commands
              such as G00 X12.5 Y15.2 F200 etc.
            * The formation of linked lists of commands (previous and next methods)
            * Allowing sections of linked lists to be declared as
              'blocks' of commands based on various rules
            * Sanitising, sorting and other manipulations of blocks of commands
    """
    # Enable O02 style line numbering of blocks of commands
    auto_number_blocks: bool = False
    # Enable N02 style line numbering
    auto_number_lines: bool = False
    # automatically sanitise GCODE into blocks
    auto_sanitise: bool = True
    # return to zero and dwell after every path
    dwell_after_block: bool = False
    tool_diameter: float = 1.0
    depth_step: float = -0.25
    evacuation_height: float = 1
    cut_speed: int = 50
    spindle_rpm: int = 1000
    fast_travel_speed: int = 800
    penetrate_speed: int = 50
    command = i = j = r = k = comment = next = previous = None
    x = y = z = None
    p = None
    f = None
    s = None
    o = None
    n = None
    line = None
    inComment = False
    visible = True
    meta = None
    max_dp = 6
    min_dp = 2
    block = 0
    blockIndex = -1
    showIndices = False
    autoBlockSort = True

    def __init__(self, line: str):
        self.line = line
        if not line:
            # permit blank objects
            return
        
        if line.strip().startswith("("):
            self.comment = line
            return

        if line.strip().startswith("%"):
            self.comment = "percent? Why in gods name?"
            return

        if "(" in line:
            line = GrblCommand.removeBracketedText(line)

        foo = line.strip().split()

        for c in foo:
            if not c:
                continue

            first_char = c.strip()[0].upper()
            last_char = c.strip()[-1:].upper()

            if last_char == ")":
                self.inComment = False
                continue

            if self.inComment:
                continue

            # Python.. pfft
            if first_char == "G":
                self.command = c
            elif first_char == "M":
                self.command = c
            elif first_char == "X":
                self.x = self.parseParameter(c)
            elif first_char == "Y":
                self.y = self.parseParameter(c)
            elif first_char == "Z":
                self.z = self.parseParameter(c)
            elif first_char == "I":
                self.i = self.parseParameter(c)
            elif first_char == "J":
                self.j = self.parseParameter(c)
            elif first_char == "S":
                self.s = self.parseParameter(c)
            elif first_char == "F":
                self.f = self.parseParameter(c)
            elif first_char == "O":
                self.o = self.parseParameter(c)
            elif first_char == "P":
                self.p = self.parseParameter(c)
            elif first_char == "N":
                self.n = self.parseParameter(c)
            elif first_char == "(":
                self.inComment = True
            else:
                raise ValueError("not recognised GRBL syntax : " + c)

    def getRawLine(self):
        return self.line

    def prependObject(self, obj):
        if not obj:
             raise ValueError("must pass valid object")
        if self.getPrevious():
            obj.setPrevious(self.getPrevious())
        self.setPrevious(obj)
        return obj

    def prepend(self,line:str):
        c = GrblCommand(line)
        return self.prependObject(c)
    
    # add a single command, or a list of commands
    def appendObjects(self, obj):
        if not obj: return None
        if not isinstance(obj, list): return self.appendObject(obj)
        lo = None
        for o in obj:
            if not lo: 
                lo = self.appendObject(o)
            else:
                lo = lo.appendObject(o)
        return lo

    def appendObject(self, obj):
        if not obj:
            return
        obj.setPrevious(self)
        # self.setNext(obj)
        return obj
    
    def append(self,line:str):
        c = GrblCommand(line)
        return self.appendObject(c)

    def delete(self):
        if self.getPrevious():
            self.getPrevious().setNext(self.getNext())
        if self.getNext():
            self.getNext().setPrevious(self.getPrevious())
        if self.getPrevious():
            return self.getPrevious()
        elif self.getNext():
            return self.getNext()
        return None

    def isInBlock(self):
        return self.blockIndex > -1

    def isBlockStart(self):
        if not self.x or not self.y:
            return False
        if "G00" == self.command:
            return True
        if not self.getPrevious():
            return True
        if self.getPrevious().isInBlock():
            return False
        return True

    def isBlockEnd(self):
        if self.isBlockStart():
            return False
        if self.isInBlock():
            # start of new fast travel indicates block end
            if "G00" == self.command:
                return True
            # stop spindle indicates block end (mainly lasers)
            if "M05" == self.command:
                return True
            # lifting the cutter indicates block end
            if self.isEvacuation():
                return True
            # pcob = self.getPrevious() and (self.getPrevious().isComment() or self.getPrevious().isBlank())
            # cob = self.isBlank() or self.isComment()
            # consecutive blank lines indicates block end
            # if pcob and cob:
            #    return True
            # other stuff here
        else:
            pass
        return False

    #sets the feed rate of all commands which operate at a
    #depth less than or equal zero
    def setCutSpeed(self, speed):
        if not speed:
            raise ValueError("must pass a valid depth")
        c = self.getFirst()
        while c:
            if c.isPenetrate():
                c = c.getNext()
                continue
            if c.z:
                if 0 >= c.z:
                    c.f = speed
            else:
                if 0 >= c.getEstimatedZ():
                    c.f = speed
            c = c.getNext()

    #sets the feed rate of all commands which operate at a
    #depth greater than or equal zero
    def setFastTravelSpeed(self, speed):
        if not speed:
            raise ValueError("must pass a valid speed and height")
        c = self.getFirst()
        while c:
            if c.z:
                if 0 <= c.z:
                    c.f = speed
            else:
                if 0 <= c.getEstimatedZ():
                    c.f = speed
            c = c.getNext()

    #should probaby pass a positive value here since
    #zero will be where you start the job
    def setEvacuateHeight(self,height):
        if not height:
            raise ValueError("must pass a valid depth")
        c = self.getFirst()
        while c:
            if c.isEvacuation():
                c.z = height
            c = c.getNext()

    def setPenetrateSpeed(self,speed):
        if not speed:
            raise ValueError("must pass a valid speed")
        c = self.getFirst()
        while c:
            if c.isPenetrate():
                c.f = speed
            c = c.getNext()

    #should pass a negative number here
    #since zero will be where you start the job
    def setPenetrateDepth(self, depth):
        if not depth:
            raise ValueError("must pass a valid depth")
        if depth >= 0:
            depth = depth * -1

        c = self.getFirst()
        while c:
            if c.isPenetrate():
                c.z = depth
            c = c.getNext()

    def isCutCommand(self):
        return "G01" == self.getCommand() or "G02" == self.getCommand() or "G03" == self.getCommand()

    def isPenetrate(self) -> bool:
        if self.line and "Penetrate" in self.line:
            return True
        if self.comment and "Penetrate" in self.comment:
            return True
        if not self.z:
            return False
        ez = self.getEstimatedZ()
        if self.z > ez:
            return False
        if self.z < 0:
            return True
        return False
    
    def isEvacuation(self) -> bool:
        if self.isPenetrate():
            return False
        if not self.z:
            return False
        # TODO get estimated z and make sure this is higher
        return True

    def getFirst(self) -> 'GrblCommand':
        c = self
        while c:
            if not c.getPrevious():
                return c
            c = c.getPrevious()

    def getLast(self) -> 'GrblCommand':
        c = self
        while c:
            if not c.getNext():
                return c
            c = c.getNext()

    def getLength(self):
        c = self
        a = 0
        while c:
            a += 1
            c = c.getNext()
        return a

    def getIndex(self):
        ret = 0
        c = self
        while c:
            if c.getPrevious():
                ret = ret - 1
            else:
                return ret * -1
            c = c.getPrevious()
        return ret
    
    def getEstimated(self):
        stop = self.getIndex()
        ret = GrblCommand("")
        ret.x = 0.0
        ret.y = 0.0
        ret.z = 0.0
        ret.s = 1000.0
        ret.f = 100.0
        c = self.getFirst()
        while c and c.getIndex() < stop:
            if c.z: ret.z = c.z
            if c.x: ret.x = c.x
            if c.y: ret.y = c.y
            if c.f: ret.f = c.f
            if c.i: ret.i = c.i
            if c.j: ret.j = c.j
            if c.s: ret.s = c.s
            if c.n: ret.n = c.n
            if c.o: ret.o = c.o
            if c.p: ret.p = c.p
            c = c.getNext()
        return ret

    def getEstimatedZ(self):
        foo = self.getEstimated()
        return foo.z

    def getEstimatedX(self):
        foo = self.getEstimated()
        return foo.x

    def getEstimatedY(self):
        foo = self.getEstimated()
        return foo.y

    def getEstimatedF(self):
        foo = self.getEstimated()
        return foo.f

    def getAverage(self, c) -> 'GrblCommand':
        # TODO this
        if not c: raise ValueError("must pass a valid block")
        foo = c.getFirst()
        while foo:
            foo = foo.getNext()

    def getMaxX(self, c) -> float:
        pass
    def getMaxY(self, c) -> float:
        pass
    def getMaxZ(self, c) -> float:
        pass

    def sanitiseBlock(self, block) -> 'GrblCommand':
        if not block:
            raise ValueError("must supply block")
        ret = None
        c = block.getFirst()
        cutSpeedSet = False
        while c:
            #remove blank lines and comments
            if c.isBlank() or c.isComment():
                c = c.delete()
                continue
            if c.getIndex() == 0:
                if not c.x and not c.y:
                    raise ValueError("first command of a block must specify x and y? Is this a bug?")
                c.setCommand("G00")
                c.setF(GrblCommand.fast_travel_speed)
                ret = c
                c = c.getNext()
                continue
            elif c.getIndex() == 1:
                if not c.isPenetrate():
                    o = GrblCommand("G01 Z-0.0 F50")
                    o.z = GrblCommand.depth_step
                    o.f = GrblCommand.penetrate_speed
                    c = c.prependObject(o)
                    continue
                else:
                    c.z = GrblCommand.depth_step
            else:
                #remove all subsequent penetrate or evacuate commands 
                if c.z and not c.y and not c.x:
                    c = c.delete()
                    continue
                #remove all depth parameters following penetrate
                c.z = None
                
                if c.isCutCommand():
                    if not cutSpeedSet:
                        c.setF(GrblCommand.cut_speed)
                        cutSpeedSet = True
                    else:
                        c.f = None
            
            c = c.getNext()
        return ret
    
    def isMultiple(self):
        return self.getPrevious() or self.getNext()

    def isBlock(self):
        c = self.getFirst()
        while c:
            if not c.isInBlock():
                return False
            c = c.getNext()
        return True

    def generateHeader(self) -> 'GrblCommand':
        ret = GrblCommand("M03 S1000")
        ret.setS(GrblCommand.spindle_rpm)
        ret = ret.append("")
        ret = ret.append("G21")
        return ret

    def generateFooter(self) -> 'GrblCommand':
        ret: GrblCommand = GrblCommand("")
        ret = ret.append("M5")
        ret = ret.append("G00 X0.0000 Y0.0000 F600")
        ret = ret.append("G00 Z0.0")
        ret = ret.append("M2")
        return ret.getFirst()

    def generateEvacuationCommand(self):
        ret = []
        if GrblCommand.dwell_after_block:
            c = GrblCommand("G00 X0 Y0")
            c.f = GrblCommand.fast_travel_speed
            ret.append(c)
            ret.append(GrblCommand("G00 Z0"))
            ret.append(GrblCommand("G04 P10000"))
        else:
            c = GrblCommand("G00 Z1.0 F100")            
            c.z = GrblCommand.evacuation_height
            c.f = GrblCommand.fast_travel_speed
            return c
        return ret

    def appendBlock(self, block) -> 'GrblCommand':
        if not block or not block.isBlock():
            return self
        bl = block.__deepcopy__()
        ret = self.append(" ")
        c = bl.getFirst()
        while c:
            ret = ret.appendObject(c)
            c = c.getNext()
        return ret

    def getBlock(self, blockNum):
        if blockNum < 0:
            raise ValueError("blocks are a zero based array")
        blocks = self.getBlocks()
        bn = 0
        for b in blocks:
            if bn == blockNum:
                return b
            bn = bn + 1
        return None

    # returns all blocks as an array of command objects
    def getBlocks(self) -> List['GrblCommand']:
        c = self.getFirst()
        ret = []
        curr = None
        while c:
            if c.blockIndex > -1:
                o = c.__copy__()
                if curr:
                    curr = curr.appendObject(o)
                else:
                    curr = o
                    curr.block = len(ret)
                    curr.blockIndex = 0
                    ret.append(curr)
            else:
                curr = None
            c = c.getNext()
        # sanitize the blocks
        for b in ret:
            foo = self.sanitiseBlock(b)
            ret[foo.block] = foo
        return ret

    def sanitise(self) -> 'GrblCommand':
        ret: GrblCommand = self.generateHeader()
        blocks = self.getBlocks()
        if self.autoBlockSort:
            blocks = self.sortBlocks(blocks)
        for b in blocks:
            # ret = ret.append("")
            ret = ret.appendObjects(self.generateEvacuationCommand())
            ret = ret.appendBlock(b)
        ret = ret.append("")
        ret = ret.appendObjects(self.generateEvacuationCommand())
        ret = ret.appendObject(self.generateFooter())
        ret = ret.getFirst()
        return ret

    #removes every command which is not in a 'block'
    def deleteAllNonBlock(self):
        c = self.getFirst()
        while c:
            if not c.isInBlock():
                c = c.delete()
                continue
            if c.isBlockStart():
                c.prepend("")
            c = c.getNext()

    def getAt(self, index):
        c = self.getFirst()
        while c.getNext():
            if c.index == index:
                return c
            c = c.getNext()
        return None

    def removeAt(self, index):
        c = self.getAt(index)
        if not c:
            return
        # is this the last element in the list?
        if not c.getNext():
            if c.getPrevious():
                c.getPrevious().setNext(None)
            return
        # is it the first element?
        if not c.getPrevious():
            if c.getNext():
                c.getNext().setPrevious(None)
            return
        c.getPrevious().setNext(c.getNext())
        c.getNext().setPrevious(c.getPrevious())

    @staticmethod
    def removeBracketedText(text, brackets="()[]") -> str:
        count = [0] * (len(brackets) // 2)  # count open/close brackets
        saved_chars = []
        for character in text:
            for i, b in enumerate(brackets):
                if character == b:  # found bracket
                    kind, is_close = divmod(i, 2)
                    count[kind] += (-1) ** is_close  # `+1`: open, `-1`: close
                    if count[kind] < 0:  # unbalanced bracket
                        count[kind] = 0  # keep it
                    else:  # found bracket to remove
                        break
            else:  # character is not a [balanced] bracket
                if not any(count):  # outside brackets
                    saved_chars.append(character)
        return "".join(saved_chars)

    def isBlank(self):
        if (
            not self.command
            and not self.comment
            and not self.x
            and not self.y
            and not self.z
            and not self.f
            and not self.i
            and not self.j
            and not self.s
            and not self.n
            and not self.o
            and not self.p
        ):
            return True
        return False

    def makeBlank(self):
        self.command = None
        self.x = None
        self.y = None
        self.z = None
        self.f = None
        self.i = None
        self.j = None
        self.s = None
        self.n = None
        self.o = None
        self.p = None
        self.comment = None
        self.visible = True

    def isComment(self):
        if not self.command and self.comment:
            return True
        return False

    def setNext(self, n):
        self.next = n

    def setPrevious(self, p):
        self.previous = p
        if not p:
            return
        p.setNext(self)
        self.blockIndex = p.blockIndex
        self.block = p.block

        #are we in the middle of an ordinary block?
        if  self.isInBlock():
            self.blockIndex += 1
        if self.isBlockEnd():
            self.blockIndex = -1
        if self.isBlockStart():
            self.block += 1
            self.blockIndex = 0

    def getNext(self):
        return self.next

    def getPrevious(self):
        return self.previous

    def setVisibility(self, visibility):
        self.visible = visibility

    def setCommand(self, command):
        if not command:
            return
        first_char = command.strip()[0].upper()
        if not first_char:
            return
        if not first_char in "M G":
            raise ValueError("commands are M and G only")
        self.command = command

    def setMeta(self, meta):
        self.meta = meta

    def getMeta(self):
        return self.meta

    @staticmethod
    def stringToDouble(s) -> float:
        if not s:
            raise ValueError("must pass a valid string representation of a double")
        return float(s)

    def floatToStr(f, dp):
        foo = round(f,dp)
        float_string = repr(foo)
        if 'e' in float_string:  # detect scientific notation
            digits, exp = float_string.split('e')
            digits = digits.replace('.', '').replace('-', '')
            exp = int(exp)
            zero_padding = '0' * (abs(int(exp)) - 1) # minus 1 for decimal point in the sci notation
            sign = '-' if f < 0 else ''
            if exp > 0:
                float_string = '{}{}{}.0'.format(sign, digits, zero_padding)
            else:
                float_string = '{}0.{}{}'.format(sign, zero_padding, digits)
        return float_string

    @staticmethod
    def doubleToString(d, dp) -> str:
        if not d and 0.0 != d:
            return None
        if not dp and 0 != dp:
            raise ValueError("must supply a decimal format pattern")
        return str(round(d, dp))
    
    def getNearestBlock(self,blocks):
        if not blocks:
            raise ValueError("must supply some blocks")
        x = None
        y = None
        if self.isBlock():
            foo = self.getLast()
            if foo.x and foo.y:
                x = foo.x
                y = foo.y
            else:
                x = foo.getEstimatedX()
                y = foo.getEstimatedY()
        if not x or not y:
            if not self.x or not self.y:
                if 0.0 != self.x and 0.0 != self.y:
                    raise ValueError("can't compare self to blocks because I have no x or y coordinates")
            x = self.x
            y = self.y
        d = 1000000
        o = None
        for b in blocks:
            foo = b.getFirst()
            if not foo.x or not foo.y:
                raise ValueError("blocks contains something that doesn't seem to be a block")
            td = math.sqrt((x - foo.x) ** 2 + (y - foo.y) ** 2)
            if td < d:
                d = td
                o = foo
        return o

    def isSameBlock(self,other):
        if not self.isBlock():
            return self == other
        if not other.isBlock():
            return False
        return self.getFirst() == other.getFirst()

    # returns this command as an SVG Path fragment
    # prev x and y tell us where the tool is just before this command
    def toSvgPathFragment(self, ox, oy) -> str:
        # good path editor!
        # https://yqnn.github.io/svg-path-editor/
        # dilation: https://github.com/bbecquet/Leaflet.PolylineOffset/blob/master/leaflet.polylineoffset.js
        r = ""
        if not self.command: return r
        if not self.x and not self.y: return r

        if "G00" == self.command:
            r = r + " M " + str(self.x) + " " + str(self.y) + ", "
        elif "G01" == self.command:
            r = r + " L " + str(self.x) + " " + str(self.y) + ", "        
        
        if len(r) > 0: return r
        
        if "G02" == self.command:
            if not self.i and not self.j: raise ValueError("G02 has no i or j")
            r = r + " L " + str(ox) + " " + str(oy) + ", "
            # r = r + " A " + str(ox + self.i) + " " + str(ox + self.j) + " 0 0 0 " + str(self.x) + " " + str(self.y) + ", "
        elif "G03" == self.command:
            if not self.i and not self.j: raise ValueError("G02 has no i or j")
            r = r + " L " + str(ox) + " " + str(oy) + ", "
            # r = r + " A " + str(ox + self.i) + " " + str(ox + self.j) + " 0 0 0 " + str(self.x) + " " + str(self.y) + ", "
        return r

    def translateCoordinates(self, ox, oy, angle):
        if ox is None or oy is None or angle is None:
            return
        if self.x is not None and self.y is not None:
            a = math.radians(angle)
            rx = ox + math.cos(a) * (self.x - ox) - math.sin(a) * (self.y - oy)
            ry = oy + math.sin(a) * (self.x - ox) + math.cos(a) * (self.y - oy)
            # TODO allow for G02 and 3 commands where only i or j exist
            # or during sanitisation, put estimated x and y in there
            if self.i is not None and self.j is not None:
                # we must calculate the arc centre and then re-calculate the new arc centre
                ai = self.x + self.i
                aj = self.y + self.j
                ax = ox + math.cos(a) * (ai - ox) - math.sin(a) * (aj - oy)
                ay = oy + math.sin(a) * (ai - ox) + math.cos(a) * (aj - oy)
                self.i = ax - rx
                self.j = ay - ry

            self.x = rx
            self.y = ry

    def rotateBlock(self, angle, x, y, blockNum) -> 'GrblCommand':
        # TODO this
        if x is None or y is None or angle is None or blockNum is None:
            return
        block = self.getBlock(blockNum)
        if not block:
            return self.getFirst()

        blocks:GrblCommand = self.getBlocks()
        if not blocks or len(blocks) == 0:
            return
        ret = self.getHeader()
        for b in blocks:
            if blockNum == b.block:
                c = b.getFirst()
                while c:
                    c.translateCoordinates(x, y, angle)
                    c = c.getNext()
                foo = self.sanitiseBlock(c)
                ret = ret.appendBlock(foo)
            else:
                ret = ret.appendBlock(b)
        ret = ret.append(self.generateFooter())
        return ret

    # rotates the whole grbl file by the given angle (degrees)
    # about the given x y coordinates
    def rotate(self, angle, x, y):
        if x is None or y is None or angle is None:
            return
        if self.getPrevious() or self.getNext():
            c = self.getFirst()
            while c:
                c.translateCoordinates(x, y, angle)
                c = c.getNext()
        else:
            self.translateCoordinates(x, y, angle)
        return self.getFirst()


    # moves the whole file according to the x y coordinates
    # ie if x is -1 then the whole grbl file is moved 1 unit
    # left etc.
    def translate(self, x, y):
        if self.getPrevious() or self.getNext():
            c = self.getFirst()
            while c:
                if c.x is not None and x is not None:
                    c.x = c.x + x
                if c.y is not None and y is not None:
                    c.y = c.y + y
                c = c.getNext()
        else:
            if self.x is not None and x is not None:
                self.x = self.x + x
            if self.y is not None and y is not None:
                self.y = self.y + y
        return self

    def reverseBlocks(self) -> 'GrblCommand':
        blocks = self.getBlocks()
        if not blocks or len(blocks) == 0:
            raise ValueError("must supply blocks for sorting")
        blocks.reverse()
        ret = self.generateHeader()
        for b in blocks:
            ret = ret.appendObjects(self.generateEvacuationCommand())
            ret = ret.appendBlock(b)
        ret = ret.appendObject(self.generateFooter())
        ret = ret.getFirst()
        return ret

    # sorts blocks such that the first block is closest to 0,0 (cartesian coords)
    # and each subsequent block is closest to the block before it
    # TODO travelling salesman
    def sortBlocks(self, blocks) -> 'GrblCommand':
        if not blocks or len(blocks) == 0:
            raise ValueError("must supply blocks for sorting")
        ret = []
        #first element should be closest to zero
        tb = blocks
        comp = GrblCommand("G00 X0.0 Y0.0")
        for x in range(0, len(tb)):
            f = comp.getNearestBlock(tb)
            if not f:
                raise ValueError("failed to find the nearest block")
            ret.append(f)
            tb.remove(f)
            comp = f
        return ret

    def extrude(self,iterations,byblock):
        if not iterations:
            raise ValueError("must pass iterations number")
        ret = self.generateHeader()
        blocks = self.getBlocks()
        if GrblCommand.autoBlockSort:
            blocks = self.sortBlocks(blocks)
        
        depth = 0
        if not byblock:
            for x in range(0, iterations):
                depth = GrblCommand.depth_step + depth
                for b in blocks:
                    ret = ret.append("")
                    ret = ret.appendObjects(self.generateEvacuationCommand())
                    b.setPenetrateDepth(depth)
                    ret = ret.appendBlock(b)
                    ret = ret.append("")
        else:
            for b in blocks:
                depth = 0
                ret = ret.append("")
                ret = ret.appendObjects(self.generateEvacuationCommand())
                for x in range(0, iterations):
                    depth = GrblCommand.depth_step + depth
                    b.setPenetrateDepth(depth)
                    ret = ret.append("")
                    ret = ret.appendBlock(b)
                    ret = ret.append("")

        ret = ret.appendObjects(self.generateEvacuationCommand())
        ret = ret.appendObject(self.generateFooter())
        ret = ret.getFirst()
        return ret

    def toSVG(self):
        # online visualisation
        # https://www.freecodeformat.com/svg-editor.php
        px = 0
        py = 0
        #TODO generate header as a string with template values for width and height etc.
        ret = "<svg>"
        # for each 'path' (block) generate an SVG path object
        bret = ""
        bn = 0
        blocks = self.getBlocks()
        for b in blocks:
            bret = bret + "\n<path " + str(bn) + "=\""
            c = b.getFirst()
            while c:
                if not c.command: continue
                bret =  bret + c.toSvgPathFragment(px, py)
                if c.x: px = c.x
                if c.y: py = c.y
                c = c.getNext()
            bn += 1
            bret = bret + "\">\n"
            ret = ret + bret
        # create a footer
        # calculate image size etc. and adjust the header
        ret = ret + "<\/svg>"
        return ret

    def getCommand(self):
        return self.command

    def getX(self):
        return GrblCommand.floatToStr(self.x, self.max_dp)
        #return GrblCommand.doubleToString(self.x, self.max_dp)

    def setX(self, x):
        self.x = x

    def getY(self):
        return GrblCommand.floatToStr(self.y, self.max_dp)

    def getZ(self):
        return GrblCommand.floatToStr(self.z, self.max_dp)

    def setZ(self, z):
        self.z = z

    def getI(self):
        return GrblCommand.floatToStr(self.i, self.max_dp)

    def getJ(self):
        return GrblCommand.floatToStr(self.j, self.max_dp)

    def getF(self):
        return(str(int(self.f)))

    def setF(self, f):
        self.f = f

    def getS(self):
        return GrblCommand.floatToStr(self.s, self.max_dp)

    def setS(self, s):
        self.s = s
    
    def getP(self):
        return GrblCommand.floatToStr(self.p, self.max_dp)

    def setP(self, p):
        self.p = p

    @staticmethod
    def parseParameter(c):
        if not c:
            raise ValueError("cannot parse null value")
        foo = re.sub("[^0-9\\-\\.]", "", c)
        return GrblCommand.stringToDouble(foo)

    @staticmethod
    def isValidDouble(d):
        return d or 0.0 == d

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        # TODO N01 style line numbers
        if not self.visible:
            return ""
        if not self.command:
            if self.comment:
                return self.comment
            return ""

        ret = self.command

        if GrblCommand.isValidDouble(self.x):
            ret += " "
            ret += "X"
            ret += self.getX()

        if GrblCommand.isValidDouble(self.y):
            ret += " "
            ret += "Y"
            ret += self.getY()

        if GrblCommand.isValidDouble(self.z):
            ret += " "
            ret += "Z"
            ret += self.getZ()

        if GrblCommand.isValidDouble(self.i):
            ret += " "
            ret += "I"
            ret += self.getI()

        if GrblCommand.isValidDouble(self.j):
            ret += " "
            ret += "J"
            ret += self.getJ()

        if GrblCommand.isValidDouble(self.f):
            ret += " "
            ret += "F"
            ret += self.getF()

        if GrblCommand.isValidDouble(self.s):
            ret += " "
            ret += "S"
            ret += self.getS()

        if GrblCommand.isValidDouble(self.p):
            ret += " "
            ret += "P"
            ret += self.getP()

        return ret

    def getLine(self) -> str:
        # override this if necessary
        ret = ""
        if GrblCommand.showIndices:
            ret += str(self.getIndex())
            ret += " "
            ret += str(self.block)
            ret += " "
            ret += str(self.blockIndex)
            ret += " "

        if GrblCommand.auto_number_lines and not self.isBlank():
            ret += "N" + str(self.getIndex()) + " "
        
        if GrblCommand.auto_number_blocks and self.isBlockStart():
            ret += "O" + str(self.block) + " "

        ret += str(self)
        
        if self.isPenetrate():
            ret += " (Penetrate)"
        if self.isEvacuation():
            ret += " (Evacuate)"
        if self.isBlockStart():
            ret += " (block start)"
        if self.isBlockEnd():
            ret += " (block end)"
        ret += "\n"
        return ret

    def dump(self):
        ret = ""
        c = self.getFirst()
        if not c:
            raise Exception("no start node")
        while c:
            if c.visible:
                ret += self.getLine()
            c = c.getNext()
        return ret

    @staticmethod
    def fromSvg(inpath:str):
        curves = parse_file(inpath) # Parse an svg file into geometric curves
        gcode_compiler = Compiler(interfaces.Gcode, movement_speed=GrblCommand.fast_travel_speed, cutting_speed=GrblCommand.cut_speed, pass_depth=GrblCommand.depth_step * -1)
        gcode_compiler.append_curves(curves) 
        raw = gcode_compiler.compile(passes=1)
        #replace M5 with G00 Z1
        #replace G01 F800 with G00 F50 Z-0.35
        c = GrblCommand.slurp(raw)
        return c

    @staticmethod
    def slurpFile(inpath:str):
        f = open(inpath, "r")
        s = ""
        for line in f:
            s = s + line + "\n"
        f.close()
        return GrblCommand.slurp(s)

    @staticmethod
    def slurp(s:str):
        if not s: raise ValueError("must supply a valid GRBL string in lines delimited by newline character")
        ret = None
        for line in s.splitlines():
            c = GrblCommand(line)
            if not ret:
                ret = c
                continue
            ret = ret.append(line)
        return ret.getFirst()

    def burp(self,outpath:str):
        try:
            os.remove(outpath)
        except OSError:
            pass

        f = open(outpath, "a")
        try:
            c = self.getFirst()
            while c:
                s = c.getLine()
                f.write(s)
                c = c.getNext()
        finally:
            f.close()

    def burpBlock(self, blocknum:int, outpath:str):
        # TODO this
        pass

    def length(self) -> int:
        ret = 1
        if not self.start:
            return 0
        c = self.start
        while c:
            c = c.getNext()
            ret += 1
        return ret
    
    def __oc__(self,s,o):
        if s is None:
            if o is None:
                return True
            else:
                return False
        else:
            if o is None: return False
        if not isinstance(o, s.__class__):
            return False
        return o == s

    def __eq__(self,other):
        if not other:
            return False
        if not isinstance(other, self.__class__):
            return False
        if not self.__oc__(self.command,other.command): return False
        if not self.__oc__(self.x,other.x): return False
        if not self.__oc__(self.y,other.y): return False
        if not self.__oc__(self.z,other.z): return False
        if not self.__oc__(self.i,other.i): return False
        if not self.__oc__(self.j,other.j): return False
        if not self.__oc__(self.s,other.s): return False
        if not self.__oc__(self.f,other.f): return False
        if not self.__oc__(self.n,other.n): return False
        if not self.__oc__(self.o,other.o): return False
        if self.isBlock():
            if not other.isBlock(): return False
            if not self.__oc__(self.block,other.block): return False
            if not self.__oc__(self.blockIndex,other.blockIndex): return False
        else:
            if other.isBlock(): return False
        return True

    def __deepcopy__(self):
        if self.isMultiple():
            c = self.getFirst()
            ret = c.__copy__()
            while c:
                c = c.getNext()
                if c:
                    foo = c.__copy__()
                    ret = ret.appendObject(foo)
            return ret
        else:
            return self.__copy__()

    def __copy__(self):
        n = type(self)("")
        n.line = self.line
        n.command = self.command
        n.z = self.z
        n.x = self.x
        n.y = self.y
        n.s = self.s 
        n.f = self.f
        n.i = self.i
        n.j = self.j
        n.p = self.p
        return n

    @staticmethod
    def processGrbl(infile:str, outfile:str) -> 'GrblCommand':
        commands:GrblCommand = GrblCommand.slurpFile(infile)
        commands = commands.sanitise()
        commands.burp(outfile)
        return commands

class Processor():
    @staticmethod
    def processSvg(infile:str, outfile:str) -> GrblCommand:
        commands:GrblCommand = GrblCommand.fromSvg(infile)
        commands = commands.sanitise()
        commands.burp(outfile)
        return commands


#fname = "test"
#fname = "jolana_bevel_outline"
#fname = "jolana_holes"
#fname = "jolana_outline"
#fname = "jolana_holes"
fname = "a"
#testsvg = "jolana"
#fname = testsvg
dirname = "D:\.scripts\python\personal\GML"
infile = dirname + "\\" + fname + ".nc"
outfile = dirname + "\\" + fname + "_" + ".nc"


GrblCommand.showIndices = False
GrblCommand.depth_step = -0.35
GrblCommand.evacuation_height = 1
GrblCommand.fast_travel_speed = 800
GrblCommand.cut_speed = 80
GrblCommand.autoBlockSort = True
GrblCommand.dwell_after_block = False

GrblCommand.auto_number_lines = False
GrblCommand.auto_number_blocks = False
foo = GrblCommand.processGrbl(infile, outfile)
foo = foo.extrude(3, True)
foo.burp(outfile)
#Processor.processSvg(dirname + "\\a.svg", dirname + "\\a.gcode")