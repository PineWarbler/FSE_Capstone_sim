# -*- coding: utf-8 -*-
"""
Created on 1/17/25

@author: REYNOLDSPG21
"""

# import spidev
import time
import gpiozero # because RPi.GPIO is unsupported on RPi5

# import sys
# sys.path.insert(0, "/home/fsepi51/Documents/FSE_Capstone_sim") # allow this file to find other project modules

class Digital_Input_Module:
    def __init__(self, gpio_in_pin : gpiozero.DigitalInputDevice):
        self.gpio_in_pin = gpio_in_pin
    
    def readState(self) -> int:
        return int(self.gpio_in_pin.value)
    
    def close(self):
        pass

if __name__ == "__main__":
    my_pin = gpiozero.DigitalInputDevice("GPIO19", pull_up=True)
    dip = DigitalInput_Pullup(gpio_in_pin = my_pin)
    while True:
        try:
            print(f"state is {dip.readState()}")
            time.sleep(0.5)
        except KeyboardInterrupt:
            break
    dip.close()
    my_pin.close()
