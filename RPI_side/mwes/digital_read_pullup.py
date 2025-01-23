# -*- coding: utf-8 -*-
"""
Created on 1/17/25

@author: REYNOLDSPG21
"""

# import spidev
import time
import gpiozero # because RPi.GPIO is unsupported on RPi5
# from typing import Union
# from statistics import stdev

import sys
sys.path.insert(0, "/home/fsepi51/Documents/FSE_Capstone_sim") # allow this file to find other project modules

my_pin = gpiozero.InputDevice(pin="GPIO26", pull_up=True)

while True:
    try:
        print(f"state is {my_pin.value}")
        time.sleep(0.5)
    except KeyboardInterrupt:
        break
my_pin.close()