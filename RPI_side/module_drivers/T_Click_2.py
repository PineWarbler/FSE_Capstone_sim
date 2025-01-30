# -*- coding: utf-8 -*-
"""
Created on Mon Oct 21 16:06:35 2024

@author: REYNOLDSPG21
"""
# import binascii
import spidev
import gpiozero
import time
import math

import sys
sys.path.insert(0, "/home/fsepi51/Documents/FSE_Capstone_sim") # allow this file to find other project modules

# these lines to free any previous lgpio resources. see https://forums.raspberrypi.com/viewtopic.php?t=362014
import os
os.environ['GPIO_PIN_FACTORY'] = os.environ.get('GPIOZERO_PIN_FACTORY','mock')

# import spidev
# import time
# import RPi.GPIO as GPIO

# this driver is a port of the C library from Mikroe
# https://libstock.mikroe.com/projects/view/5135/4-20ma-t-2-click

class DAC997_status:
    ''' data model to parse and interpret the 8-bit STATUS word'''
    def __init__(self, dac_res: int = 0, errlvl_pin_state: int = 0, ferr_sts: int = 0, 
                 spi_timeout_err: int = 0, loop_sts: int = 0, curr_loop_sts: int=0):
        ''' dummy init; if want to initialize using an 8-bit word, use method `from_8bit_response` '''
        self.dac_res = dac_res
        self.errlvl_pin_state = errlvl_pin_state
        self.ferr_sts = ferr_sts
        self.spi_timeout_err = spi_timeout_err
        self.loop_sts = loop_sts
        self.curr_loop_sts = curr_loop_sts
    
    @classmethod
    def from_response(cls, resp: list[int]):
        ''' alternative constructor. Call using d = DAC997_status.from_8bit_response(my_status_word)'''
        # force to int to allow for masking operations below
        if len(resp) != 3:
            raise ValueError(f"Expected length 3, but got length {len(resp)}")
        
        # status_word = resp[0] << 16
        # status_word += resp[1] << 8
        # status_word += resp[2]
        status_word = resp[2]
        # only care about last 8 lsbs
        print(f"[from_response] status word is: {status_word}")
        
        dac_res = int((status_word & T_CLICK_2.STATUS_DAC_RES_BIT_MASK) >> 5 ) # should always output 111_2 = 7_10
        
        errlvl_pin_state = int((status_word & T_CLICK_2.STATUS_ERRLVL_PIN_BIT_MASK) >> 4 )
        
        # frame error sticky bit (1: Frame error has occurred since last Status read) (0: no frame error occurred)
        ferr_sts = int((status_word & T_CLICK_2.STATUS_ERRLVL_PIN_BIT_MASK) >> 3 )
        
        spi_timeout_err = int((status_word & T_CLICK_2.STATUS_SPI_TIMEOUT_ERR_BIT_MASK) >> 2 )
        
        loop_sts = int((status_word & T_CLICK_2.STATUS_LOOP_STS_BIT_MASK) >> 1 )
        
        curr_loop_sts = int((status_word & T_CLICK_2.STATUS_CURR_LOOP_STS_BIT_MASK) >> 0 )
        return cls(dac_res, errlvl_pin_state, ferr_sts, spi_timeout_err, loop_sts, curr_loop_sts)
    
    
    def __str__(self):
        bs = ""
        bs += f"dac_res : {self.dac_res}\n"
        bs += f"errlvl_pin_state : {self.errlvl_pin_state}\n"
        bs += f"frame-error status : {self.ferr_sts}\n"
        bs += f"spi_timeout_error : {self.spi_timeout_err}\n"
        bs += f"loop_status : {self.loop_sts}\n"
        bs += f"curr_loop_status : {self.curr_loop_sts}"
        return bs

class T_CLICK_2:
    # R_IN = 20E3 # ohms
    # V_REF = 4.096 # Volts
    BIT_RES = 16 # for the DAC161S997
    BITS_PER_TRANSACTION = 24
    BYTES_PER_TRANSACTION = int(BITS_PER_TRANSACTION/8)
    # first 8 bits are command, last 16 are data
    
    REG_XFER = 0x01
    REG_NOP = 0x02
    REG_WR_MODE = 0x03
    REG_DACCODE = 0x04 # used to write 16-bit mA value to chip
    REG_ERR_CONFIG = 0x05
    REG_ERR_LOW = 0x06
    REG_ERR_HIGH = 0x07
    REG_RESET = 0x08
    REG_STATUS = 0x09 # read-only
    
    DUMMY = 0xFFFF # 16 bits of dummy data, used for register flush during reads
    
    # status bitmasks
    STATUS_DAC_RES_BIT_MASK = 0x00E0
    STATUS_ERRLVL_PIN_BIT_MASK = 0x0010
    STATUS_FERR_STS_BIT_MASK = 0x0008
    STATUS_SPI_TIMEOUT_ERR_BIT_MASK = 0x0004
    STATUS_LOOP_STS_BIT_MASK = 0x0002
    STATUS_CURR_LOOP_STS_BIT_MASK = 0x0001
    
    # absolute current limits in mA
    ERR_CURRENT_LIMIT_12_mA = 12.0
    CURRENT_LIMIT_RANGE_MIN = 2.0
    CURRENT_LIMIT_RANGE_MAX = 24.1
    CURRENT_OUTPUT_RANGE_MIN = 3.9
    CURRENT_OUTPUT_RANGE_MAX = 20.0
    
    def __init__(self, gpio_cs_pin, spi : spidev.SpiDev, make_persistent : bool = True):
        '''
        gpio_cs_pin : str, the GPIO object that will be used as the chip select pin. Uses the gpiozero library
        spi : spidev.SpiDev, the SPI object that will be used to communicate with the `997
        '''
        self.spi_master = spi           
        self.gpio_cs_pin = gpio_cs_pin # use the gpio_manager class to fetch the GPIO object
        self.dac997_status = DAC997_status(None, None, None, None, None, None) # initialize to empty data model
        
        if make_persistent:
            # disable SPI timeout error reporting (i.e. maintain output current indefinitely)
            # otherwise, the chip will assert output current level set in ERR_LOW reg, which by default is 0x24 -> 3.37 mA
            self.set_error_config_mode(50, True, False, False,
                                  True, 100, True)
            
    
    def _write_data(self, reg: int, data_in: int): # TODO: add return type hint for type of `resp`
        ''' joins data to reg addr into a 24-bit (3-byte) word, then writes over SPI, 
        returning a 24-bit response which is the previous content held in the shift register'''
        # modeled after c420mat2_write_data
        full_command = (reg << T_CLICK_2.BIT_RES) + data_in # first 8 bits is REG, last 16 are actual data
        # print(f"full command as int is {full_command}")
        # split into three 8-bit words for Pi's spi limitation
        asBytes = int(full_command).to_bytes(self.BYTES_PER_TRANSACTION, byteorder="big") # produces a bytearray of length 3
        write_list = [int(b) for b in asBytes]
        # print(f"write_list is {write_list}")
        self.gpio_cs_pin.value = 0 # initiate transaction by pulling cs low
    
        resp = self.spi_master.xfer(write_list) # also catches the shift register contents that are being shifted out

        self.gpio_cs_pin.value = 1 # end transaction by pulling cs high
        return resp        
    
    def write_mA(self, mA_val: float) -> None:
        ''' produces as 24-bit word REG+DACCODE, and writes it to SPI '''
        # modeled after c420mat2_set_output_current
        if (mA_val < self.CURRENT_OUTPUT_RANGE_MIN) or (mA_val > self.CURRENT_OUTPUT_RANGE_MAX):
            raise ValueError(f"The requested current value of {mA_val} mA is outside the valid range of the transmitter.")
        # print(f"{mA_val} mA converted to DAC code is {self._convert_mA_to_DAC_code(mA_val)}")
        self._write_data(self.REG_DACCODE, self._convert_mA_to_DAC_code(mA_val))
        
    
    def _convert_mA_to_DAC_code(self, mA_value: float) -> int:
        ''' see datasheet '''
        # I_LOOP = 24 mA (DACCODE / 2**16) (pg 18 of datasheet)
        # so DACCODE = (I_LOOP/24mA) * 2**16
        return int((mA_value / 24) * 2**T_CLICK_2.BIT_RES)
    
    def read_status_register(self) -> 'DAC997_status':
        # requires two SPI transactions: one to send read command, another with dummy data to flush out the data from the registers
        # The first transaction shifts in the register read command; an 8-bits of command byte followed by 16-bits of dummy data. The register read
        # command transfers the contents of the internal register into the FIFO. The second transaction shifts out the FIFO
        # contents; an 8-bit command byte (which is a copy of previous transaction) followed by the register data.
        r = self._write_data(self.REG_STATUS| 0x80, self.DUMMY) # 8 bit command + 16 bits of dummy data ORed with read prefix (see datasheet page 11)
        # print(f"first response is {r}")
        
        register_contents = self._write_data(self.REG_STATUS | 0x80, self.DUMMY) # repeated to flush, returns a list
        # print(f"raw register contents: {register_contents}") # this returns a list of three 8-bit numbers

        self.dac997_status = DAC997_status.from_response(register_contents)
        return self.dac997_status
    
    def write_NOP(self) -> None:
        '''datasheet: indicates that the SPI connection is functioning and is used to avoid SPI_INACTIVE errors.'''
        self._write_data(self.REG_NOP, self.DUMMY)
        
    def set_error_config_mode(self, retry_loop_time_ms: float, enable_retry_loop: bool, maskLooperr: bool, dis_loop_err_errb: bool,
                              mask_spi_err: bool, spi_timeout_ms: float, mask_spi_tout: bool):
        # convert non-bools to ints for command building later
        code_loop_retry_time = int((retry_loop_time_ms / 50.0) - 1) # convert from ms to code
        code_spi_timeout_ms = int((retry_loop_time_ms / 50.0) - 1)
        
        code_loop_retry_time = min(7, code_loop_retry_time) # chop down to fit within the three bit field length
        code_spi_timeout_ms = min(7, code_spi_timeout_ms)
        
        data_word = 0
        data_word += code_loop_retry_time << 7 # three bits reserved, so max is 400 ms
        data_word += int(enable_retry_loop) << 6
        data_word += int(maskLooperr) << 5
        data_word += int(dis_loop_err_errb) << 4
        data_word += int(code_spi_timeout_ms) << 3
        data_word += int(mask_spi_tout) << 0
        
        # print(f"set_error_config_mode command is {data_word}")
        self._write_data(self.REG_ERR_CONFIG, data_word)
    
    def set_err_low_current_level(self, mAVal: float) -> None:
        ''' define the output current amount to assert when an error occurs.
            default on chip startup is 0x24 -> 3.37 mA
            must be between 0x00 (0 mA) and 0x80 (12 mA)'''
        code = math.floor(mAVal * 10.666) # linear interpolation
        padded_code = (code << 8) + 0x00 # shift to the right to make word 16 bits (see datasheet)
        self._write_data(self.REG_ERR_LOW, padded_code)
    
    def reset(self) -> None:
        ''' return all writable registers to their defaults '''
        self._write_data(self.REG_RESET, 0xC33C) # see datasheet pg 15
        self.write_NOP()
        
    def close(self) -> None:
        self.reset()
       
        

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

    cs = gpiozero.DigitalOutputDevice("GPIO19", initial_value = bool(1))
   
    t2 = T_CLICK_2(gpio_cs_pin = cs, spi = spi, make_persistent = True)
    
    print(t2.read_status_register())
    
    
    
    # disable SPI timeout error reporting (i.e. maintain output current indefinitely)
    # otherwise, the chip will assert output current level set in ERR_LOW reg, which by default is 0x24 -> 3.37 mA
    # t2.set_error_config_mode(50, True, False, False,
                              # True, 100, True)
               
    # t2.set_err_low_current_level(1.0) # the default 3.37 mA seems a bit much...
    
    t2.write_mA(10.5) # because we've disabled SPI timeout error, this current level will hold indefinitly until loop error

    
    time.sleep(10) # only sleep to delay the call to close(), which will reset spi timeout error reporting (end indefinite current hold)
    
    # print("after set current command: ")
    # print(t2.read_status_register())
    
    # for _ in range(0, 30):
        # print(t2.read_status_register())
        # time.sleep(1)
    
    # cleanup
    t2.close()
    spi.close()
    cs.close()