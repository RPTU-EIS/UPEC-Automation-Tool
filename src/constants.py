""" Constants used throughout the project. """

""" Directions for Fan Analysis """
FANOUT = True
FANIN = False

""" Port Direction (match PySlang) """
INPUT   = 0
OUTPUT  = 1
INOUT   = 2
UNKNOWN = -1  # -1 instead of None so comparisons are safe

""" Instance Names """
INST_1 = "U1"
INST_2 = "U2"

""" Suffix to be appended to the Top Module Name in the Miter Circuit """
MITER_SUFFIX = "_miter"
