# -*- coding: utf-8 -*-
"""
Created on Sun Oct 20 14:19:42 2024

@author: REYNOLDSPG21
"""

import warnings
import gpiozero # because RPi.GPIO is unsupported on RPi5

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
    
    def __init__(self, kind, spi, gpio_pins: list[gpiozero.output_devices.DigitalOutputDevice], 
                 output_channel_names: list[any], 
                 strobe_pins: list[gpiozero.output_devices.DigitalOutputDevice]=None, 
                 spi_polarity="active_low"):
        '''
        `kind`: str, may be one of ["one-to-one", "2-4_decoder", "3-8_decoder", "4-16_decoder", "5-32_decoder"]
        
        `spi` : spi object
        
        `gpio_pins` : list[gpiozero.output_devices.DigitalOutputDevice]
                These are the physical gpio pins responsible (mediately or immediately) for controlling CS lines downstream
                In the case of "one-to-one", the gpio pins are directly connected to the CS lines.
                In the decoder cases, the gpio pins are selector pins on a decoder IC, which this class
                assumes produces outputs sufficient to activate the CS bus with the proper polarity.
                These must be provided by the calling function because gpiozero pin states fall back to their defaults
                once their gpiozero objects lose scope (not what we want if we have multiple instances of this class)
                
        `gpio_pins` goes from msb to lsb for selection order (i.e. if want to select 28 in (26,27,28,29) on a 2-4_decoder with cs_pins=(4,5), 
                would output 01 (for index 1=28))
        
        `strobe_pins` : list[gpiozero.output_devices.DigitalOutputDevice]
            on the 74xxx series of decoders, deselecting all outputs is achieved only by
            setting one of these pins high.  This argument is only needed if `kind` contains "decoder"
        
        e.g. `cs=Master_CS("2-4_decoder", my_spi, [gpio_obj1, gpio_obj_baz], ["sig_foo", 1, 3.5, myObj], strobe_pins=[gpio_obj_strobe1])`
        `cs.select("sig_foo")
        <spi transfer>
        `cs.deselect_all()`
        '''
        self.kind = kind
        self.spi = spi
        self.gpio_pins = gpio_pins
        self.output_channel_names = output_channel_names
        self.spi_polarity = spi_polarity
        self.strobe_pins = strobe_pins
        
        # TODO: add conflict checking if user doesn't provide strobe pins for kind "decoder"
        
        # disable decoder outputs by setting at least one high
        # also, make a list of objects as a member var to ensure that scope is persistent within the class
        # the gpiozero library resets pins to their default states after loss of scope (not what we want)...
        if self.strobe_pins is not None:
            for p in self.strobe_pins:
                p.value = 1
            print("[init] ensured that strobe_pins are High")      

        
        #config GPIO
        # GPIO.setmode(GPIO.BCM)
        # for n in gpio_pins:    
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
    def gpio_pins(self):
        return self._gpio_pins
    
    @gpio_pins.setter
    def gpio_pins(self, o_gpio_pins):
        if not isinstance(o_gpio_pins, list):
            raise ValueError("gpio_pins must be a list")
            
        # if the user provides too many gpio pins for the decoder type specified...
        if self.kind!="one-to-one" and len(o_gpio_pins) > int(self.kind[0]):
            self._gpio_pins = o_gpio_pins[0:int(self.kind[0])+1]
            warnings.warn(f"You provided {len(o_gpio_pins)} gpio pin numbers, which is too many for the decoder of type `{self.kind}` which you selected.\n Will truncate pins to first {int(self.kind[0])}.")
        self._gpio_pins = o_gpio_pins
    
    @property # getter
    def output_channel_names(self):
        return self._output_channel_names
    @output_channel_names.setter
    def output_channel_names(self, o_output_channel_names):
        # note: length of output_channel_names could be less than max capacity of decoder
        # if user leaves some decoder channels unused
        if "decoder" in self.kind and len(o_output_channel_names)>2**len(self.gpio_pins):
            raise ValueError("Type is decoder, but number of gpio_pins is insufficient to satisfy the number of outputs")
        if self.kind=="one-to-one" and len(o_output_channel_names)>len(self.gpio_pins):
            warnings.warn(f"For one-to-one mode, expected to receive list no longer than gpio_pins, but received list of length {len(o_output_channel_names)} instead. Some of the later channels will not be reachable")
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
            
            my_str = self._get_padded_bin_str(output_idx, len(self.gpio_pins))
            pin_states = [int(i) for i in my_str] # convert to list of integers
            return (self.gpio_pins, pin_states)
        
        elif self.kind=="one-to-one":
            output_idx = self.output_channel_names.index(output_channel_to_select)
            if output_idx>=len(self.gpio_pins):
                raise IndexError(f"The requested channel is at index {output_idx}, which exceeds the number of gpio_pins")
            # if self.spi_polarity=="active_low":
            #     active=0
            # else:
            #     active=1
            pin_states = len(self.gpio_pins)*[int(not self.active_as_int)] # initialize to all pins inactive
            pin_states[output_idx] = self.active_as_int
            return ((self.gpio_pins), pin_states)
        
        else:
            raise ValueError
    
    def _get_padded_bin_str(self, bin_num: int, padded_len: int) -> str:
        bin_str = bin(bin_num)[2:] # omit the "0b" prefix
        bin_str = ("0" * (padded_len-len(bin_str))) + bin_str
        return bin_str
    
    def select(self, output_channel_to_select: any) -> None:
        ''' write to the gpio pin states needed to select the requested chip '''
        pin_nums, pin_states = self.get_pin_states_for_selecting_channel(output_channel_to_select)
        
        # write those digital states to the pins
        for i in range(0, len(pin_nums)):
            gpiozero.DigitalOutputDevice(pin_nums[i]).value = pin_states[i]
            print(f"pin_no: {pin_nums[i]}, pin_state: {pin_states[i]}")
            # GPIO.output(pin_nums[i], pin_states[i])
            
        # on the 74xxx series of decoders, enabling the demuxer is achieved when all strobe pins are low
        if self.strobe_pins is not None:
            for sp in self.strobe_pins:
                gpiozero.DigitalOutputDevice(sp).off() # after this command, the demux will be active
                print(f"set strobe pin {self.strobe_pins[0]} to off")
            # GPIO.output(self.strobe_pins[0], 1) 
        
    def deselect_all(self) -> None:
        # need to set one of of decoder strobe inputs HIGH
        
        # write all gpio pins to polarity type
        if self.kind == "one-to-one":
            for p in self.gpio_pins:
                print(f"one-to-one: set pin {p} to {not self.active_as_int}.")
                p.value = int(not self.active_as_int)
                # GPIO.output(self.gpio_pins[i], not self.active_as_int)
        
        if self.strobe_pins is not None:
            print(f"set strobe pin {self.strobe_pins[0]} to high.")
            self.strobe_pins[0].value = 1
            # GPIO.output(self.strobe_pins[0], 1) # after this command, the demux will be active
            
    def close(self) -> None:
        pass
        # GPIO.cleanup()
    