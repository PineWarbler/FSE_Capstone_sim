# -*- coding: utf-8 -*-
"""
Created on Sun Oct 20 14:19:42 2024

@author: REYNOLDSPG21
"""

from abc import ABC, abstractmethod
import warnings
# import RPi.GPIO as GPIO

# import spidev

# spi = spidev.SpiDev()

# csh = Master_CS(type="16decoder")
# csh.select_pins  = [25, 26, 29, 30] # msb to lsb

# for pin_no, pin_state in Master_CS.get_pin_states_for_selecting_channel(0):
#     GPIO.output(pin, pin_status)
    
# spi.xfer2(msgList)

# then write all pins high again

# class DAC_997:
#     # only generates codes, does not send...
#     def write_val()


class Master_CS:
    # different types: linear (list), 4/8/16 decoder options
    # outputs the pin status in order to write to chip at name
    # needs a list of pins and a list of output channel names
    allowed_kinds = ["one-to-one", "2-4_decoder", "3-8_decoder", "4-16_decoder", "5-32_decoder"]
    
    def __init__(self, kind, spi, gpio_pin_nums: list[int], output_channel_names: list[any], strobe_pins: list[int]=None, spi_polarity="active_low"):
        '''
        `kind`: str, may be one of ["one-to-one", "2-4_decoder", "3-8_decoder", "4-16_decoder", "5-32_decoder"]
        
        `spi` : spi object
        
        `gpio_pin_nums`:
                These are the physical gpio pins responsible (mediately or immediately) for controlling CS lines downstream
                In the case of "one-to-one", the gpio pins are directly connected to the CS lines.
                In the decoder cases, the gpio pins are selector pins on a decoder IC, which this class
                assumes produces outputs sufficient to activate the CS bus with the proper polarity.
                
        `gpio_pin_nums` goes from msb to lsb
        
        `strobe_pins` : on the 74xxx series of decoders, deselecting all outputs is achieved only by
        setting one of these pins high.  This argument is only needed if `kind` contains "decoder"
        
        e.g. `cs=Master_CS("2-4_decoder", [24, 19], ["sig_foo", 1, 3.5, myObj])`
        `for pin_no, pin_state in cs.get_pin_states_for_selecting_channel(3.5):
             GPIO.output(pin, pin_status)`
        '''
        self.kind = kind
        self.spi = spi
        self.gpio_pin_nums = gpio_pin_nums
        self.output_channel_names = output_channel_names
        self.spi_polarity = spi_polarity
        self.strobe_pins = strobe_pins
        
        # TODO: add conflict checking if user doesn't provide strobe pins for kind "decoder"
        if self.strobe_pins is not None:
            print("[init] default set first strobe pin to high")
            # GPIO.output(self.strobe_pins[0], 1) # disable decoder outputs by default
        
        #config GPIO
        # GPIO.setmode(GPIO.BCM)
        # for n in gpio_pin_nums:    
        #     GPIO.setup(n, GPIO.OUT)
        # GPIO.setwarnings(False)
    
    @property # getter
    def kind(self):
        return self._kind
    @kind.setter
    def kind(self, o_kind):
        if o_kind not in Master_CS.allowed_kinds:
            raise ValueError(f"The kind of Master_CS is invalid. Must be one of {Master_CS.allowed_kinds}")
        self._kind = o_kind
    
    # TODO: add property for spi object with setter type checking
        
    @property # getter
    def gpio_pin_nums(self):
        return self._gpio_pin_nums
    
    @gpio_pin_nums.setter
    def gpio_pin_nums(self, o_gpio_pin_nums):
        if not isinstance(o_gpio_pin_nums, list):
            raise ValueError("gpio_pin_nums must be a list")
            
        # if the user provides too many gpio pins for the decoder type specified...
        if self.kind!="one-to-one" and len(o_gpio_pin_nums) > int(self.kind[0]):
            self._gpio_pin_nums = o_gpio_pin_nums[0:int(self.kind[0])+1]
            warnings.warn(f"You provided {len(o_gpio_pin_nums)} gpio pin numbers, which is too many for the decoder of type `{self.kind}` which you selected.\n Will truncate pins to first {int(self.kind[0])}.")
        self._gpio_pin_nums = o_gpio_pin_nums
    
    @property # getter
    def output_channel_names(self):
        return self._output_channel_names
    @output_channel_names.setter
    def output_channel_names(self, o_output_channel_names):
        # note: length of output_channel_names could be less than max capacity of decoder
        # if user leaves some decoder channels unused
        if "decoder" in self.kind and len(o_output_channel_names)>2**len(self.gpio_pin_nums):
            raise ValueError("Type is decoder, but number of gpio_pins is insufficient to satisfy the number of outputs")
        if self.kind=="one-to-one" and len(o_output_channel_names)>len(self.gpio_pin_nums):
            warnings.warn(f"For one-to-one mode, expected to receive list no longer than gpio_pin_nums, but received list of length {len(o_output_channel_names)} instead. Some of the later channels will not be reachable")
        self._output_channel_names = o_output_channel_names
        
    @property # getter
    def spi_polarity(self):
        return self._spi_polarity
    @spi_polarity.setter #
    def spi_polarity(self, o_spi_polarity: str):
        # also map the string to an integer for later calls to GPIO output
        if o_spi_polarity == "active_low":
            self.active_as_int = 0
        elif o_spi_polarity == "active_high":
            self.active_as_int = 1
        else:
            raise ValueError(f"Spi polarity {o_spi_polarity} is not an option")
    
    def get_pin_states_for_selecting_channel(self, output_channel_to_select) -> tuple[list, list]:
        ''' Note: on actual decoder ic, outputs might be inverted or non-inverted (outside control of this code)
        Therefore, make sure that circuitry is implemented to ensure proper active low/high
        for CS line
        
        returns a list of the pin names and a list of their corresponding gpio pin states (1 or 0)
        '''
        if output_channel_to_select not in self.output_channel_names:
            raise AttributeError(f"The requested channel name `{output_channel_to_select}` does not exist in the object!")
            
        if "decoder" in self.kind:
            output_idx = self.output_channel_names.index(output_channel_to_select) # find index of the requested channel name
            
            my_str = self._get_padded_bin_str(output_idx, len(self.gpio_pin_nums))
            pin_states = [int(i) for i in my_str] # convert to list of integers
            return (self.gpio_pin_nums, pin_states)
        
        elif self.kind=="one-to-one":
            output_idx = self.output_channel_names.index(output_channel_to_select)
            if output_idx>=len(self.gpio_pin_nums):
                raise IndexError(f"The requested channel is at index {output_idx}, which exceeds the number of gpio_pins")
            # if self.spi_polarity=="active_low":
            #     active=0
            # else:
            #     active=1
            pin_states = len(self.gpio_pin_nums)*[int(not self.active_as_int)] # initialize to all pins inactive
            pin_states[output_idx] = self.active_as_int
            return ((self.gpio_pin_nums), pin_states)
        
        else:
            raise ValueError
    
    def _get_padded_bin_str(self, bin_num: int, padded_len: int) -> str:
        bin_str = bin(bin_num)[2:] # omit the "0b" prefix
        bin_str = ("0" * (padded_len-len(bin_str))) + bin_str
        return bin_str
    
    def select(self, output_channel_to_select: any) -> None:
        ''' write to the gpio pin states needed to select the requested chip '''
        pin_nums, pin_states = self.get_pin_states_for_selecting_channel(output_channel_to_select)
        for i in range(0, len(pin_nums)):
            print(f"pin_no: {pin_nums[i]}, pin_state: {pin_states[i]}")
            # GPIO.output(pin_nums[i], pin_states[i])
            
        if self.strobe_pins is not None:
            print(f"set strobe pin {self.strobe_pins[0]} to high")
            # GPIO.output(self.strobe_pins[0], 1) # after this command, the demux will be active
        
    def deselect_all(self) -> None:
        # need to set one of of decoder strobe inputs HIGH
        
        # write all gpio pins to polarity type
        if self.kind == "one-to-one":
            for i in range(0, len(self.gpio_pin_nums)):
                print(f"one-to-one: set pin {self.gpio_pin_nums[i]} to {not self.active_as_int}.")
                # GPIO.output(self.gpio_pin_nums[i], not self.active_as_int)
        
        if self.strobe_pins is not None:
            print(f"set strobe pin {self.strobe_pins[0]} to high.")
            # GPIO.output(self.strobe_pins[0], 1) # after this command, the demux will be active
            
    def close(self) -> None:
        pass
        # GPIO.cleanup()
    