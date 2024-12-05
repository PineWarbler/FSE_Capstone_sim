# -*- coding: utf-8 -*-
"""
Created on Wed Nov 13 13:26:36 2024

@author: REYNOLDSPG21
"""

import spidev
import time
import gpiozero # because RPi.GPIO is unsupported on RPi5

import sys
sys.path.insert(0, "/home/fsepi51/Documents/FSE_Capstone_sim") # allow this file to find other project modules

from ChipSelect_Abstraction import Master_CS

class R_Click:
    
    V_REF = 2.048 # voltage reference for the ADC chip
    R_SHUNT = 4.99 # ohms.  shunt resistor through which the signal current flows.
    BIT_RES = 12 # of ADC
    
    def __init__(self, output_channel_name, spi, cs: Master_CS):
        self.output_channel_name = output_channel_name
        self.spi_master = spi
        self.cs_master = cs
        
    def _twoBytes_to_counts(byteList: list[int]) -> int:
        ''' combines the two 8-bit words into a single 12-bit word that contains actual ADC count'''
        if len(byteList) != 2: # byteList should be a list containing two 8-bit integers
            raise ValueError(f"Expected byte list of length 2, but received length {len(byteList)}")
            
        mask = 0x1F7E
        combined_word = (byteList[0]<<8) + byteList[1]
        return (combined_word & mask) >> 1

    def _counts_to_mA(self, counts: int) -> float:
        return (1000 * self.V_REF * counts)/(self.R_SHUNT * 2**self.BIT_RES * 20) # see derivation in design notes

    def _twoBytes_to_mA(self, byteList: list[int]) -> float:
        return self._counts_to_mA(self._twoBytes_to_counts(byteList))
    
    def read_mA(self) -> float:
        self.cs_master.select(self.output_channel_name)
        rawResponse = self.spi.readbytes(2)
        self.cs_master.deselect_all()
        
        return self._twoBytes_to_mA(rawResponse)
    
    def close(self) -> None:
        pass
    
    def __str__(self) -> str:
        return f"R Click with channel name: {self.output_channel_name}"
    
    
    
if __name__ == "__main__":
    
    # --- INITIALIZE SPI ---
    bus = 0 # RPI has only two SPI buses: 0 and 1
    device = 0 # Device is the chip select pin. Set to 0 or 1, depending on the connections
    # max allowable device index is equal to number of select pins minus one
    spi = spidev.SpiDev()
    # Open a connection to a specific bus and device (chip select pin)
    spi.open(bus, device) # connects to /dev/spidev<bus>.<device>
    # Set SPI speed and mode
    spi.max_speed_hz = 5000 # start slow at first
    spi.mode = 0
    spi.bits_per_word = 8 # would prefer 16, but this is the maximum supported by the Pi's spi driver
    
    # can't use the built-in cs pin because it would interrupt the 16-bit word into three individual words
    # the DAC would reject the frame because it's not a contiguous 16 bits
    spi.no_cs
    spi.threewire
    
    cs_pins = [gpiozero.DigitalOutputDevice("GPIO26", initial_value = bool(1))]
    cs = Master_CS("one-to-one", spi, cs_pins, ["ch1"])
    
    r = R_Click("ch1", spi, cs)
    
    while True:
        try:
            mA_val = r.read_mA()
            print(f"loop current: {mA_val} mA")
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            break
    
   
    # cleanup
    r.close()
    spi.close()
    for p in cs_pins:
        p.close()
