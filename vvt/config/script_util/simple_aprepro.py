#!/usr/bin/env python3
from __future__ import division  # Make python2 and python3 handle divisions the same.
import sys
import os
import math
import random
import re

class AlarmDict:

    def __getitem__(self, key):
        if key in self.access_history:
            self.access_history[key] = True
        return self.input_dict.__getitem__(key)

    def __setitem__(self, key, value):
        try:
            value = value.replace("\n", "\\n")
        except AttributeError:
            pass  # Turns out 'value' wasn't a string.

        if key not in self.access_history:
            self.access_history[key] = False
        self.input_dict.__setitem__(key, value)

    def __init__(self, input_dict):
        self.input_dict = dict(input_dict.items())
        self.access_history = {}
        for key in self.input_dict:
            self.access_history[key] = False

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
        self.defined_variables = set()
        self.possibly_unused_defined_variables = set()

        # This is a special function that will be stored in 'safe_globals`.
        def aprepro_include(filename):
            with open(filename, 'r') as F:
                txt = F.read()
                if not txt.endswith("\n"):
                    txt += "\n"
                return txt

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

                             # Other variables and functionality
                             'include': aprepro_include,
                            }
        self.eval_locals = AlarmDict(self.override)


    def safe_eval(self, txt, is_comment):
        """
        Evaluate the text given in 'txt'. If it has an assignment operator
        assign the value to the appropriately named key in 'eval_locals'.

        If 'immutable==True', allow values to be evaluated and stored, but
        do not allow them to be overwritten. Return the string representation
        of the computed value.
        """

        if "^" in txt:
            raise Exception("simple_aprepro() only supports exponentiation via **" +
                  " and not ^. As aprepro supports both, please use ** instead." +
                  " Encountered while processing '{0}'".format(txt))

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

            self.defined_variables.add(name)
            if is_comment:
                self.possibly_unused_defined_variables.add(name)
            val = self.eval_locals.input_dict[name]
        else:
            try:
                val = eval(txt, self.safe_globals, self.eval_locals)
            except NameError:
                print("eval() failed. eval_locals = {0}".format(self.eval_locals.input_dict))
                raise


        if type(val) is list:
            # This is for {include("stuff")}
            return val
        elif type(val) is str:
            # Python3 and non-unicode vars in python2.
            return val
        elif str(type(val)) == "<type 'unicode'>":
            # Unicode vars in python2.
            return val.encode('ascii')

        return repr(val)


    def load_file(self):
        """
        This file reads the file given by self.src_f and saves the list
        of lines to self.src_txt. It is modular so that testing can
        occur without actual files.
        """
        with open(self.src_f, 'r') as src:
            self.src_txt = src.read().splitlines()

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
        jdx = 0
        while True:
            if jdx >= len(self.src_txt):
                break
            line = self.src_txt[jdx]

            # Process escaped curly braces.
            clean_line = line.replace("\{", "{").replace("\}", "}")

            # Process the aprepro directive blocks.
            split_line = re.split(r"({[^{]*?})", clean_line)
            is_comment = False
            for idx, chunk in enumerate(split_line):
                if chunk.startswith("{") and chunk.endswith("}"):
                    # Found a chunk to evaluate.
                    split_line[idx] = self.safe_eval(chunk[1:-1], is_comment)
                else:
                    if "#" in chunk:
                        is_comment = True

            joined_line = "".join(split_line)

            # Sometimes when you {include("stuff")} a file, you can get an
            # extra trailing linebreak. Remove it.
            if joined_line.endswith("\n"):
                joined_line = joined_line.rstrip("\n")

            # If there are any linebreaks, expand them and edit the
            # src_txt. Then reprocess this line.
            if joined_line.count("\n") > 0:
                resplit_line = joined_line.splitlines()
                self.src_txt = self.src_txt[:jdx] + resplit_line + self.src_txt[jdx+1:]
                continue

            self.dst_txt.append(joined_line)
            if self.chatty:
                print("* {0: 4d}: {1}".format(jdx, repr(self.dst_txt[-1])))

            jdx += 1

        if self.chatty:
            print("* --- Usage summary")

            keys = [key for key in self.override if self.eval_locals.access_history[key]]
            print("*   Used override variables: {0:d}".format(len(keys)))
            for key in sorted(keys):
                print("*     {0}".format(key))

            keys = [key for key in self.override if not self.eval_locals.access_history[key]]
            print("*   Unused override variables: {0:d}".format(len(keys)))
            for key in sorted(keys):
                print("*     {0}".format(key))

            print("*   Internally-defined variables: {0:d} (! is possibly unused)".format(len(self.defined_variables)))
            for key in sorted(self.defined_variables):

                if not self.eval_locals.access_history[key] and key in self.possibly_unused_defined_variables:
                    print("*   ! {0}".format(key))
                else:
                    print("*     {0}".format(key))

            print("* End call to SimpleAprepro.process()")
            print("*" * 72 + "\n")

        return self.eval_locals


def test0():
    """
    Test how integers are represented.
    """
    processor = SimpleAprepro("", "")
    processor.src_txt = ["# abc = {abc = 123}", "# abc = { abc }"]
    out = processor.process().input_dict
    assert processor.dst_txt == ["# abc = 123", "# abc = 123"]
    assert out == {"abc": 123}

def test1():
    """
    Test how floats are represented with only several digits.
    """
    processor = SimpleAprepro("", "")
    processor.src_txt = ["# abc = {abc = 123.456}", "# abc = { abc }"]
    out = processor.process().input_dict
    assert processor.dst_txt == ["# abc = 123.456", "# abc = 123.456"]
    assert out == {"abc": 123.456}

def test2():
    """
    Test how floats are represented with machine precision.
    """
    processor = SimpleAprepro("", "")
    processor.src_txt = ["# abc = {abc = PI}", "# abc = { abc }"]
    out = processor.process().input_dict
    assert processor.dst_txt == ["# abc = 3.141592653589793",
                                 "# abc = 3.141592653589793"]
    assert out == {"abc": math.pi}

def test3():
    """
    Test for integer division
    """
    processor = SimpleAprepro("", "")
    processor.src_txt = ["# abc = {abc = 1 / 3}"]
    out = processor.process().input_dict
    assert out == {"abc": float(1.0) / float(3.0)}  # all floats, in case you were unsure
    #                                    12345678901234567
    assert processor.dst_txt[0][:17] == "# abc = 0.3333333"

def test4():
    """
    Test for exponentiation.
    """
    processor = SimpleAprepro("", "")
    processor.src_txt = ["# abc = {abc = 2 ** 2}"]
    out = processor.process().input_dict
    assert out == {"abc": 4}
    assert processor.dst_txt == ["# abc = 4",]

def test5a():
    """
    Test for {include("file.txt")}
    """
    with open('to_include.apr', 'w') as F:
        F.write("# iam = {iam = \"teapot\"}\n")
        F.write("This is being included.")

    processor = SimpleAprepro('to_include.apr', '')
    processor.load_file()
    processor.process()

    comp = processor.dst_txt
    gold = ["# iam = teapot", "This is being included."]

    assert len(comp) == len(gold)
    for idx in range(len(comp)):
        assert comp[idx] == gold[idx]

def test5b():
    """
    Test for {include("file.txt")}
    """
    with open('to_include.apr', 'w') as F:
        F.write("middle\n")
        F.write("middle middle\n")
        F.write("middle")

    with open('does_including.apr', 'w') as F:
        F.write("beginning\n")
        F.write("beginning beginning\n")
        F.write("pre{include(\"to_include.apr\")}post\n")
        F.write("end end\n")
        F.write("end")

    processor = SimpleAprepro('does_including.apr', '')
    processor.load_file()
    processor.process()

    comp = processor.dst_txt
    gold = ["beginning", "beginning beginning",
            "premiddle", "middle middle", "middle",
            "post",
            "end end", "end"]

    assert len(comp) == len(gold)
    for idx in range(len(comp)):
        assert comp[idx] == gold[idx]



def test5():
    """
    Test for {include("file.txt")}
    """
    with open('to_include.apr', 'w') as F:
        F.write("# iam = {iam = \"teapot\"}\n")
        F.write("This is being included.")

    with open('does_including.apr', 'w') as F:
        F.write("This is before.\n")
        F.write("{include(\"to_include.apr\")}\n")
        F.write("I'm a little {iam}")

    processor = SimpleAprepro('does_including.apr', '')
    processor.load_file()
    processor.process()

    comp = processor.dst_txt
    gold = ["This is before.", "# iam = teapot", "This is being included.", "I'm a little teapot"]

    assert len(comp) == len(gold)
    for idx in range(len(comp)):
        assert comp[idx] == gold[idx]

def test6():
    """
    Aprepro doesn't expand linebreaks in variables.
    """
    with open('newlines.apr', 'w') as F:
        F.write("# txt = {txt = \"hello\\nworld\"}\n")
        F.write("{txt}")

    processor = SimpleAprepro('newlines.apr', '')
    processor.load_file()
    processor.process()

    comp = processor.dst_txt
    gold = ["# txt = hello\\nworld", "hello\\nworld"]

    assert len(comp) == len(gold)
    for idx in range(len(comp)):
        assert comp[idx] == gold[idx]



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


def main(args):

    import argparse
    import json

    # Parse inputs
    parser = argparse.ArgumentParser("simple_aprepro.py")
    parser.add_argument('input_file', action='store',
                        help='File to be processed.')
    parser.add_argument('output_file', action='store', default=None,
                        help='File to be written.')
    parser.add_argument('--params', dest='parameters_jsonl',
           action='store', default=None,
           help='Create multiple files parameterizing from a jsonl file.')
    parser.add_argument('--chatty', dest='chatty', action='store_true', default=False,
           help='Increase verbosity [default: %(default)s]')
    args = parser.parse_args(args)

    # Check inputs
    if not os.path.isfile(args.input_file):
        sys.exit("Input file not found: {0}".format(args.input_file))

    if args.parameters_jsonl is not None:

        # Ensure that the jsonl file exists.
        if not os.path.isfile(args.parameters_jsonl):
            sys.exit("Parameter file not found: {0}".format(args.parameters_jsol))

        # Read in all the realizations.
        realizations = []
        with open(args.parameters_jsonl, 'r') as F:
            for line in F.readlines():
                realizations.append(json.loads(line, encoding='utf-8'))

        # Create each file.
        base, suffix = os.path.splitext(args.output_file)
        for realization in realizations:
            sorted_items = sorted(realization.items(), key=lambda x: x[0])
            param_string = ".".join(["{0}={1}".format(key, value) for key, value in sorted_items])
            output_f = base + "." + param_string + suffix
            simple_aprepro(args.input_file, output_f, override=realization, chatty=args.chatty)
            print("Wrote {0}".format(output_f))

    else:
        # Process file
        simple_aprepro(args.input_file, args.output_file, chatty=args.chatty)


if __name__ == '__main__':
    main(sys.argv[1:])
