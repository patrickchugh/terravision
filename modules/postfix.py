import hashlib
import re


def compute_hash(bstring):
    # A arbitrary (but fixed) buffer
    # size (change accordingly)
    # 65536 = 65536 bytes = 64 kilobytes
    BUF_SIZE = 65536

    # Initializing the sha256() method
    sha256 = hashlib.sha256()
    sha256.update(bstring)
    return str(int(sha256.hexdigest(), 16))


def find_nth(string, substring, n):
    if n == 1:
        return string.find(substring)
    else:
        return string.find(substring, find_nth(string, substring, n - 1) + 1)


# Class to eval the postfix expression
class Evaluate:
    # Constructor to initialize the class variables
    def __init__(self, capacity):
        self.top = -1
        self.capacity = capacity
        # This array is used a stack
        self.array = []

    # check if the stack is empty
    def isEmpty(self):
        return True if self.top == -1 else False

    # Return the value of the top of the stack
    def peek(self):
        if len(self.array) > 0:
            return self.array[-1]
        else:
            return " "

    # Pop the element from the stack
    def pop(self):
        if not self.isEmpty():
            self.top -= 1
            return self.array.pop()
        else:
            return " "

    # Push the element to the stack
    def push(self, op):
        self.top += 1
        self.array.append(op)

    # The main function that converts given infix expression
    # to postfix expression

    def evaluatePostfix(self, exp):
        # Iterate over the expression for conversion
        for i in exp:
            # If the scanned character is an operand
            # (number here) push it to the stack
            if i.isdigit() or i == " ":
                self.push(i)
            # If the scanned character is an operator,
            # pop two elements from stack and apply it.
            elif i != ":":
                val1 = ""
                val2 = ""
                # Trim leading spaces until we find first value for val1
                tried = 0
                while self.peek() == " ":
                    if tried > 100:
                        break
                    tried = tried + 1
                    self.pop()
                if tried > 100:
                    return "ERROR!"
                # Accumulate multi digit operand until we hit a space
                while self.peek() != " ":
                    val1 = str(self.pop()) + val1
                # Now do the same for val2
                while self.peek() == " " and not self.isEmpty():
                    self.pop()
                while self.peek() != " ":
                    val2 = str(self.pop()) + val2
                estr = str(val2) + str(i) + str(val1)
                estr = estr.replace("=", "==")
                estr = estr.replace("!", "!=")
                estr = estr.replace("&", " and ")
                estr = estr.replace("|", " or ")
                estr = estr.replace("G", " >= ")
                estr = estr.replace("L", " <= ")
                # print(estr)
                try:
                    self.push(eval(estr))
                except:
                    return "ERROR!"
                self.push(" ")
            elif i == ":":
                val1 = ""
                val2 = ""
                val3 = ""
                if self.peek() == " ":
                    self.pop()
                while self.peek() != " ":
                    val1 = str(self.pop()) + val1
                self.pop()
                while self.peek() != " ":
                    val2 = str(self.pop()) + val2
                while (
                    not isinstance(self.peek(), bool)
                    and str(self.peek()) != "1"
                    and str(self.peek()) != "0"
                    and self.top != -1
                ):
                    self.pop()
                if self.top != -1:
                    val3 = int(self.pop())
                else:
                    val3 = False
                if val3 == True:
                    self.push(val2)
                else:
                    self.push(val1)
        return self.pop()


# Class to convert the expression from infix to postfix
class Conversion:
    # Constructor to initialize the class variables
    def __init__(self, capacity):
        self.top = -1
        self.capacity = capacity
        # This array is used a stack
        self.array = []
        # Precedence setting
        self.output = []
        self.precedence = {
            ":": 0,
            "+": 1,
            "~": 1,
            "*": 2,
            "/": 2,
            "^": 3,
            "&": 4,
            "|": 4,
            "!": 4,
            ">": 5,
            "<": 5,
            "=": 6,
        }

    # Evaluate Sub Expressions within main expression recursively
    def evaluate_subexp(self, exp):
        obj = Conversion(len(exp))
        pf = obj.infixToPostfix(exp)
        # print(pf)
        obj = Evaluate(len(pf))
        returnval = obj.evaluatePostfix(pf)
        # print(returnval)
        return returnval

    # check if the stack is empty
    def isEmpty(self):
        return True if self.top == -1 else False

    # Return the value of the top of the stack
    def peek(self):
        return self.array[-1]

    # Pop the element from the stack
    def pop(self):
        if not self.isEmpty():
            self.top -= 1
            return self.array.pop()
        else:
            return " "

    # Push the element to the stack
    def push(self, op):
        if op != "":
            self.top += 1
            self.array.append(op)

    # A utility function to check is the given character
    # is operand
    def isOperand(self, ch):
        return ch.isdigit() or ch == "T" or ch == "F"

    def hash_strings(self, exp):
        tried = 0
        while exp.count('"') > 1:
            if tried > 100:
                break
            split_array = exp.split('"')
            string = split_array[1]
            if len(string) > 0:
                exp = exp.replace('"' + string + '"', compute_hash(str.encode(string)))
            else:
                exp = exp.replace('""', "0")
            tried = tried + 1
        if tried > 100:
            return "ERROR"
        tried = 0
        while exp.count("'") > 1:
            split_array = exp.split("'")
            string = split_array[1]
            if len(string) > 0:
                exp = exp.replace("'" + string + "'", compute_hash(str.encode(string)))
            else:
                exp = exp.replace("''", "0")
            tried = tried + 1
        if tried > 100:
            return "ERROR"
        return exp

    # Check if the precedence of operator is strictly
    # less than top of stack or not
    def notGreater(self, i):
        try:
            a = self.precedence[i]
            b = self.precedence[self.peek()]
            return True if a <= b else False
        except KeyError:
            return False

    # The main function that
    # converts given infix expression
    # to postfix expression
    def infixToPostfix(self, exp):
        # Shorten two char operators to one char and replace True/False with condition
        if "${" in exp:
            exp = "".join(exp.rsplit("}", 1))
            exp = exp.replace("${", "", 1)
        exp = exp.replace("==", "=")
        exp = exp.replace('"True"', "T")
        exp = exp.replace('"False"', "F")
        exp = exp.replace("False", "F")
        exp = exp.replace("True", "T")
        exp = exp.replace(" !False ", " T ")
        exp = exp.replace(" !True ", " F ")
        exp = exp.replace("&&", "&")
        exp = exp.replace("||", "|")
        exp = exp.replace("!=", "!")
        exp = exp.replace(">=", "G")
        exp = exp.replace("<=", "L")
        # exp = exp.replace(",", "")
        exp = exp.replace("[", "")
        exp = exp.replace("]", "")
        exp = exp.replace("!F", "T")
        exp = exp.replace("!0", "1")
        exp = exp.replace("!  None", "F")
        exp = exp.replace("UNKNOWN", "F")
        exp = exp.replace('"None"', '""')
        none_parameters = re.findall("None\.[A-Za-z0-9_-]+", exp)
        for np in none_parameters:
            exp = exp.replace(np, '""')
        exp = exp.replace("!None", " T ")
        exp = exp.replace("None", '""')
        exp = exp.replace("  ", "")
        exp = self.hash_strings(exp)
        counter = -1
        tried = 1
        spaces = 0
        while exp.count("?") > 1:
            if tried > 20:
                break
            num_ifs = exp.count("?")
            begin_index = find_nth(exp, "?", num_ifs)
            end_index = find_nth(exp, ":", num_ifs)
            spaces = begin_index - 1
            while exp[spaces] == " ":
                spaces = spaces - 1
                if spaces > 100:
                    break
            middle = exp[spaces:end_index]
            parsed_value = self.evaluate_subexp(middle)
            exp = exp.replace(middle, str(parsed_value))
            tried = tried + 1
        if spaces > 100:
            return "ERROR!"
        if tried > 20:
            return "ERROR!"
        # Iterate over the expression for conversion
        for i in exp:
            counter += 1
            # If the character is an operand,
            # add it to output
            if self.isOperand(i):
                o = i
                if i == "T":
                    o = "1"
                    if exp[counter + 1] != " ":
                        o = o + " "
                if i == "F":
                    o = "0"
                    if exp[counter + 1] != " ":
                        o = o + " "
                self.output.append(o)

            # If the character is an '(', push it to stack
            elif i == "(":
                self.push(i)
            elif i == " ":
                pass
            elif i == "?":
                self.output.append(self.pop())
                self.output.append(self.pop())

            # If the scanned character is an ')', pop and
            # output from the stack until and '(' is found
            elif i == ")":
                while (not self.isEmpty()) and self.peek() != "(":
                    a = self.pop()
                    self.output.append(a)
                if not self.isEmpty() and self.peek() != "(":
                    return -1
                else:
                    self.pop()

            # An operator is encountered
            else:
                while not self.isEmpty() and self.notGreater(i):
                    self.output.append(self.pop())
                self.output.append(" ")
                self.push(i)

        # pop all the operator from the stack
        while not self.isEmpty():
            self.output.append(self.pop())
        return "".join(self.output)


######
##### For Module Testing Only
#####

# exp = 'False && !False ? "Can not remove the app prefix from a role that is not SAML enabled" : 0'

# print(exp)
# obj = Conversion(len(exp))

# print (obj.hash_strings(exp))

# pf = obj.infixToPostfix(exp)
# print(pf)
# obj = Evaluate(len(pf))
# eval_value = obj.evaluatePostfix(pf)
# print(eval_value)
