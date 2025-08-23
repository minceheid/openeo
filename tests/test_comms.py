#!/usr/bin/env python3

import sys
sys.path.insert(0,'..')
from EO_comms.MiniPro2 import MiniPro2
from EO_comms.HomeHub import HomeHub


if MiniPro2.identify_hardware():
    eo=MiniPro2()
else:
    eo=HomeHub()

eo.test()

