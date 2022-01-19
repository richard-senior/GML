import re
import types
from ply import lex, yacc

# Comprensive list of GRBL codes with descriptions, and matching regex etc.
# Used primarily with python PLY (Python Lex/Yacc) in order to create a rudimentary system
# for parsing and creating GRBL routines.

#LinuxCNC Definition
#https://linuxcnc.org/docs/html/gcode/overview.html

# potential yacc clarity :
# https://blog.emptyq.net/a?ID=00004-e785af2d-906b-46df-9062-22d0bae88f57
# some stuff I don't understand here :
# https://grass.osgeo.org/grass80/manuals/libpython/_modules/temporal/temporal_algebra.html
# a decent java dev does python PLY!! : https://www.programcreek.com/python/?code=wemake-services%2Fdotenv-linter%2Fdotenv-linter-master%2Fdotenv_linter%2Fgrammar%2Flexer.py

class GrblCode:
    def __init__(self, description: str, name: str, regex: str, lregex: str, allowedParams: str):
        self.allowedParams = allowedParams
        self.description = description
        self.name = name.upper()
        # this regex will find tokens in an entire source file
        self.regex = re.compile(regex)
        self.lregex = re.compile(lregex)

    # define a static factory method here
    def isCode(self, code: str) -> bool:
        if self.regex.match(" " + code + " "):
            return True
        else:
            return False

    # returns the source code (in the form of a string) that can be used as a 'rule' function
    # in lex. That is, a function which can find and validate tokens in the input string.
    # these rules have to be named t_TOKEN where TOKEN is the name of one of the tokens you
    # defined in the 'tokens' global variable. The tokens array and these rules are found
    # by PLY using introspection at runtime. Any decending classes can alter this method
    # to return a different lex rule function if required
    def lexFunctionSource(self) -> str:
        foo = ""
        foo = foo + "def t_" + self.name + "(t):\n"
        foo = foo + "   r'" + self.lregex.pattern + "'\n"
        foo = foo + "   t.value = t.value.strip()\n"
        # foo = foo + "   print(t.type)\n"
        foo = foo + "   return t"
        return foo

class LetterCode(GrblCode):
    def __init__(self, desc: str, letter: str, allowedParams: str):
        if not letter: raise ValueError("must supply a valid letter")
        self.type = letter.upper()
        # regex should allow floating point numbers
        reg = r"\s+[" + letter.upper() + letter.lower() + r"]{1}([0-9\.+-]+)\s+"
        lreg = r"[" + letter.upper() + letter.lower() + r"]{1}([0-9\.+-]+)"
        super().__init__(desc, letter.upper(), reg, lreg, allowedParams)

    def getValue(self, code: str) -> str:
        if not self.isCode(code): raise ValueError("the supplied code in string form (" + str(code) +") is not of type " + self.name)
        m = self.regex.match(" " + code + " ")
        if not m:
            return None
        foo = m.group(1)
        if not foo:
            return None
        else:
            return foo

    def getFloatValue(self, code: str) -> float:
        v = self.getValue(code)
        try:
            ret = float(v)
            return ret
        except:
            raise ValueError("The value of the Letter Code " + code + " is not an floating point number")

    def getIntValue(self, code: str) -> int:
        v = self.getValue(code)
        try:
            ret = int(v)
            return ret
        except:
            raise ValueError("The value of the Letter Code " + code + " is not an integer")
    
    # overridden abstract method from parent class
    # will find and validate letter codes
    def lexFunctionSource(self) -> str:
        foo = ""
        foo = foo + "def t_" + self.name + "(t):\n"
        foo = foo + "   r'" + self.lregex.pattern + "'\n"
        foo = foo + "   t.value = t.value[1:]\n"
        foo = foo + "   return t"
        return foo


class GMCode(GrblCode):
    def __init__(self, desc: str, morg: str, num: int, allowedParams: str):
        if num < 0 or num > 999:
            raise ValueError("G COdes must be between zero and 999")
        self.value = num
        self.type = morg.upper()
        name = self.type + str(num).zfill(2)
        reg = r"\s+[" + morg.upper() + morg.lower() + r"]0*(" + str(num) + r")\s+"
        if num == 0:
            lreg = r"[" + morg.upper() + morg.lower() + r"]0*"
        else:
            lreg = r"[" + morg.upper() + morg.lower() + r"]0*?" + str(num)
        super().__init__(desc, name, reg, lreg, allowedParams)


class CommentCode(GrblCode):
    def __init__(self):
        reg = r"\s*\([^\)]*\)\s*"
        lreg = r"\([^\)]*\)"
        super().__init__("comment", "COMMENT", reg, lreg, None)
 
    def lexFunctionSource(self) -> str:
        foo = ""
        foo = foo + "def t_" + self.name + "(t):\n"
        foo = foo + "   r'" + self.lregex.pattern + "'\n"
        foo = foo + "   t.value = t.value.replace('(','').replace(')','').strip()\n"
        foo = foo + "   return t"
        return foo

class Codes:
    gcodes = [
        GMCode('Rapid Positioning', 'G', 0, "XYZFHES"),
        GMCode('Linear Interpolation', 'G', 1, "XYZFHES"),
        GMCode('Circular Interpolation CW', 'G', 2, "XYZEFHIJKRS"),
        GMCode('Circular Interpolation ACW', 'G', 3, "XYZEFHIJKRS"),
        GMCode('Dwell', 'G', 4, "PS"),
        GMCode('Contour Control', 'G', 5, ""),
        GMCode('B-Spline', 'G', 6, "ABCR"),
        GMCode('Imaginary Axis Designation', 'G', 7,""),
        GMCode('Unused', 'G', 8,""),
        GMCode('Exact Stop Check', 'G', 9,""),
        GMCode('Set Origin (See L Command)', 'G', 10,""),
        GMCode('Data Write Cancel', 'G', 11, ""),
        GMCode('Circular Pocket CW', 'G', 12, ""),
        GMCode('Circular Pocket ACW', 'G', 13, ""),
        GMCode('Unused', 'G', 14, ""),
        GMCode('Unused', 'G', 15, ""),
        GMCode('Unused', 'G', 16, ""),
        GMCode('XY Plane Selection', 'G', 17, ""),
        GMCode('ZX Plane Selection', 'G', 18, ""),
        GMCode('YZ Plane Selection', 'G', 19, ""),
        GMCode('Decimal Imperial (pfft)', 'G', 20, ""),
        GMCode('mm', 'G', 21, ""),
        GMCode('Unused', 'G', 22, ""),
        GMCode('Unused', 'G', 23, ""),
        GMCode('Unused', 'G', 24, ""),
        GMCode('Unused', 'G', 25, ""),
        GMCode('Unused', 'G', 26, ""),
        GMCode('Unused', 'G', 27, ""),
        GMCode('Return Home', 'G', 28, "XYZF"),
        GMCode('Unused', 'G', 29, "XYZF"),
        GMCode('Return Secondary Home', 'G', 30, ""),
        GMCode('Skip Function', 'G', 31, ""),
        GMCode('Unused (turning)', 'G', 32, ""),
        GMCode('Constant Pitch Threading', 'G', 33, ""),
        GMCode('Variable Pitch Threading', 'G', 34, ""),
        GMCode('Unused', 'G', 35, ""),
        GMCode('Unused', 'G', 36, ""),
        GMCode('Unused', 'G', 37, ""),
        GMCode('Unused', 'G', 38, ""),
        GMCode('Unused', 'G', 39, ""),
        GMCode('Radius Compensation Off', 'G', 40, ""),
        GMCode('Radius Compensation Left', 'G' ,41, ""),
        GMCode('Radius Compensation Right', 'G', 42, ""),
        GMCode('Tool Height Offset Negative', 'G', 43, ""),
        GMCode('Tool Height Offset Positive', 'G', 44, ""),
        GMCode('Axis Offset Single Increase', 'G', 45, ""),
        GMCode('Axis Offset Single Decrease', 'G', 46, ""),
        GMCode('Axis Offset Double Increase', 'G', 47, ""),
        GMCode('Axis Offset Double Decrease', 'G', 48, ""),
        GMCode('Tool Length Offset Cancel', 'G', 49, ""),
        GMCode('Scaling Function Cancel', 'G', 50, ""),
        GMCode('Unused', 'G', 51, ""),
        GMCode('Local Coordinate System', 'G', 52, ""),
        GMCode('Machine Coordinate System', 'G', 53, ""),
        GMCode('Work Coordinate System 1', 'G', 54, ""),
        GMCode('Work Coordinate System 2', 'G', 55, ""),
        GMCode('Work Coordinate System 3', 'G', 56, ""),
        GMCode('Work Coordinate System 4', 'G', 57, ""),
        GMCode('Work Coordinate System 5', 'G', 58, ""),
        GMCode('Work Coordinate System 6', 'G', 59, ""),
        GMCode('Unused', 'G', 60, ""),
        GMCode('Unused', 'G', 62, ""),
        GMCode('Unused', 'G', 61, ""),
        GMCode('Unused', 'G', 63, ""),
        GMCode('Unused', 'G', 64, ""),
        GMCode('Unused', 'G', 65, ""),
        GMCode('Unused', 'G', 66, ""),
        GMCode('Unused', 'G', 67, ""),
        GMCode('Unused', 'G', 68, ""),
        GMCode('Unused', 'G', 69, ""),
        GMCode('Unused (turning)', 'G', 70, ""),
        GMCode('Unused (turning)', 'G', 71, ""),
        GMCode('Unused (turning)', 'G', 72, ""),
        GMCode('Peck Drilling Cycle', 'G', 73, ""),
        GMCode('Tapping Cycle Left', 'G', 74, ""),
        GMCode('Unused (turning)', 'G', 75, ""),
        GMCode('Fine Boring Cycle', 'G', 76, ""),
        GMCode('Unused', 'G', 77, ""),
        GMCode('Unused', 'G', 78, ""),
        GMCode('Unused', 'G', 79, ""),
        GMCode('Canned Cycle Cancel', 'G', 80, ""),
        GMCode('Simple Drilling Cycle', 'G', 81, ""),
        GMCode('Drilling Cycle With Dwell', 'G', 82, ""),
        GMCode('Peck Drilling Cycle (adv)', 'G', 83, ""),
        GMCode('Tapping Cycle Right', 'G', 84, ""),
        GMCode('Unused', 'G', 85, ""),
        GMCode('Unused', 'G', 86, ""),
        GMCode('Unused', 'G', 87, ""),
        GMCode('Unused', 'G', 88, ""),
        GMCode('Unused', 'G', 89, ""),
        GMCode('Absolute Programming', 'G', 90, "XYZFES"),
        GMCode('Incremental Programming', 'G', 91, "XYZFES"),
        GMCode('Position Register', 'G', 92, ""),
        GMCode('Unused', 'G', 93, ""),
        GMCode('Feed Rate (per min)', 'G', 94, ""),
        GMCode('Feed Rate (per rev)', 'G', 95, ""),
        GMCode('Unused (turning)', 'G', 96, ""),
        GMCode('Constant Spindle Speed', 'G', 97, ""),
        GMCode('Return to initial Z', 'G', 98, ""),
        GMCode('Return to R Level', 'G', 99, ""),
        GMCode('Unused', 'G', 100, "")
    ]

    mcodes = [
        GMCode('Stop!', 'M', 0, ""),
        GMCode('Stop (optional)', 'M', 1, ""),
        GMCode('Program End', 'M', 2, ""),
        GMCode('Spindle On CW', 'M', 3, ""),
        GMCode('Spindle On ACW', 'M', 4, ""),
        GMCode('Spindle Stop', 'M', 5, ""),
        GMCode('Tool Change', 'M', 6, ""),
        GMCode('Coolant On (Mist)', 'M', 7, ""),
        GMCode('Coolant On (Flood)', 'M', 8, ""),
        GMCode('Coolant Off', 'M', 9, ""),
        GMCode('unused', 'M', 10, ""),
        GMCode('unused', 'M', 11, ""),
        GMCode('unused', 'M', 12, ""),
        GMCode('unused', 'M', 13, ""),
        GMCode('unused', 'M', 14, ""),
        GMCode('unused', 'M', 15, ""),
        GMCode('unused', 'M', 16, ""),
        GMCode('FADAL return', 'M', 17, ""),
        GMCode('unused', 'M', 18, ""),
        GMCode('unused', 'M', 19, ""),
        GMCode('unused', 'M', 20, ""),
        GMCode('unused', 'M', 21, ""),
        GMCode('unused', 'M', 22, ""),
        GMCode('unused', 'M', 23, ""),
        GMCode('unused', 'M', 24, ""),
        GMCode('unused', 'M', 25, ""),
        GMCode('unused', 'M', 26, ""),
        GMCode('unused', 'M', 27, ""),
        GMCode('unused', 'M', 28, ""),
        GMCode('FANUC tapping', 'M', 29, ""),
        GMCode('End Program and reset', 'M', 30, ""),
        GMCode('unused', 'M', 31, ""),
        GMCode('unused', 'M', 32, ""),
        GMCode('unused', 'M', 33, ""),
        GMCode('unused', 'M', 34, ""),
        GMCode('unused', 'M', 35, ""),
        GMCode('unused', 'M', 36, ""),
        GMCode('unused', 'M', 37, ""),
        GMCode('unused', 'M', 38, ""),
        GMCode('unused', 'M', 39, ""),
        GMCode('unused', 'M', 40, ""),
        GMCode('unused', 'M', 41, ""),
        GMCode('unused', 'M', 42, ""),
        GMCode('unused', 'M', 43, ""),
        GMCode('unused', 'M', 44, ""),
        GMCode('unused', 'M', 45, ""),
        GMCode('unused', 'M', 46, ""),
        GMCode('unused', 'M', 47, ""),
        GMCode('unused', 'M', 48, ""),
        GMCode('unused', 'M', 49, ""),
        GMCode('unused', 'M', 50, ""),
        GMCode('unused', 'M', 51, ""),
        GMCode('unused', 'M', 52, ""),
        GMCode('unused', 'M', 53, ""),
        GMCode('unused', 'M', 54, ""),
        GMCode('unused', 'M', 55, ""),
        GMCode('unused', 'M', 56, ""),
        GMCode('unused', 'M', 57, ""),
        GMCode('unused', 'M', 58, ""),
        GMCode('unused', 'M', 59, ""),
        GMCode('unused', 'M', 60, ""),
        GMCode('unused', 'M', 61, ""),
        GMCode('unused', 'M', 62, ""),
        GMCode('unused', 'M', 63, ""),
        GMCode('unused', 'M', 64, ""),
        GMCode('unused', 'M', 65, ""),
        GMCode('unused', 'M', 66, ""),
        GMCode('unused', 'M', 67, ""),
        GMCode('unused', 'M', 68, ""),
        GMCode('unused', 'M', 69, ""),
        GMCode('unused', 'M', 70, ""),
        GMCode('unused', 'M', 71, ""),
        GMCode('unused', 'M', 72, ""),
        GMCode('unused', 'M', 73, ""),
        GMCode('unused', 'M', 74, ""),
        GMCode('unused', 'M', 75, ""),
        GMCode('unused', 'M', 76, ""),
        GMCode('unused', 'M', 77, ""),
        GMCode('unused', 'M', 78, ""),
        GMCode('unused', 'M', 79, ""),
        GMCode('unused', 'M', 80, ""),
        GMCode('unused', 'M', 81, ""),
        GMCode('unused', 'M', 82, ""),
        GMCode('unused', 'M', 83, ""),
        GMCode('unused', 'M', 84, ""),
        GMCode('unused', 'M', 85, ""),
        GMCode('unused', 'M', 86, ""),
        GMCode('unused', 'M', 87, ""),
        GMCode('unused', 'M', 88, ""),
        GMCode('unused', 'M', 89, ""),
        GMCode('unused', 'M', 90, ""),
        GMCode('unused', 'M', 91, ""),
        GMCode('unused', 'M', 92, ""),
        GMCode('unused', 'M', 93, ""),
        GMCode('unused', 'M', 94, ""),
        GMCode('unused', 'M', 95, ""),
        GMCode('unused', 'M', 96, ""),
        GMCode('HAAS subroutine call', 'M', 97, ""),
        GMCode('Subroutine call', 'M', 98, ""),
        GMCode('Subroutine end', 'M', 99, ""),
        GMCode('unused', 'M', 100, "")
    ]

    lettercodes = [
        LetterCode('A Axis', 'A', ""),
        LetterCode('B Axis', 'B', ""),
        LetterCode('C Axis', 'C', ""),
        LetterCode('Tool Diameter Compensation', 'D',""),
        LetterCode('Lathe Feedrate', 'E',""),
        LetterCode('Feed Rate', 'F',""),

        # G (go) See Above
        LetterCode('Go Code', 'G',""),

        LetterCode('Tool Length Compensation', 'H',""),
        LetterCode('Arc Centre (X axis)', 'I',""),
        LetterCode('Arc Centre (Y axis)', 'J',""),
        LetterCode('Arc Centre (Z axis)', 'K',""),
        LetterCode('Loop (see G10)', 'L',""),
        
        # M (misc) See above
        LetterCode('Misc Code', 'M',""),

        LetterCode('Line Number', 'N',""),
        LetterCode('Program Name', 'O',""),
        LetterCode('Parameter Address (iteration register)', 'P',""),
        LetterCode('Canned Cycle Increment', 'Q',""),
        LetterCode('Arc Radius', 'R',""),
        LetterCode('Speed', 'S',""),
        LetterCode('Tool Selection', 'T',""),
        LetterCode('Incremental X (Lathe)', 'U',""),
        LetterCode('Incremental Y (Lathe)', 'V',""),
        LetterCode('Incremental Z (Lathe)', 'W',""),
        LetterCode('X Axis Position', 'X',""),
        LetterCode('Y Axis Position', 'Y',""),
        LetterCode('Z Axis Position', 'Z',"")
    ]

    # TODO comments and other oddities

    def __init__(self):
        pass

    @staticmethod
    def getCode(type:str, value:any) -> GrblCode:
        if "G" == type:
            for g in Codes.gcodes:
                if int(value) == g.value: return g
        elif "M" == type:
            for m in Codes.mcodes:
                if int(value) == m.value: return m
        elif len(type) == 1:
            for l in Codes.lettercodes:
                if type.upper() == l.type: return l
        return None

    def getAllCodes(self):
        ret = []
        #for c in self.gcodes: ret.append(c)
        #for c in self.mcodes: ret.append(c)
        for c in self.lettercodes: ret.append(c)
        ret.append(CommentCode())
        return ret

    # TODO find a way of accessing main globals from here withing requiring a parameter
    # to use this method from another python file pass (globals()) as g
    def createPlyIntrospectionObjects(self, g):
        # get all codes in a single array
        ac = self.getAllCodes()
        # create the PLY 'tokens' variable
        ret = []
        for c in ac: ret.append(c.name)
        g["tokens"] = ret
        # now create all the matching t_TOKEN functions
        for c in reversed(ac):
            bar = compile(str(c.lexFunctionSource()), "<string>", "exec")
            fn = types.FunctionType(bar.co_consts[0], g)
            g[f"t_{c.name}"] = fn

# A lexer for rudimentary parsing of GRBL and GRBLScript
class BaseLexer:
    def __init__(self, infile):
        self.infile = infile
        self.codesObj = Codes()
        self.setLexingMethods()

    def setLexingMethods(self):
        self.t_ignore = ' \t'
        ac = self.codesObj.getAllCodes()
        # create the PLY 'tokens' variable
        ret = []
        for c in ac: ret.append(c.name)
        self.tokens = ret
        # dynamically compile lex methods for each type of GCode and
        # add them to this class. This is just easier than adding the t_
        # methods for each code manually
        for c in reversed(ac):
            n = f"t_{c.name}"
            bar = compile(str(c.lexFunctionSource()), "<string>", "exec")
            environment = {}
            exec(bar, environment)
            m = types.MethodType(environment[n], self)
            #fn = types.MethodType(bar.co_consts[0])
            setattr(self, f"t_{c.name}", m)
            #self[f"t_{c.name}"] = fn

    def t_error(self, t: lex.LexToken) -> lex.LexToken:
        # t.type = t.value[0]
        # t.value = t.value[0]
        print("Illegal character '%s'" % t.value[0])
        t.lexer.skip(1)
        return t

    def t_newline(self, t: lex.LexToken) -> lex.LexToken:
        r'\n+'
        t.lexer.lineno += len(t.value)

    def doLexing(self):
        self.lexer = lex.lex(module=self)
        file = open(self.infile)
        foo = file.read()
        self.lexer.input(foo)

    def burp(self):
        for t in self.lexer:
            print(str(t.type))


#l = BaseLexer("D:\.scripts\python\personal\GML\jolana.nc")
#l.doLexing()
#l.burp()