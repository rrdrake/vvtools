#!/usr/bin/env python3
import sys
import os
import math
import random
import re

class SimpleAprepro:
    """
    This class is a scaled-down version of Aprepro, a text preprocessor
    for mathematical expressions. It only supports the subset of
    capabilities from Aprepro that are most useful for V&V and automated
    testing. While the general behavior is the same as Aprepro, the
    replaced text is not guaranteed to be the same (e.g. the number of
    digits of printed accuracy might not be the same).

    The source of Aprepro lives in Seacas:

        https://github.com/gsjaardema/seacas

    and the documentation can be found here:

        https://gsjaardema.github.io/seacas/


    Quick Description
    -----------------

    A file can be written with mathematical expressions between curly
    braces (on a single line) and it will write a new file with those
    chunks replaced. For example:

      Input:  "I have {n_bananas = 6} bananas.
               Would you like {n_bananas / 2}?"

      Output: "I have 6 bananas.
               Would you like 3 bananas?"

    It is also able to handle simple mathematical functions like sin(),
    cos(), and sqrt().


    Inputs
    ------

    src_f        filename of the file to process
    dst_f        filename of where to write the processed file
    chatty       bool defining if messages should be written to screen
    override     dictionary of values to override or None
    immutable    bool defining if variables can be overwritten


    Outputs
    -------

    eval_locals  dictionary of variable names and values that were
                 evaluated while processing src_f.
    """


    def __init__(self, src_f, dst_f,
                       chatty=True,
                       override=None,
                       immutable=False):
        self.src_f = src_f
        self.dst_f = dst_f
        self.chatty = chatty
        if override is None:
            self.override = {}
        else:
            self.override = override
        self.immutable = immutable
        self.src_txt = []
        self.dst_txt = []

        # These are defined here so that each time process() is called
        # it gets a new version of the locals and globals so that there
        # isn't cross-call contamination. Commented entries are present
        # in Aprepro but are not supported here.
        self.safe_globals = {
                             "abs": math.fabs,
                             "acos": math.acos,
                             #"acosd"
                             "acosh": math.acosh,
                             "asin": math.asin,
                             #"asind"
                             "asinh": math.asinh,
                             "atan": math.atan,
                             "atan2": math.atan2,
                             #"atan2d"
                             #"atand"
                             "atanh": math.atanh,
                             "ceil": math.ceil,
                             "cos": math.cos,
                             #"cosd"
                             "cosh": math.cosh,
                             "d2r": math.radians,
                             #"dim"
                             #"dist"
                             "exp": math.exp,
                             #"find_word"
                             "floor": math.floor,
                             "fmod": math.fmod,
                             "hypot": math.hypot,
                             #"int" (I think this is part of the python interpreter)
                             #"julday"
                             #"juldayhms"
                             #"lgamma"
                             "ln": math.log,
                             "log": math.log,
                             "log10": math.log10,
                             "log1p": math.log1p,
                             "log1p": math.log1p,
                             "max": max,
                             "min": min,
                             "nint" : round,
                             #"polarX"
                             #"polarY"
                             "r2d" : math.degrees,
                             "rand" : random.uniform,
                             "rand_lognormal" : random.lognormvariate,
                             "rand_normal" : random.normalvariate,
                             "rand_weibull" : random.weibullvariate,
                             "sign": math.copysign,
                             "sin": math.sin,
                             #"sind"
                             "sinh": math.sinh,
                             "sqrt": math.sqrt,
                             #"srand"
                             #"strtod"
                             "tan": math.tan,
                             #"tand"
                             "tanh": math.tanh,
                             #"Vangle"
                             #"Vangled"
                             #"word_count"

                             # Predefined Variables from Aprepro
                             "PI": math.pi,
                             "PI_2": 2 * math.pi,
                             "SQRT2": math.sqrt(2.0),
                             "DEG": 180.0 / math.pi,
                             "RAD": math.pi / 180.0,
                             "E": math.e,
                             "GAMMA": 0.57721566490153286060651209008240243,
                             "PHI": (math.sqrt(5.0) + 1.0) / 2.0,
                            }
        self.eval_locals = {}


    def safe_eval(self, txt):
        """
        Evaluate the text given in 'txt'. If it has an assignment operator
        assign the value to the appropriately named key in 'eval_locals'.

        If 'immutable==True', allow values to be evaluated and stored, but
        do not allow them to be overwritten. Return the string representation
        of the computed value.
        """

        # For each call, make sure the override variables are in place.
        self.eval_locals.update(self.override)

        if "=" in txt:
            name, expression = [_.strip() for _ in txt.split("=", 2)]

            if self.immutable and name in self.eval_locals.keys():
                raise Exception("Cannot change '{0}'".format(name)
                                + " because it is immutable. Context:"
                                + " '{0}'".format(txt))

            if name in self.override:
                print("* !!! override variable '{0}' cannot".format(name)
                      + " be updated. Context: '{0}'".format(txt))
            else:
                self.eval_locals[name] = eval(expression,
                                              self.safe_globals,
                                              self.eval_locals)

            return repr(self.eval_locals[name])
        else:
            return repr(eval(txt, self.safe_globals, self.eval_locals))


    def load_file(self):
        """
        This file reads the file given by self.src_f and saves the list
        of lines to self.src_txt. It is modular so that testing can
        occur without actual files.
        """
        with open(self.src_f, 'r') as src:
            self.src_txt = src.readlines()

    def dump_file(self):
        """
        This function dumps the processed file to self.dst_f. It is
        modular so that testing can occur without actual files. If
        dst_f is 'None', do not write to disk.
        """
        if self.dst_f is None:
            return

        with open(self.dst_f, 'w') as dst:
            # line breaks should already be present
            dst.write("".join(self.dst_txt))

    def process(self):
        """
        Output
        -------

        eval_locals  dictionary of variable names and values that were
                     evaluated while processing src_txt.
        """

        if self.chatty:
            print("\n" + "*" * 72)
            print("* Calling SimpleAprepro.process()")
            print("* --- Current state")
            print("*   src_f = {0}".format(self.src_f))
            print("*   dst_f = {0}".format(self.dst_f))
            print("*   chatty = {0}".format(self.chatty))
            print("*   override = {0}".format(self.override))

        # Process the input file line-by-line
        for jdx, line in enumerate(self.src_txt):
            split_line = re.split(r"({.*?})", line)
            for idx, chunk in enumerate(split_line):
                if chunk.startswith("{") and chunk.endswith("}"):
                    # Found a chunk to evaluate.
                    split_line[idx] = self.safe_eval(chunk[1:-1])
            joined_line = "".join(split_line)
            if self.chatty:
                print("* {0: 4d}: {1}".format(jdx, repr(joined_line)))
            self.dst_txt.append("".join(split_line))

        if self.chatty:
            print("* End call to SimpleAprepro.process()")
            print("*" * 72 + "\n")

        return self.eval_locals


def test0():
    """
    Test how integers are represented.
    """
    processor = SimpleAprepro("", "")
    processor.src_txt = ["# abc = {abc = 123}", "# abc = { abc }"]
    out = processor.process()
    assert processor.dst_txt == ["# abc = 123", "# abc = 123"]
    assert out == {"abc": 123}

def test1():
    """
    Test how floats are represented with only several digits.
    """
    processor = SimpleAprepro("", "")
    processor.src_txt = ["# abc = {abc = 123.456}", "# abc = { abc }"]
    out = processor.process()
    assert processor.dst_txt == ["# abc = 123.456", "# abc = 123.456"]
    assert out == {"abc": 123.456}

def test2():
    """
    Test how floats are represented with machine precision.
    """
    processor = SimpleAprepro("", "")
    processor.src_txt = ["# abc = {abc = PI}", "# abc = { abc }"]
    out = processor.process()
    assert processor.dst_txt == ["# abc = 3.141592653589793",
                                 "# abc = 3.141592653589793"]
    assert out == {"abc": math.pi}


def simple_aprepro(src_f, dst_f,
                   chatty=True,
                   override=None,
                   immutable=False):
    """
    This function is a simplified interface to the SimpleAprepro class.
    It instantiates and object and calls the process() function and
    returns the dictionary of evaluted values.

    Inputs
    ------

    src_f        filename of the file to process
    dst_f        filename of where to write the processed file. If 'None'
                 return the dictionary of values and do not write to disk.
    chatty       bool defining if messages should be written to screen
    override     dictionary of values to override or None
    immutable    bool defining if variables can be overwritten


    Outputs
    -------

    eval_locals  dictionary of variable names and values that were
                 evaluated while processing src_f.
    """

    processor = SimpleAprepro(src_f, dst_f,
                              chatty=chatty,
                              override=override,
                              immutable=immutable)

    processor.load_file()
    eval_locals = processor.process()
    processor.dump_file()

    return eval_locals

if __name__ == '__main__':
    import argparse

    # Parse inputs
    parser = argparse.ArgumentParser("simple_aprepro.py")
    parser.add_argument('input_file', action='store',
                        help='File to be processed.')
    parser.add_argument('output_file', action='store', default=None,
                        help='File to be written.')
    args = parser.parse_args(sys.argv[1:])

    # Check inputs
    if not os.path.isfile(args.input_file):
        sys.exit("Input file not found: {0}".format(args.input_file))

    # Process file
    simple_aprepro(args.input_file, args.output_file)
