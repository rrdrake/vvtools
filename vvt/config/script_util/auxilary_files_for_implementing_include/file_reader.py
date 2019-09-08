#!/usr/bin/env python3
import sys

for filename in sys.argv[1:]:
    print("\n----- ----- {0}".format(filename))
    with open(filename, 'r') as F:
        print("===== read()")
        print(repr(F.read()))

    with open(filename, 'r') as F:
        print("===== readlines()")
        print(repr(F.readlines()))
