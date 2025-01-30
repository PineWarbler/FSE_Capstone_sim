from typing import Union, Tuple
import warnings
import gpiozero
import time
import spidev

import sys
sys.path.append("..") # include parent directory in path

from PacketBuilder import dataEntry, errorEntry
from gpio_manager import GPIO_Manager
from module_drivers.T_Click_2 import T_CLICK_2
from module_drivers.Digital_Input_Module import Digital_Input_Module
from module_drivers.R_Click import R_CLICK
from module_drivers.Relay_Channel import RELAY_CHANNEL

class Module_Manager:
    # maintain a list of modules (e.g. R_CLICK, COMPARATOR_CLICK)
    #  initiated by the master, over the socket 
    # has an instance of GPIO_manager to allocate GPIOs to serve as 
    #  chip selects and digital inputs for the modules

    # also responsible for creating a module if not exist yet
    # or to write a value to a module at the specified gpio pin

    def __init__(self, spi : spidev.SpiDev):
        self.spi = spi
        self.module_dict = dict() # a dict like {"GPIO26" : ["ao", driver_obj]}
        self.gpio_manager = GPIO_Manager() # initialize to empty at first
    
    def execute_command(self, gpio_str: str, chType: str, val: float | int) -> Tuple[dataEntry, errorEntry]:
        '''TODO: write docstring
        '''
        if gpio_str not in self.module_dict:
            print(f"[Module_Manager] making a module entry for {gpio_str} as a {chType}")
            self.make_module_entry(gpio_str = gpio_str, chType = chType)

        driverObj = self.module_dict.get(gpio_str)[1] # second element in value list is the driver object
        print(f"[Module_Manager] Found the driver object {driverObj}")

        # first element is the channel type
        if chType.lower() == "ao": # then it's a T_CLICK_2 instance
            driverObj.write_mA(val)
            # now check for errors...
            if driverObj.dac997_status.curr_loop_sts == 1: # then a loop error is happening right now
                errorResponse = errorEntry(source = f"Analog Output Module", criticalityLevel = "High", description = f"Loop error detected on {gpio_str}.")
            else:
                errorResponse = None
            valueResponse = None
        elif chType.lower() == "ai": # then it's an R_CLICK instance
            ma_reading = driverObj.read_mA()
            valueResponse = dataEntry(chType = chType, gpio_str = gpio_str, val = ma_reading, time = time.time())
            errorResponse = None
        elif chType.lower() == "do": # then it's a relay channel instance
            print(f"[Module_Manager] writingState to {val}")
            driverObj.writeState(state = bool(val))
            valueResponse = None
            errorResponse = None
        elif chType.lower() == "di": # then it's a comparator channel instance
            di_value = int(driverObj.readState())
            valueResponse = dataEntry(chType = chType, gpio_str = gpio_str, val = comparator_value, time = time.time())
            errorResponse = None
        else:
            valueResponse = None
            errorResponse = errorEntry(source = f"Module Manager", criticalityLevel = "Medium", description = f"Invalid channel type given {chType} for module at {gpio_str}.")

        return (valueResponse, errorResponse)


    def make_module_entry(self, gpio_str: str, chType: str):
        # add an entry to the dictionary because it doesn't exist yet.
        # Also need to request the gpio_manager to add a GPIO object to itself
        self.gpio_manager.put_gpio(gpio_str, chType = chType)

        # now create a driver object for the module of the correct type
        if chType.lower() == "ai":
            driverObj = R_CLICK(gpio_cs_pin = self.gpio_manager.get_gpio(gpio_str),
                                spi = self.spi)
        elif chType.lower() == "ao":
            driverObj = T_CLICK_2(gpio_cs_pin = self.gpio_manager.get_gpio(gpio_str),
                                    spi = self.spi)
        
        elif chType.lower() == "di":
            driverObj = Digital_Input_Module(gpio_in_pin = self.gpio_manager.get_gpio(gpio_str))
        elif chType.lower() == "do":
            driverObj = RELAY_CHANNEL(gpio_out_pin = self.gpio_manager.get_gpio(gpio_str))
        else:
            driverObj = None
            warnings.warn(f"[module_manager] Invalid channel type {chType}")
        print("[Module_Manager make_module_entry] will insert key {gpio_str} with values {chType} and {driverObj}")
        self.module_dict[gpio_str] = [chType, driverObj]
    
    def release_all_modules(self):
        for chType, driver_obj in self.module_dict.values():
            driver_obj.close()

        self.gpio_manager.release_all_gpios()
        self.module_dict.clear()

