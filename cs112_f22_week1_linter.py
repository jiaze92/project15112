_module = 'cs112_f22_week1_linter.py version 2.0'
# Place this file in the same folder as your Python files.
# While you need to use this file to do your exercises, students
# are not expected to look at nor to understand any code in this file.

_bannedTokens = (
        'as,break,class,continue,del,except,finally,for,' +
        'global,in,lambda,nonlocal,raise,repr,' +
        'try,while,with,yield,' +
        '__import__,ascii,bin,bytearray,bytes,callable,' +
        'classmethod,compile,delattr,dict,dir,enumerate,' +
        'eval,literal_eval,exec,filter,format,frozenset,getattr,globals,' +
        'hasattr,hash,help,hex,id,issubclass,iter,' +
        'list,map,memoryview,next,object,oct,' +
        'open,ord,property,range,reversed,set,' +
        'setattr,slice,sorted,staticmethod,super,' +
        'vars,zip,importlib,imp,string,[,],{,}')

_conversions = {
    'classdef': 'class',
}

import math, sys, traceback, inspect
import ast
import platform


class _AssertionError(AssertionError): pass


def _formatError(header, file, line, fn, text, msg, expl):
    messages = ['\n******************************']
    if (header): messages.append(header)
    if (file): messages.append('  File:     "%s"' % file)
    if (line): messages.append('  Line:     %d' % line)
    if (fn): messages.append('  Function: %s' % fn)
    if (text): messages.append('  Code:     %s' % text.strip())
    messages.append('  Error:    %s' % msg)
    if (expl): messages.append('  Hint:     %s' % expl)
    message = '\n'.join(messages)
    return message


class _LintError(Exception):
    def __init__(self, errors):
        messages = ['']
        for i, e in enumerate(errors):
            (msg, file, line, fn, text, expl) = e
            header = 'LintError #%d of %d:' % (i + 1, len(errors))
            message = _formatError(header, file, line, fn, text, msg, expl)
            messages.append(message)
        message = ''.join(messages)
        super().__init__(message)


class _Linter(ast.NodeVisitor):
    def __init__(self, code=None, filename=None, bannedTokens=None):
        self.code = code
        self.filename = filename
        self.bannedTokens = set(bannedTokens or [])
        self.issuedRoundOopsMessage = False
        ifMain = ast.parse("if __name__ == '__main__': main()")
        self.allowableConditional = ast.dump(ifMain.body[0])

    def lint(self):
        print('Linting... ', end='')
        self.errors = []
        if (self.code == None):
            with open(self.filename, 'rt', encoding="utf-8") as f:
                try:
                    self.code = f.read()
                except e:
                    msg = 'Error when trying to read file:\n' + str(e)
                    expl = ("This usually means something got corrupted in "
                            "your file\n\t\t\t and you should remove the "
                            "corrupted portions or\n\t\t\t start a new file.")
                    self.oops(msg, expl)
                    raise _LintError(self.errors)
        if (self.code in [None, '']):
            self.oops('Could not read code from "%s"' % self.filename)
            raise _LintError(self.errors)

        self.tree = ast.parse(self.code)

        # print(ast.dump(self.tree, indent=4))

        self.lintLineWidths()  # Strips out trailing whitespace
        self.lintSymbols()  # Things that are easier to catch in text
        self.lintTopLevel()  # Only allow import, def, class, or if...main()
        self.lintAllLevels()  # AST diving
        if (self.errors != []):
            raise _LintError(self.errors)
        print("Passed!")

    def lintLineWidths(self):
        lines = self.code.splitlines()

        for i in range(len(lines)):
            line = lines[i].rstrip()
            if (len(line) > 80):
                msg = 'Line width is >80 characters'
                expl = ("You may not have a line of code "
                        "longer than 80 characters.")
                self.oops(msg, expl,
                          line=i + 1, text='\n' + line[:81] + '...')

    def lintSymbols(self):
        symbols = {'[', ']', '{', '}', '@', '&', '^', '|'}
        prohibitedSymbols = symbols.intersection(self.bannedTokens)

        lines = self.code.splitlines()
        for i in range(len(lines)):
            line = lines[i]
            for token in prohibitedSymbols:
                if token in line:
                    msg = f'Disallowed token: {token}'
                    expl = ("You are using a feature of Python that is "
                            "not allowed in this\n\t\t\tassignment. You will "
                            "need to solve this assignment without using "
                            "\n\t\t\tthat feature.")
                    self.oops(msg, expl, line=i, text=line)

    def lintTopLevel(self):
        exemptNodeTypes = (ast.ClassDef,
                           ast.FunctionDef,
                           ast.Import,
                           ast.ImportFrom)
        for node in self.tree.body:
            if (type(node) not in exemptNodeTypes
                    and (ast.dump(node) != self.allowableConditional)):
                msg = "Top-level code that is not import, def, or class."
                expl = ("All of your code should be inside of a function. "
                        "If you want to make sure\n\t\t\tsomething runs "
                        "every time, add it to main().")
                text = ast.get_source_segment(self.code, node, padded=True)
                self.oops(msg, expl, line=node.lineno, text=text, node=node)

    def lintAllLevels(self):
        self.visit(self.tree)

    def visit_Import(self, node):
        for n in node.names:
            self.checkToken(n.name, node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.checkToken(node.name, node)
        self.generic_visit(node)

    def visit_Call(self, node):
        if hasattr(node.func, "id"):
            self.checkToken(node.func.id, node)
        else:
            self.visit(node.func.value)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if hasattr(node.value, "id"):
            self.checkToken(node.value.id, node)
        self.checkToken(node.attr, node)
        self.generic_visit(node)

    # def visit_Expr(self, node):
    #    self.generic_visit(node)

    # def visit_With(self, node):
    #    self.generic_visit(node)

    def generic_visit(self, node):
        token = str(type(node)).split('.')[-1].split("'")[0].lower()
        self.checkToken(token, node)
        super().generic_visit(node)

    def checkToken(self, token, node):
        token = _conversions.get(token, token)
        if token == 'round':
            self.roundOops(node)
        elif token in self.bannedTokens:
            msg = f'Disallowed token: {token}'
            expl = ("You are using a feature of Python that is not allowed "
                    "in this\n\t\t\tassignment. You will need to solve this "
                    "assignment without using\n\t\t\tthat feature.")
            text = ast.get_source_segment(self.code, node, padded=True)
            self.oops(msg, expl, line=node.lineno, text=text, node=node)

    def roundOops(self, node):
        msg = 'Do not use builtin "round" in Python 3'
        if (self.issuedRoundOopsMessage):
            msg += ' (see above for details)'
            expl = ''
        else:
            self.issuedRoundOopsMessage = True
            expl = ('The behavior of "round" in Python 3 may be unexpected. '
                    '\n\t\t\tFor example: '
                    '\n\t\t\t   round(1.5) returns 2 '
                    '\n\t\t\t   round(2.5) returns 2 '
                    '\n\t\t\tInstead, in 15-112, use the roundHalfUp(d) '
                    'function provided. ')
        text = ast.get_source_segment(self.code, node, padded=True)
        self.oops(msg, expl, line=node.lineno, text=text, node=node)

    def oops(self, msg, expl=None,
             line=None,
             fn=None,
             text=None,
             node=None):
        self.errors.append((msg, self.filename, line, fn, text, expl))


def lint(code=None, filename=None, bannedTokens=_bannedTokens):
    if (isinstance(bannedTokens, str)):
        bannedTokens = bannedTokens.split(',')
    if ((code == None) and (filename == None)):
        try:
            module = None
            frame = inspect.stack()[1]
            module = inspect.getmodule(frame[0])
            if ((module == None) or (module.__file__ == None)):
                # this may help, or maybe not (sigh)
                module = sys.modules['__main__']
            # the next line may fail (sigh)
            filename = module.__file__
        except:
            raise Exception('lint cannot find module/file to lint!')
    try:
        _Linter(code=code, filename=filename, bannedTokens=bannedTokens).lint()
    except _LintError as lintError:
        # just 'raise lintError' for cleaner traceback
        lintError.__traceback__ = None
        raise lintError


def _printImportReport():
    import platform, datetime
    # print('Importing %s in Python %s' % (_module, platform.python_version()))
    (major, minor, micro, releaselevel, serial) = sys.version_info
    if (major < 3):
        raise Exception("You must use Python 3, not Python 2!")
    if (minor < 7):
        raise Exception("You must use Python 3.7 or newer!")


if (__name__ != '__main__'):
    _printImportReport()
