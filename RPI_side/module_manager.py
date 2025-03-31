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
from module_drivers.Indicator_Light import INDICATOR_LIGHT

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
    
    def execute_command(self, gpio_str: str, chType: str, val: float | int) -> Tuple[dataEntry, list[errorEntry]]:
        '''
        Executes a command from the socket, given the module's gpio string, channel type, and value.  This class
        is responsible for choosing the appropriate driver instance for the requested channel and for allocating
        a gpio reservation with self.gpio_manager.
        If `chType` is "ai", then the `val` (int) will be interpreted as the number of measurements to average 
        (LPF) before returning a value
        This method can also return multiple error entries. See the implementation for details.

        :param str gpio_str: the gpio string of the module (e.g. "GPIO13")
        :param str chType: one of ["ao", "ai", "di", "do"]
        :param float|int val: the value to write to the module
        '''
        if gpio_str not in self.module_dict:
            print(f"[Module_Manager] making a module entry for {gpio_str} as a {chType}")
            self.make_module_entry(gpio_str = gpio_str, chType = chType)
            print(f"[module_manager] made a new module entry. module_dict is now {self.module_dict}")

        driverObj = self.module_dict.get(gpio_str)[1] # second element in value list is the driver object
        print(f"[module_manager] driverObj is {driverObj}")
        
        valueResponse = None # we will update these later
        errorResponse_list = []

        # first element is the channel type
        if chType.lower() == "ao": # then it's a T_CLICK_2 instance
            try:
                driverObj.write_mA(val)
            except ValueError: # although the GUI should have already screened out invalid commands...
                print(f"Transmitter driver refused to assert {val} mA")
            # now check for errors...
            print(f" --- T2 status --- after write {val}")
            driverObj.read_status_register()
            print(str(driverObj.dac997_status))
            print("----")
            if driverObj.dac997_status.curr_loop_sts == 1: # then a loop error is happening right now
                errorResponse_list.append(errorEntry(source = "ao", criticalityLevel = "High", description = f"Loop error detected:{gpio_str}"))
            if driverObj.dac997_status.dac_res != 7: # defined on datasheet. Indicates that the chip can be reached via SPI.
                errorResponse_list.append(errorEntry(source = "ao", criticalityLevel = "High", description = f"SPI communication error detected:{gpio_str}"))
            # don't update the valueResponse with anything. This is no ao signal, so don't return anything
        elif chType.lower() == "ai": # then it's an R_CLICK instance
            # the ai adc readings can be noisy, so do a simple average to attenuate noise
            numMeasurements = max(int(val), 1) # at least one measurement
            sum = 0
            for _ in range(numMeasurements):
                sum += driverObj.read_mA()
                
            ma_reading = sum / numMeasurements
            valueResponse = dataEntry(chType = chType, gpio_str = gpio_str, val = ma_reading, time = time.time())

            if ma_reading == 0: # there is always a small amount of random noise that can be read on the adc chip to indicate a valid SPI connection
                errorResponse_list.append(errorEntry(source = "ai", criticalityLevel = "High", description = f"SPI communication error detected:{gpio_str}"))

        elif chType.lower() == "do": # then it's a relay channel instance
            print("[module_manager] entered do branch to write val: {bool(val)}")
            driverObj.writeState(state = bool(val))
            # don't update either the value response or the error response list
        elif chType.lower() == "di": # then it's a comparator channel instance
            di_value = int(driverObj.readState())
            valueResponse = dataEntry(chType = chType, gpio_str = gpio_str, val = di_value, time = time.time())

        # the "in" chtype is not controlled by packet data. The RPi locally controls the indicator lights, but
        # we still need the GUI to tell the RPi which GPIO pin the lights are using
        elif chType.lower() == "in": # indicator light
            # different indication modes: 2:blink rapidly, 1:solid on, 0:off
            if val==2:
                driverObj.setBlink(on_time=0.3, off_time=0.3)
            elif val==1:
                driverObj.turnOn()
            elif val==0:
                driverObj.turnOff()
            valueResponse = None
            errorResponse_list.append(errorEntry(source = "Module Manager", criticalityLevel = "Medium", description = "The indicator light channel is reserved. Any commands from master will be ignored."))
        else:
            valueResponse = None
            errorResponse_list.append(errorEntry(source = "Module Manager", criticalityLevel = "Medium", description = f"Invalid channel type given {chType} for module at {gpio_str}."))

        return (valueResponse, errorResponse_list)


    def make_module_entry(self, gpio_str: str, chType: str):
        # add an entry to the dictionary because it doesn't exist yet.
        # Also need to request the gpio_manager to add a GPIO object to itself
        self.gpio_manager.put_gpio(gpio_str, chType = chType)
        print(f"[module_manager.make_module_entry] after put_gpio, list is {self.gpio_manager.gpio_dict}")

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
        elif chType.lower() == "in": # this channel is not writable by the master. We include it here so that the 
            # Pi can initialize it at its own startup
            driverObj = INDICATOR_LIGHT(led_pin = self.gpio_manager.get_gpio(gpio_str))
        else:
            driverObj = None
            warnings.warn(f"[module_manager] Invalid channel type {chType}")
        print("[Module_Manager make_module_entry] will insert key {gpio_str} with values {chType} and {driverObj}")
        self.module_dict[gpio_str] = [chType, driverObj]
        print(f"[module_manager.make_module_entry] new module_dict is {self.module_dict}")
    
    def release_all_modules(self):
        for chType, driver_obj in self.module_dict.values():
            driver_obj.close()

        self.gpio_manager.release_all_gpios()
        self.module_dict.clear()

