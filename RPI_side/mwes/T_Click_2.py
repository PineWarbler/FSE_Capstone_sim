# -*- coding: utf-8 -*-
"""
Created on Mon Oct 21 16:06:35 2024

@author: REYNOLDSPG21
"""
import binascii

# import spidev
# import time
# import RPi.GPIO as GPIO

# this driver is a port of the C library from Mikroe
# https://libstock.mikroe.com/projects/view/5135/4-20ma-t-2-click

class DAC997_status:
    ''' data model to parse and interpret the 8-bit STATUS word'''
    def __init__(self, dac_res: int, errlvl_pin_state: int, ferr_sts: int, 
                 spi_timeout_err: int, loop_sts: int, curr_loop_sts: int):
        ''' dummy init; if want to initialize using an 8-bit word, use method `from_8bit_response` '''
        self.dac_res = None
        self.errlvl_pin_state = None
        self.ferr_sts = None
        self.spi_timeout_err = None
        self.loop_sts = None
        self.curr_loop_sts = None
    
    @classmethod
    def from_8bit_response(cls, status_word: int):
        ''' alternative constructor. Call using d = DAC997_status.from_8bit_response(my_status_word)'''
        # force to int to allow for masking operations below
        if isinstance(status_data, str):
            status_data = int(status_data, 2)
            if status_data > 2**8-1:
                raise ValueError("Failed to cast argument to int")
           
        dac_res = int((status_data & T_CLICK_2.STATUS_DAC_RES_BIT_MASK) >> 5 ) # should always output 111_2 = 7_10
        
        errlvl_pin_state = int((status_data & T_CLICK_2.STATUS_ERRLVL_PIN_BIT_MASK) >> 4 )
        
        # frame error sticky bit (1: Frame error has occurred since last Status read) (0: no frame error occurred)
        ferr_sts = int((status_data & T_CLICK_2.STATUS_ERRLVL_PIN_BIT_MASK) >> 3 )
        
        spi_timeout_err = int((status_data & T_CLICK_2.STATUS_SPI_TIMEOUT_ERR_BIT_MASK) >> 2 )
        
        loop_sts = int((status_data & T_CLICK_2.STATUS_LOOP_STS_BIT_MASK) >> 1 )
        
        curr_loop_sts = int((status_data & T_CLICK_2.STATUS_CURR_LOOP_STS_BIT_MASK) >> 0 )
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

spi_master(spi, CS_obj)
dacobj.setoutputcurr(amount, spi) * assumes CS has already been treated (not ideal because might need to toggle CS pin mid-command)
dacobj.setoutputcurr(amount, spi_master, cs_master)
OR
spi_master.

class T_CLICK_2:
    # R_IN = 20E3 # ohms
    # V_REF = 4.096 # Volts
    BIT_RES = 16 # for the DAC161S997
    BITS_PER_TRANSACTION = 24
    BYTES_PER_TRANSACTION = BITS_PER_TRANSACTION/8
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
    
    def __init__(self, output_channel_name, spi, cs: Master_CS):
        self.spi_master = spi
        # check for essential configuration: bits per word = 16
        if self.spi_master.bits_per_word != T_CLICK_2.BITS_PER_TRANSACTION:
            print(f"overriding spi bits per word from {self.spi_master.bits_per_word} to {T_CLICK_2.BITS_PER_TRANSACTION}.")
            self.spi_master.bits_per_word = T_CLICK_2.BITS_PER_TRANSACTION
            
        self.cs_master = cs
        self.output_channel_name = output_channel_name # used in calls to cs_master.select
        self.dac997_status = DAC997_status() # initialize to empty data model
    
    def write_data(self, reg: int, data_in: int): # TODO: add return type hint for type of `resp`
        ''' joins data to reg addr into a 24-bit (3-byte) word, then writes over SPI, 
        returning a 24-bit response which is the previous content held in the shift register'''
        # modeled after c420mat2_write_data
        full_command = (reg << T_CLICK_2.BIT_RES) + data_in # first 8 bits is REG, last 16 are actual data
        
        self.cs_master.select(self.output_channel_name) # prepare for write   
        resp = self.spi_master.xfer2([full_command]) # also catches the shift register contents that are being shifted out
        self.cs_master.deselect_all()
        return resp
        # self.dac997_status = DAC997_status.from_8bit_response(resp) # parse response and store in member variable
        
    
    def set_output_current(self, mA_val: float) -> None:
        ''' produces as 24-bit word REG+DACCODE, and writes it to SPI '''
        # modeled after c420mat2_set_output_current
        if (mA_val < CURRENT_OUTPUT_RANGE_MIN) or (mA_val > CURRENT_OUTPUT_RANGE_MAX):
            raise ValueError(f"The requested current value of {mA_val} mA is outside the valid range of the transmitter.")
            
        self.write_data(self.REG_DACCODE, self._convert_mA_to_DAC_code(mA_val))
        
    
    def _convert_mA_to_DAC_code(self, mA_value: float) -> int:
        ''' see datasheet '''
        # I_LOOP = 24 mA (DACCODE / 2**16) (pg 18 of datasheet)
        # so DACCODE = (I_LOOP/24mA) * 2**16
        return int((mA_value / 24) * 2**T_CLICK_2.BIT_RES)
    
    def read_status_register(self) -> 'DAC997_status':
        # requires two SPI transactions: one to send read command, another with dummy data to flush out the data from the registers
#         The first transaction shifts in the register read command; an 8-bits of command byte followed by 16-bits of dummy data. The register read
# command transfers the contents of the internal register into the FIFO. The second transaction shifts out the FIFO
# contents; an 8-bit command byte (which is a copy of previous transaction) followed by the register data.
        _ = self.write_data(self.REG_STATUS, self.DUMMY) # 8 bit command + 16 bits of dummy data
        register_contents = self.write_data(self.REG_STATUS, self.DUMMY) # repeated to flush
        # TODO: What is the 8-bit command to read register? C drivers claim it's 0x09, but datasheet
        # says its (0x09 | 0x080). see datasheet page 11
        self.dac997_status = DAC997_status.from_8bit_response(register_contents)
        return self.dac997_status
    
       
        

if __name__ == "__main__":
    t2 = T_CLICK_2()
    # apparently, python printing does weird things to bytearrays....
    # see https://stackoverflow.com/a/17093845
    print(f"for 4 ma: {binascii.hexlify(t2.get_command_for(4))}")
    print(f"for 20 ma: {binascii.hexlify(t2.get_command_for(20))}")
    # check. These values agree with datasheet page 19
    
    