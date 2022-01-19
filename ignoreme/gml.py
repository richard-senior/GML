from ply import lex, yacc
import codes
import burper

# #######################################
# ########## Constants ##################
# #######################################
codesObj = codes.Codes()
LINE_NUMBERS_ENABLED = False
# #######################################
# ########## Lex/Yacc ###################
# #######################################
t_ignore = ' \t'


def t_error(t: lex.LexToken) -> lex.LexToken:
    # t.type = t.value[0]
    # t.value = t.value[0]
    print("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)
    return t


def t_newline(t: lex.LexToken) -> lex.LexToken:
    r'\n+'
    t.lexer.lineno += len(t.value)


def p_error(p):
    #print("error at '%s'" % p.value)
    pass

class Param():
    def __init__(self, t: lex.LexToken):
        self.t = t

    def __str__(self):
        return str(self.t.type) + str(self.t.value)

class Command():
    def __init__(self, p):
        s = p.slice[1]
        if "COMMENT" == s.type:
            self.comment = s.value
        else:
            print("found comand")

class Code():
    def __init__(self, p):
        self.params = []
        t = p.slice[1]
        if type(t) != lex.LexToken:
            raise ValueError("must supply a parser token that has a lexxing token as parameter 1 of it's slice")
        if "G" == t.type and int(t.value) == 0:
            print("Found G00")
        self.t = t

    def addParam(self, par: Param):
        if "Z" == par.t.type:
            print("Z command found")
        self.params.append(par)

    @staticmethod
    def getCode(p):
        t = p.slice[1]
        v = t.value
        if type(t) == lex.LexToken:
            #print("found new code " + str(t.type) + str(t.value))
            ret = Code(p)
            if len(p.slice) < 3 or type(p.slice[2]) != yacc.YaccSymbol or type(p.slice[2].value) != Param:
                raise ValueError("parser should have passed a parameter for this code but did not")
            param = p.slice[2].value
            ret.addParam(param)
            return ret
        elif type(v) == Code:
            param = p.slice[2].value
            v.addParam(param)
            #print("found existing code : " + str(v))
            return v

    def __str__(self):
        ret = str(self.t.type) + str(self.t.value)
        for p in self.params:
            ret = ret + " " + str(p)
        return ret


def p_command(p):
    """
        command : g_command
            | m_command
            | COMMENT
    """
    p[0] = Command(p)

def p_g_command(p):
    """
        g_command : G g_param
                | g_command g_param
    """
    if type(p[1]) == str:
        #print(p[1])
        pass
    elif type(p[1]) == Code:
        #print(str(p[1]))
        pass
    
    p[0] = Code.getCode(p)

def p_m_command(p):
    """
        m_command : M m_param
                | m_command m_param
    """
    p[0] = Code.getCode(p)
    print(str(p[0]))

def p_m_param(p):
    """
        m_param : S
                | F
    """
    par = Param(p.slice[1])
    p[0] = par

# A command is any G or M code
def p_g_param(p):
    """
        g_param : F
                | H
                | I
                | J
                | K
                | L
                | S
                | T
                | W
                | X
                | Y
                | Z
    """
    par = Param(p.slice[1])
    p[0] = par


codesObj.createPlyIntrospectionObjects(globals())
lexer = lex.lex()
file = open("D:\.scripts\python\personal\GML\jolana_letter_outlines.nc")
foo = file.read()
lexer.input(foo)

parser = yacc.yacc(debug=1)
result = parser.parse(debug=1)
print(result)

#burper = burper.PostProcessor(lexer)