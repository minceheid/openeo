#!/usr/bin/env python3

import sys
sys.path.append('..')

from openeoConfig import openeoConfigClass

config=config()

print("Empty")
print(config)

print ("One entry")
config.set("testmodule","testkey","testvalue")
print(config)
