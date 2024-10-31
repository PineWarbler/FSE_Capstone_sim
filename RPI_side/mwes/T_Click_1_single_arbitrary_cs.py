# interactively interface with a single Mikroe T-Click 1 using an arbitrary CS pin
# Note: the MCP4921's SPI interface is three-wire (i.e. no MISO)

import spidev
import time
import gpiozero # because RPi.GPIO is unsupported on RPi5
import binascii

# these lines to free any previous lgpio resources. see https://forums.raspberrypi.com/viewtopic.php?t=362014
import os
os.environ['GPIO_PIN_FACTORY'] = os.environ.get('GPIOZERO_PIN_FACTORY','mock')


class T_CLICK_1:
    R_IN = 20E3 # ohms
    V_REF = 4.096 # Volts
    BIT_RES = 12 # for the MCP4921
    BITS_PER_TRANSACTION = 16
    
    def __init__(self, SHDNB:int=1, GAB:int=1, BUF:int=0): # originally 1,1,0
        ''' T_CLICK_1 board has an MCP4921 (12-bit DAC) that feeds an XTR116 loop driver (voltage-to-current converter).
        This class provides a single function, `get_command_for(maVal)`, that considers both chips' behaviors. You can input
        a current value (4-20mA), and this class will tell you what 16-bit command you must place on the T_Click_1's SPI bus
        to produce this current value
        
        Inputs: (see MCP4921 datasheet)
        SHDNB : Shutdown Bar
        GAB : GA Bar "Output Gain Select bit"; if 1, no gain. If 0, 2x gain
            Note: V_ref on T_Click board is 4.096 V, so no gain is needed
        BUF : whether to use input buffer (limits output voltage swing) default is 0 (unbuffered)
        
        '''
        self.SHDNB = SHDNB
        self.GAB = GAB
        self.BUF = BUF
    
    def get_command_for(self, maVal: float) -> list[int]:
        ''' based on MCP4921 datasheet; returns a list of integers!'''
        # first four msb bits are for config instructions
        command = 0
        command += 0 << self.BITS_PER_TRANSACTION-1
        command += self.BUF << self.BITS_PER_TRANSACTION - 2
        command += self.GAB << self.BITS_PER_TRANSACTION -3
        command += self.SHDNB << self.BITS_PER_TRANSACTION - 4
        
        # add the actual DAC signal code
        command += self._convert_mA_to_DAC_code(maVal)

        # sending as single int doesn't work.  Try splitting into two 8-bit ints
        asBytes = int(command).to_bytes(int(T_CLICK_1.BITS_PER_TRANSACTION/8), byteorder="big")
        
        returnList = [int(b) for b in asBytes] # separate into 8-bit chunks for the SPI channel's limitations on word length
        print(f"return list is {returnList}")
        return returnList
    
    
    def _convert_mA_to_DAC_code(self, mA_value: float) -> int:
        ''' based on XTR116 datasheet '''
        # according to XTR116 datasheet, I_out = 100*I_in
        # The T-Click datasheet uses a 20k resistor between the DAC and the XTR116, and "The input voltage at the I_IN pin is zero"
        # Thus, I_out=100*(V_DAC/R_in) where R_in=20k
        # And V_DAC = (I_out*R_in)/100
        # for the DAC, V_out=(V_REF*D_N)/2^12 where 
            # V_REF=4.096V (on board, pulled from XTR116's VREF output)
            # and D_N is the digital input value
        # therefore, I_out = (100*V_REF*D_N)/(R_IN * 2^12)
        # by inspection, the maximum output current is 20.48 mA
        Amps_value = mA_value / 1E3
        
        DAC_CODE_float = abs((Amps_value * T_CLICK_1.R_IN * 2**T_CLICK_1.BIT_RES) / (100*T_CLICK_1.V_REF))
        DAC_CODE_float = min(DAC_CODE_float, 2**T_CLICK_1.BIT_RES-1) # safety
        return int(DAC_CODE_float)



def writeToSPI(spi, cs_obj, msgList: list[int]):
    ''' 
    a wrapper for spi.xfer2 that allows a custom CS pin
    '''
    # what if cs input pin on T_CLICK1 is active high?
    cs_obj.off() # initiate transaction by pulling low
    spi.writebytes(msgList)
    cs_obj.on()

def mainLoop(t1: T_CLICK_1, spi, cs_obj):
    while True:
        try:
            maValStr = input("mA value to write: ")
            
            try:
                maVal = float(maValStr)
                if maVal<0 or maVal>21:
                    raise ValueError
            except ValueError:
                print("invalid input. Try again")
                continue
            
            # 12 bits is not an integer number of bytes, so need to pass bits instead?
            print(f"maVal to write is {maVal}")
            writeToSPI(spi, cs_obj, t1.get_command_for(maVal))
            
        except KeyboardInterrupt:
            break
    spi.close()


if __name__ == "__main__":

    CS_PIN = "GPIO26" # arbitrary CS pin number on RPI
    # or an supply an integer. see https://gpiozero.readthedocs.io/en/stable/recipes.html#pin-numbering


    # bus zero supports up to 2 CS assignments; bus one supports up to 3 CS pins
    # https://forums.raspberrypi.com/viewtopic.php?t=126912
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
    
    # disable the default CS pin
    spi.no_cs
    spi.threewire # the MCP4921 doesn't have a MISO pin

    #config GPIO
    cs = gpiozero.DigitalOutputDevice(CS_PIN)
    cs.off() # default to non-active spi
    
    t1 = T_CLICK_1()
    
    
    mainLoop(t1, spi, cs)
    
    spi.close()
    
    cs.close()
