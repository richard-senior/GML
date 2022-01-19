import ply
import collections
import codes

class StateObject:
    def __init__(self):
        self.d = {
            "A":None,"B":None,"C":None,"D":None,"E":None,"F":None,"G":None,
            "H":None,"I":None,"J":None,"K":None,"L":None,"M":None,"N":None,
            "O":None,"P":None,"Q":None,"R":None,"S":None,"T":None,"U":None,
            "V":None,"W":None,"X":None,"Y":None,"Z":None,"COMMENT":None
        }

    def handleToken(self, t: ply.lex.LexToken):
        if not t: return
        self.d[t.type] = t.value


class ParserState():
    def __init__(self):
        self.current: StateObject = None
        self.previous: StateObject = None
        self.showComments: bool = False
        self.lineNumbers: bool = False
        self.blockNumbers: bool = False
        global parserState

    def setLexer(self, lexer: ply.lex.Lexer):
        self.lexer = lexer

    def getLexer(self) -> ply.lex.Lexer:
        return self.lexer

    def update(self, t: ply.lex.LexToken):
        if not t: return
        self.previous = self.current
        if not self.previous: 
            self.current = StateObject()
        else:
            self.current = self.previous.copy()
        self.current.handleToken(t)

    def isParamChangePositive(self, param: str) -> bool:
        if not self.previous or not self.previous[param]: return False
        if not self.current or not self.current[param]: return False
        c = float(self.curent[param])
        p = float(self.previous[param])
        return c > p

    def isParamChangeNegative(self, param: str) -> bool:
        if not self.previous or not self.prevoius[param]: return False
        if not self.current or not self.current[param]: return False
        c = float(self.curent[param])
        p = float(self.previous[param])
        return c < p

    @staticmethod
    def getState():
        global parserState
        if parserState is None:
            ParserState()
        return parserState


# class which holds a single command which is any G or M code and all it's associated
# Parameters(X,Y,Z,J,I etc.)
class Command:

    def __init__(self):
        self.lineNumber = 0
        self.command = None
        self.parameters = []
        self.gcodeobject: codes.GrblCode = None

    # handles any lex token.
    # Return None if handled by this instance of Command object
    # Returns new instance of Command object if the existing one is 'full'.
    def handleToken(self, t: ply.lex.LexToken):
        if not t:
            raise ValueError("must pass a valid LexToken")
        
        # make a record of this token
        state = ParserState().getState()
        state.update(t)

        if "COMMENT" == t.type or "M" == t.type or "G" == t.type or "O" == t.type:
            ret = self.__setCommand(t)
            # things here?
            return ret

        self.addParameter(t)
        return None

    def __setCommand(self, t: ply.lex.LexToken) -> ply.lex.LexToken:
        if self.command:
            if not self.isValid():
                raise ValueError("two consecutive commands of this type are ivalid :" + t.type)
            c = Command()
            c.command = t
            return c
        else:
            self.command = t
            return None

    def isValid(self) -> bool:
        if not self.command: return False
        if "COMMENT" == self.command.type: return True
        if not self.gcodeobject:
            self.gcodeobject = codes.Codes.getCode(self.command.type, self.command.value)
        if not self.gcodeobject:
            raise ValueError("Bug!? Unknown or unsupported code!")
        if len(self.gcodeobject.allowedParams) == 0:
            return True
        if len(self.parameters) == 0: return False
        if "M" == self.command.type or "G" == self.command.type:
            for t in self.parameters:
                if t.type in self.gcodeobject.allowedParams: return True
        return False

    def hasParameterType(self, par: str) -> bool:
        if len(self.parameters) == 0: return False
        if not par: raise ValueError("must pass a parameter letter")
        for p in self.parameters:
            if par.upper() == p.type: return True
        return False

    def getCommand(self) -> ply.lex.LexToken:
        return self.command

    def getCommandType(self) -> str:
        if not self.command: return None
        return self.command.type

    def getParameter(self, comm: str) -> ply.lex.LexToken:
        if not comm: return None
        if len(self.parameters) < 1: return None
        for t in self.parameters:
            if comm == t.type:
                return t
        return None

    def getX(self) -> float:
        p = self.getParameter("X")
        if not p: return None
        return p.value

    def addParameter(self, t: ply.lex.LexToken):
        if self.hasParameterType(t.type): raise ValueError("already have one of these parameters : " + t.type)
        self.parameters.append(t)

    def __str__(self):
        if not self.command: return ""
        if "COMMENT" == self.command.type:
            return "(" + self.command.value + ")"
        ret = self.command.type + self.command.value
        for a in self.parameters:
            ret = ret + " "
            ret = ret + a.type
            ret = ret + a.value
        return ret


# a block is an ordered list of Commands
# a block is any set of commands which come between two z axis lifts
# ie. a block is a set of commands in one run of the tool at any particular depth
class Block:
    def __init__(self):
        self.blockNum: int = 0
        self.commands: list[Command] = []
        self.s: ParserState = ParserState.getState()

    def addToken(self, t: ply.lex.LexToken):
        c: Command = None
        
        if len(self.commands) < 1:
            c = Command()
            self.commands.append(c)
        else:
            c = self.commands[-1]
        
        foo = c.handleToken(t)
        if foo:
            # new command so is this a new block?
            self.commands.append(foo)
            if self.isEndBlock():
                return Block()
        return None
    
    def isEndBlock(self) -> bool:
        c = self.commands[-1]
        if self.s.isParamChangePositive("Z"):
            print("z param changed")
        return False


    def __str__(self):
        if len(self.commands) < 1: return ""
        ret = ""
        for c in self.commands:
            if "COMMENT" == c.getCommand().type and not self.s.showComments: continue
            ret = ret + str(c) + "\n"
        return ret

# a job is an ordered list of Blocks
class Job:
    def __init__(self):
        self.blocks = []
        self.state = ParserState.getState()

    def slurp(self):
        lexer = self.state.getLexer()
        if len(self.blocks) == 0:
            self.blocks.append(Block())
        
        for t in lexer:
            b = self.blocks[-1]
            foo = b.addToken(t)
            if foo:
                self.blocks.append(foo)
            #TODO new blocks

    def __str__(self):
        if len(self.blocks) < 1: return ""
        ret = ""
        for b in self.blocks:
            ret = ret + str(b)
        return ret


class PostProcessor:
    def __init__(self, lexer: ply.lex.Lexer):
        self.state = ParserState.getState()
        self.state.setLexer(lexer)
        self.job = Job()
        self.job.slurp()
        print(self.job)
