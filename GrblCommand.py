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
    order = ["O", "N", "G", "M", "X", "Y", "Z", "H", "I", "J", "K", "L", "A", "B", "C", "D", "E", "P", "Q", "R", "S", "T", "U", "V", "W", "F"]
    # Enable O02 style line numbering of blocks of commands
    auto_number_blocks: bool = False
    # Enable N02 style line numbering
    auto_number_lines: bool = False
    # automatically sanitise GCODE into blocks
    auto_sanitise: bool = True
    auto_decurve: bool = False
    # return to zero and dwell after every path
    dwell_after_block: bool = False
    tool_diameter: float = 1.0
    depth_step: float = -0.25
    evacuation_height: float = 1
    cut_speed: int = 50
    spindle_rpm: int = 1000
    fast_travel_speed: int = 800
    showIndices = False
    autoBlockSort = True
    penetrate_speed: int = 50
    max_dp = 4
    vals = None
    next = previous = None
    line = None
    inComment = False
    visible = True
    meta = None
    block = 0
    blockIndex = -1

    def __init__(self, line: str):
        self.line = line
        self.vals = GrblCommand.getBlankValuesDictionary(None)

        if not line:
            # permit blank objects
            return

        if line.strip().startswith("("):
            self.vals["COMMENT"] = line
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

            if first_char == "(":
                self.inComment = True
            else:
                self.vals[first_char] = GrblCommand.parseParameter(c)

    @staticmethod
    def getBlankValuesDictionary(i: any) -> dict:
        return {
            "A": i, "B": i, "C": i, "D": i, "E": i,
            "F": i, "G": i, "H": i, "I": i, "J": i,
            "K": i, "L": i, "M": i, "N": i, "O": i,
            "P": i, "Q": i, "R": i, "S": i, "T": i,
            "U": i, "V": i, "W": i, "X": i, "Y": i,
            "Z": i, "COMMENT": None
        }

    def getRawLine(self) -> str:
        return self.line

    def prependObject(self, obj) -> 'GrblCommand':
        if not obj:
            raise ValueError("must pass valid object")
        if self.getPrevious():
            obj.setPrevious(self.getPrevious())
        self.setPrevious(obj)
        return obj

    def prepend(self, line: str) -> 'GrblCommand':
        c = GrblCommand(line)
        return self.prependObject(c)

    def insertObjectAfter(self, obj) -> 'GrblCommand':
        if not obj: return self
        n = self.getNext()
        obj.setPrevious(self)
        if n:
            obj.setNext(n)
        return obj

    # add a single command, or a list of commands
    def appendObjects(self, obj) -> 'GrblCommand':
        if not obj: return None
        if not isinstance(obj, list): return self.appendObject(obj)
        lo = None
        for o in obj:
            if not lo: 
                lo = self.appendObject(o)
            else:
                lo = lo.appendObject(o)
        return lo

    def appendObject(self, obj) -> 'GrblCommand':
        if not obj: return self
        obj.setPrevious(self)
        return obj

    def append(self, line: str) -> 'GrblCommand':
        c = GrblCommand(line)
        return self.appendObject(c)

    def delete(self) -> 'GrblCommand':
        if self.getPrevious():
            self.getPrevious().setNext(self.getNext())
        if self.getNext():
            self.getNext().setPrevious(self.getPrevious())
        if self.getPrevious():
            return self.getPrevious()
        elif self.getNext():
            return self.getNext()
        return None

    def isInBlock(self) -> bool:
        return self.blockIndex > -1

    def isBlockStart(self) -> bool:
        c = self.getCommand()
        x = self.getX()
        y = self.getY()
        if not self.getX() or not self.getY():
            return False
        if self.isCommand("G00"):
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
            if self.isCommand("G00"):
                return True
            # stop spindle indicates block end (mainly lasers)
            if self.isCommand("M05"):
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

    # sets the feed rate of all commands which operate at a
    # depth less than or equal zero
    def setCutSpeed(self, speed):
        if not speed:
            raise ValueError("must pass a valid depth")
        c = self.getFirst()
        while c:
            if c.isPenetrate():
                c = c.getNext()
                continue
            if c.z:
                if 0 >= c.getZ():
                    c.setF(speed)
            else:
                if 0 >= c.getEstimatedZ():
                    c.setF(speed)
            c = c.getNext()

    # sets the feed rate of all commands which operate at a
    # depth greater than or equal zero
    def setFastTravelSpeed(self, speed):
        if not speed:
            raise ValueError("must pass a valid speed and height")
        c = self.getFirst()
        while c:
            if c.nn("Z"):
                if 0 <= c.getZ():
                    c.setF(speed)
            else:
                if 0 <= c.getEstimatedZ():
                    c.setF(speed)
            c = c.getNext()

    # should probaby pass a positive value here since
    # zero will be where you start the job
    def setEvacuateHeight(self,height):
        if not height:
            raise ValueError("must pass a valid depth")
        c = self.getFirst()
        while c:
            if c.isEvacuation():
                c.setZ(height)
            c = c.getNext()

    def setPenetrateSpeed(self,speed):
        if not speed:
            raise ValueError("must pass a valid speed")
        c = self.getFirst()
        while c:
            if c.isPenetrate():
                c.setF(speed)
            c = c.getNext()

    # should pass a negative number here
    # since zero will be where you start the job
    def setPenetrateDepth(self, depth):
        if not depth:
            raise ValueError("must pass a valid depth")
        if depth >= 0:
            depth = depth * -1

        c = self.getFirst()
        while c:
            if c.isPenetrate():
                c.setZ(depth)
            c = c.getNext()

    def isCutCommand(self):
        return self.isCommand("G01") or self.isCommand("G02") or self.isCommand("G03")

    def isPenetrate(self) -> bool:
        if self.line and "Penetrate" in self.line:
            return True
        if self.vals["COMMENT"] and "Penetrate" in self.vals["COMMENT"]:
            return True
        if not self.getZ() and 0 != self.getZ():
            return False
        ez = self.getEstimatedZ()
        if self.getZ() > ez:
            return False
        if self.getZ() < 0:
            return True
        return False
    
    def isEvacuation(self) -> bool:
        if self.isPenetrate():
            return False
        if not self.getZ():
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

    def getLength(self) -> int:
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

    def getEstimated(self) -> 'GrblCommand':
        try:
            stop = self.getIndex()
            ret = GrblCommand("")
            c = self.getFirst()
            while c and c.getIndex() < stop:
                for l in c.vals:
                    if c.nn(l):
                        ret.vals[l] = c.vals[l]
                c = c.getNext()
            return ret
        except:
            return None

    def getEstimatedZ(self):
        foo = self.getEstimated()
        if GrblCommand.isNone(foo) or (not foo.nn('Z')): return 0.0
        return foo.getZ()

    def getEstimatedX(self):
        foo = self.getEstimated()
        if GrblCommand.isNone(foo) or (not foo.nn('Z')): return 0.0
        return foo.getX()

    def getEstimatedY(self):
        foo = self.getEstimated()
        if GrblCommand.isNone(foo) or (not foo.nn('Z')): return 0.0
        return foo.getY()

    def getEstimatedF(self):
        foo = self.getEstimated()
        if GrblCommand.isNone(foo) or (not foo.nn('Z')): return GrblCommand.cut_speed
        return foo.getF()

    def getAverage(self) -> 'GrblCommand':
        # TODO this
        count = GrblCommand.getBlankValuesDictionary(0)
        sum = GrblCommand.getBlankValuesDictionary(0.0)
        sumn = GrblCommand.getBlankValuesDictionary(0.0)
        ret = GrblCommand.getBlankValuesDictionary(None)
        c = self.getFirst()
        while c:
            for l in c.vals:
                if c.nn(l):
                    v = c.vals[l]
                    count[l] = count[l] + 1
                    if v < 0:
                        sumn[l] = sumn[l] + v
                    else:
                        sum[l] = sum[l] + v
            c = c.getNext()

        for l in count:
            if not GrblCommand.isNone(count[l]) and count[l] > 0:
                sum[l] = sum[l] - sumn[l]
                ret[l] = sum[l] / count[l]
        return ret

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
            # remove blank lines and comments
            if c.isBlank() or c.isComment():
                c = c.delete()
                continue
            if c.getIndex() == 0:
                if not c.getX() and not c.getY():
                    raise ValueError("first command of a block must specify x and y? Is this a bug?")
                c.setCommand("G00")
                c.setF(GrblCommand.fast_travel_speed)
                ret = c
                c = c.getNext()
                continue
            elif c.getIndex() == 1:
                if not c.isPenetrate():
                    o = GrblCommand("G01 Z-0.0 F50")
                    o.setZ(GrblCommand.depth_step)
                    o.setF(GrblCommand.penetrate_speed)
                    c = c.prependObject(o)
                    continue
                else:
                    c.setZ(GrblCommand.depth_step)
            else:
                # remove all subsequent penetrate or evacuate commands 
                if c.getZ() and not c.getY() and not c.getX():
                    c = c.delete()
                    continue
                # remove all depth parameters following penetrate
                c.setZ(None)

                if c.isCutCommand():
                    if not cutSpeedSet:
                        c.setF(GrblCommand.cut_speed)
                        cutSpeedSet = True
                    else:
                        c.setF(None)

                if c.nn("I") and c.nn("J") and GrblCommand.auto_decurve:
                    # TODO interpolate points in the curve
                    c.setCommand("G01")
                    c.setI(None)
                    c.setJ(None)

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
            c.setZ(GrblCommand.evacuation_height)
            c.setF(GrblCommand.fast_travel_speed)
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

    # returns true if the given block represents a closed path
    # that is, it's start and end point are the same (within tolerance)
    def isBlockAClosedPath(self, blocknum: int) -> bool:
        b = self.getBlock(blocknum)
        if not b: return False
        c = b.getFirst()
        fx = fy = lx = ly = None
        while c:
            if c.nn("X"):
                if GrblCommand.isNone(fx):
                    fx = c.getX()
                    fy = c.getY()
                else:
                    lx = c.getX()
                    ly = c.getY()
            c = c.getNext()
        if GrblCommand.isNone(lx): return False
        return (abs(lx - fx) < 0.05) and (abs(ly - fy) < 0.05)

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

    #gets just the block data without any homing etc.
    def getRawBlocks(self) -> 'GrblCommand':
        foo = self.__deepcopy__()
        foo.deleteAllNonBlock()
        return foo.getFirst()

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
        for l in self.vals:
            if self.nn(l):
                return False
        return True

    def removeArc(self):
        if "G02" != self.getCommand() and "G03" != self.getCommand():
            return
        self.setCommand("G01")
        self.setI(None)
        self.setJ(None)

    def makeBlank(self):
        self.vals = GrblCommand.getBlankValuesDictionary(None)
        self.visible = True

    def isComment(self):
        if not self.getCommand() and self.vals["COMMENT"]:
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

        # are we in the middle of an ordinary block?
        if self.isInBlock():
            self.blockIndex += 1
        if self.isBlockEnd():
            self.blockIndex = -1
        if self.isBlockStart():
            self.block += 1
            self.blockIndex = 0

    def getNext(self):
        return self.next

    def getPreviousCoordinates(self) -> 'GrblCommand':
        if not self.getPrevious(): return None
        c = self.getPrevoius()
        while c:
            if c.nn("X"): return c
            c = c.getPrevious()
        return None

    def getPrevious(self):
        return self.previous

    def setVisibility(self, visibility):
        self.visible = visibility

    def setCommand(self, command):
        if not command:
            return
        first_char = command.strip()[0].upper()
        if not first_char: return
        if not first_char in "M G":
            raise ValueError("commands are M and G only")
        self.vals[first_char] = GrblCommand.parseParameter(command)

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
        foo = round(f, dp)
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

    def getNearestBlock(self, blocks):
        if not blocks:
            raise ValueError("must supply some blocks")
        x = None
        y = None
        if self.isBlock():
            foo = self.getLast()
            if foo.getX() and foo.getY():
                x = foo.getX()
                y = foo.getY()
            else:
                x = foo.getEstimatedX()
                y = foo.getEstimatedY()
        if not x or not y:
            if not self.getX() or not self.getY():
                if 0.0 != self.getX() and 0.0 != self.getY():
                    raise ValueError("can't compare self to blocks because I have no x or y coordinates")
            x = self.getX()
            y = self.getY()
        d = 1000000
        o = None
        for b in blocks:
            foo = b.getFirst()
            if not foo.getX() or not foo.getY():
                raise ValueError("blocks contains something that doesn't seem to be a block")
            td = math.sqrt((x - foo.getX()) ** 2 + (y - foo.getY()) ** 2)
            if td < d:
                d = td
                o = foo
        return o

    def isSameBlock(self, other):
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
        if not self.getCommand(): return r
        if not self.getX() and not self.getY(): return r

        if self.isCommand("G00"):
            r = r + " M " + str(self.getX()) + " " + str(self.getY()) + ", "
        elif self.isCommand("G01"):
            r = r + " L " + str(self.getX()) + " " + str(self.getY()) + ", "
        
        if len(r) > 0: return r
        
        if self.isCommand("G02"):
            if not self.getI() and not self.getJ(): raise ValueError("G02 has no i or j")
            r = r + " L " + str(ox) + " " + str(oy) + ", "
        elif self.isCommand("G03"):
            if not self.getI() and not self.getJ(): raise ValueError("G02 has no i or j")
            r = r + " L " + str(ox) + " " + str(oy) + ", "
        return r

    def translateCoordinates(self, ox, oy, angle):
        if GrblCommand.isNone(ox) or GrblCommand.isNone(oy) or GrblCommand.isNone(angle):
            return
        if self.nn('X') and self.nn('Y'):
            a = math.radians(angle)
            rx = ox + math.cos(a) * (self.getX() - ox) - math.sin(a) * (self.getY() - oy)
            ry = oy + math.sin(a) * (self.getX() - ox) + math.cos(a) * (self.getY() - oy)
            # TODO allow for G02 and 3 commands where only i or j exist
            # or during sanitisation, put estimated x and y in there
            if self.nn("I") and self.nn("J"):
                # we must calculate the arc centre and then re-calculate the new arc centre
                ai = self.getX() + self.getI()
                aj = self.getY() + self.getJ()
                ax = ox + math.cos(a) * (ai - ox) - math.sin(a) * (aj - oy)
                ay = oy + math.sin(a) * (ai - ox) + math.cos(a) * (aj - oy)
                self.setI(ax - rx)
                self.setJ(ay - ry)
            self.setX(rx)
            self.setY(ry)

    def rotateBlock(self, angle, x, y, blockNum) -> 'GrblCommand':
        # TODO this
        if GrblCommand.isNone(y) or GrblCommand.isNone(angle) or GrblCommand.isNone(blockNum):
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
        if GrblCommand.isNone(x) or GrblCommand.isNone(y) or GrblCommand.isNone(angle):
            return
        if self.getPrevious() or self.getNext():
            c = self.getFirst()
            while c:
                c.translateCoordinates(x, y, angle)
                c = c.getNext()
        else:
            self.translateCoordinates(x, y, angle)
        return self.getFirst()

    def getNewDilatePoint(self, units: float, cx: float, cy: float) -> 'GrblCommand':
        if not self.nn("X") or not self.nn("Y"):
            return self
        nx = cx + ((self.getX() - cx) * units)
        ny = cy + ((self.getY() - cy) * units)
        if self.nn("I") and self.nn("J"):
            self.setI(nx - ((self.getX() - self.getI()) * units))
            self.setJ(ny - ((self.getY() - self.getJ()) * units))
        self.setX(nx)
        self.setY(ny)

    def dilate(self, units: float, centreX: float, centreY: float) -> 'GrblCommand':
        # dilate algorithm : Tiller and Hanson
        c = self.getFirst()
        f = c
        while c:
            c.getNewDilatePoint(units, centreX, centreY)
            c = c.getNext()
        return f

    # converts curves (G02,G03) into a set of points (G01) 
    # that describe the same curve, based on
    # the current tool diameter and other constants
    # also replaces points that are very close with single points
    @staticmethod
    def pointify(c) -> 'GrblCommand':
        if c is None: raise ValueError("Must pass a valid curve command")
        p = c.getPreviousCoordinates()
        if "G02" != c.getCommand() and "G03" != c.getCommand(): 
            if "G01" != c.getCommand(): return c
            # TODO remove points close together
            return c
        if not p: raise ValueError("found a curve with no start coordinates!?")
        radius = math.sqrt(((c.getX() - (c.getX() - c.getI())) ** 2) + ((c.getY() - (c.getY() - c.getJ())) ** 2))
        chord = math.sqrt(((c.getX() - p.getX()) ** 2) + ((c.getY() - p.getY()) ** 2))
        theta = math.acos(1 - ((chord ** 2) / (2 * (radius ** 2))))
        arclen = radius * theta
        if arclen < GrblCommand.tool_diameter or chord < GrblCommand.tool_diameter:
            c.removeArc()
            return c
        subarcs = arclen / GrblCommand.tool_diameter
        sumarcs = subarcs
        while sumarcs < (arclen - subarcs):
            # calculate interim XY
            sumarcs += subarcs

    def offset(self, offs: float) -> 'GrblCommand':
        copy = self.__deepcopy__()
        c = copy.getFirst()
        if not c.getNext(): return c
        f = c
        x1 = x2 = y1 = y1 = None
        while c:
            if not c.nn("X") or not c.nn("Y"): 
                c = c.getNext()
                continue
            if c.nn("I"):
                # TODO not this!
                c.removeArc()
            if GrblCommand.isNone(x1):
                x1 = c.getX()
                y1 = c.getY()
                c = c.getNext()
                continue
            elif GrblCommand.isNone(x2):
                x2 = c.getX()
                y2 = c.getY()
            # tangential slope approximation
            try:
                slope = (y2 - y1) / (x2 - x1)
                # perpendicular slope
                pslope = -1/slope  # (might be 1/slope depending on direction of travel)
            except ZeroDivisionError:
                x2 = y2 = None
                c = c.getNext()
                continue
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2

            sign = ((pslope > 0) == (x1 > x2)) * 2 - 1
            delta_x = sign * offs / ((1 + pslope**2)**0.5)
            delta_y = pslope * delta_x
            nx = mid_x + delta_x
            ny = mid_y + delta_y

            if c.nn("I"):
                # TODO recalculate arcs and curves based on new X,Y point!
                pass

            # points.append((mid_x + delta_x, mid_y + delta_y))
            c.setX(nx)
            c.setY(ny)
            x1, y1 = x2, y2
            x2 = y2 = None
            c = c.getNext()
        # append a last coordinate to close the path
        return f

    def scale(self, units: float) -> 'GrblCommand':
        c = self.getFirst()
        f = c
        while c:
            nx = None
            ny = None
            if c.nn("X") and c.nn("Y"):
                nx = (c.getX() * units)
                ny = (c.getY() * units)
                if c.nn("I") and c.nn("J"):
                    c.setI(nx - ((c.getX() - c.getI()) * units))
                    c.setJ(ny - ((c.getY() - c.getJ()) * units))
            if nx: c.setX(nx)
            if ny: c.setY(ny)
            c = c.getNext()
        return f

    # moves the whole file according to the x y coordinates
    # ie if x is -1 then the whole grbl file is moved 1 unit
    # left etc.
    def translate(self, x, y) -> 'GrblCommand':
        if self.getPrevious() or self.getNext():
            c = self.getFirst()
            while c:
                if c.nn("X"):
                    c.setX(c.getX() + x)
                if c.nn("Y"):
                    c.setY(c.getY() + y)
                c = c.getNext()
        else:
            if self.nn("X"):
                self.setX(self.getX() + x)
            if self.nn("Y"):
                self.setY(self.getY() + y)
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

    def extrude(self, iterations, byblock):
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
        # TODO generate header as a string with template values for width and height etc.
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

    def isCommand(self, command: str) -> bool:
        c = self.getCommand()
        if not c or not command: return False
        return command == c

    def getCommand(self):
        if not self.isNone("G"):
            return "G" + str(self.vals['G']).zfill(2)
        if not self.isNone("M"):
            return 'M' + str(self.vals['M']).zfill(2)
        return None

    def getLargestXY(self):
        c = self.getFirst()
        x = 0
        y = 0
        while c:
            if c.getX() and abs(x) < abs(c.getX()):
                x = c.getX()
            if c.getY() and abs(y) < abs(c.getY()):
                y = c.getY()
            c = c.getNext()
        return {"x": x, "y": y}

    def getFirstContactPoint(self) -> 'GrblCommand':
        c = self.getFirst()
        while c:
            if self.isCommand("G00"):
                return c
        return None

    def getParameterAsString(self, paramname: str) -> any:
        ret = self.vals[paramname]
        if ret is None and (0 != ret): return None
        if isinstance(ret, float):
            return GrblCommand.floatToStr(self.vals[paramname], GrblCommand.max_dp)
        elif isinstance(ret, int):
            return str(ret).zfill(2)
        else:
            return str(ret)

    @staticmethod
    def isNone(obj: any) -> bool:
        # pfft
        return (obj is None and (0 != obj))

    # Return true if the given parameter exists and is not null
    def nn(self, param: str) -> bool:
        ret = self.vals[param]
        return not GrblCommand.isNone(ret)

    def getComment(self): return self.vals["COMMENT"]
    def setComment(self, comment: str): self.vals["COMMENT"] = comment
    def getX(self): return self.vals["X"]
    def setX(self, x: float): self.vals["X"] = x
    def getStrX(self): return self.getParamAsString("X")
    def getY(self): return self.vals["Y"]
    def setY(self, y: float): self.vals["Y"] = y
    def getStrY(self): return self.getParamAsString("Y")
    def getZ(self): return self.vals["Z"]
    def setZ(self, z: float): self.vals["Z"] = z
    def getStrZ(self): return self.getParamAsString("Z")
    def getI(self): return self.vals["I"]
    def setI(self, i: float): self.vals["I"] = i
    def getStrI(self): return self.getParamAsString("I")
    def getJ(self): return self.vals["J"]
    def setJ(self, j: float): self.vals["J"] = j
    def getStrJ(self): return self.getParamAsString("J")
    def getF(self): return self.vals["F"]
    def setF(self, f: float): self.vals["F"] = f
    def getStrF(self): return self.getParamAsString("F")
    def getS(self): return self.vals["S"]
    def setS(self, s: float): self.vals["S"] = s
    def getStrS(self): return self.getParamAsString("S")
    def getP(self): return self.vals["P"]
    def setP(self, p: float): self.vals["P"] = p
    def getStrP(self): return self.getParamAsString("P")

    @staticmethod
    def parseParameter(c: str) -> any:
        if not c:
            raise ValueError("cannot parse null value")
        foo = re.sub("[^0-9\\-\\.]", "", c)
        if foo:
            if "." in foo:
                return GrblCommand.stringToDouble(foo)
            else:
                return int(foo)
        else:
            return c

    @staticmethod
    def isValidDouble(d):
        return d or 0.0 == d

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        ret = ""
        if not self.visible:
            return ret

        if not self.getCommand():
            if self.getComment():
                return self.getComment()
            return ""

        for o in GrblCommand.order:
            if self.nn(o):
                p = self.getParameterAsString(o)
                if len(ret) == 0:
                    ret = ret + o + p
                else:
                    ret = ret + " " + o + p
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
    def fromSvg(inpath: str):
        curves = parse_file(inpath) # Parse an svg file into geometric curves
        gcode_compiler = Compiler(interfaces.Gcode, movement_speed=GrblCommand.fast_travel_speed, cutting_speed=GrblCommand.cut_speed, pass_depth=GrblCommand.depth_step * -1)
        gcode_compiler.append_curves(curves) 
        raw = gcode_compiler.compile(passes=1)
        # replace M5 with G00 Z1
        # replace G01 F800 with G00 F50 Z-0.35
        c = GrblCommand.slurp(raw)
        return c

    @staticmethod
    def slurpFile(inpath: str):
        f = open(inpath, "r")
        s = ""
        for line in f:
            s = s + line + "\n"
        f.close()
        return GrblCommand.slurp(s)

    @staticmethod
    def slurp(s: str):
        if not s: raise ValueError("must supply a valid GRBL string in lines delimited by newline character")
        ret = None
        for line in s.splitlines():
            c = GrblCommand(line)
            if not ret:
                ret = c
                continue
            ret = ret.appendObject(c)
        return ret.getFirst()

    def burp(self, outpath: str):
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
    
    def __oc__(self, s, o):
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

    def __eq__(self, other):
        if not other:
            return False

        if not isinstance(other, self.__class__):
            return False

        if not self.__oc__(self.vals, other.vals): return False
        if self.isBlock():
            if not other.isBlock(): return False
            if not self.__oc__(self.block, other.block): return False
            if not self.__oc__(self.blockIndex, other.blockIndex): return False
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
        n.vals = self.vals.copy()
        n.line = self.line
        n.block = self.block
        n.blockIndex = self.blockIndex
        return n

    @staticmethod
    def processGrbl(infile: str, outfile: str) -> 'GrblCommand':
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
# fname = "jolana_bevel_outline"
#fname = "jolana_holes"
#fname = "jolana_outline"
#fname = "jolana_holes"
# fname = "test"
#testsvg = "jolana"
#fname = testsvg
fname = "a"
dirname = "D:\.scripts\python\personal\GML"
infile = dirname + "\\" + fname + ".nc"
outfile = dirname + "\\" + fname + "_" + ".nc"

GrblCommand.showIndices = False
GrblCommand.depth_step = -0.35
GrblCommand.evacuation_height = 1
GrblCommand.fast_travel_speed = 800
GrblCommand.cut_speed = 150
GrblCommand.autoBlockSort = True
GrblCommand.dwell_after_block = False
GrblCommand.auto_number_lines = False
GrblCommand.auto_number_blocks = False
GrblCommand.auto_decurve = False

foo = GrblCommand.processGrbl(infile, outfile)
#foo = foo.offset(-0.5)
foo.burp(outfile)
#Processor.processSvg(dirname + "\\a.svg", dirname + "\\a.gcode")