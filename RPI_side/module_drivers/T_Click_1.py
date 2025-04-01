# interactively interface with a single Mikroe T-Click 1 using an arbitrary CS pin
# Note: the MCP4921's SPI interface is three-wire (i.e. no MISO)

import spidev
import gpiozero # because RPi.GPIO is unsupported on RPi5

class T_CLICK_1:
    R_IN = 20E3 # ohms
    V_REF = 4.096 # Volts
    BIT_RES = 12 # for the MCP4921
    BITS_PER_TRANSACTION = 16

    CURRENT_OUTPUT_RANGE_MIN = 3 # arbitrarily chosen
    CURRENT_OUTPUT_RANGE_MAX = 20.048 # calculated from pcb component choices
    
    def __init__(self, gpio_cs_pin, spi: spidev.SpiDev, SHDNB:int=1, GAB:int=1, BUF:int=0): # originally 1,1,0
        ''' T_CLICK_1 board has an MCP4921 (12-bit DAC) that feeds an XTR116 loop driver (voltage-to-current converter).
        This class provides a single function, `write_mA`, that considers both chips' behaviors. 
        
        Inputs: (see MCP4921 datasheet)
        gpio_cs_pin : gpio pin object used for chip select
        spi : spidev object to use for the SPI communication
        SHDNB : Shutdown Bar
        GAB : GA Bar "Output Gain Select bit"; if 1, no gain. If 0, 2x gain
            Note: V_ref on T_Click board is 4.096 V, so no gain is needed
        BUF : whether to use input buffer (limits output voltage swing) default is 0 (unbuffered)
        
        '''
        self.gpio_cs_pin = gpio_cs_pin
        self.spi_master = spi

        self.SHDNB = SHDNB
        self.GAB = GAB
        self.BUF = BUF
    
    def write_mA(self, mA_val: float) -> None:
        # writeToSPI(spi, cs_obj, t1.get_command_for(maVal)
        if (mA_val < self.CURRENT_OUTPUT_RANGE_MIN) or (mA_val > self.CURRENT_OUTPUT_RANGE_MAX):
            print(f"The requested current value of {mA_val} mA is outside the valid range of the transmitter.")
            # don't throw an exception because this driver will need to run uninterrupted in a main loop
        
        # first four msb bits are for config instructions
        command = 0
        command += 0 << self.BITS_PER_TRANSACTION-1
        command += self.BUF << self.BITS_PER_TRANSACTION - 2
        command += self.GAB << self.BITS_PER_TRANSACTION -3
        command += self.SHDNB << self.BITS_PER_TRANSACTION - 4
        
        # according to XTR116 datasheet, I_out = 100*I_in
        # The T-Click datasheet uses a 20k resistor between the DAC and the XTR116, and "The input voltage at the I_IN pin is zero"
        # Thus, I_out=100*(V_DAC/R_in) where R_in=20k
        # And V_DAC = (I_out*R_in)/100
        # for the DAC, V_out=(V_REF*D_N)/2^12 where 
            # V_REF=4.096V (on board, pulled from XTR116's VREF output)
            # and D_N is the digital input value
        # therefore, I_out = (100*V_REF*D_N)/(R_IN * 2^12)
        # by inspection, the maximum output current is 20.48 mA
        Amps_value = mA_val / 1E3
        DAC_CODE_float = abs((Amps_value * T_CLICK_1.R_IN * 2**T_CLICK_1.BIT_RES) / (100*T_CLICK_1.V_REF))
        DAC_CODE_float = min(DAC_CODE_float, 2**T_CLICK_1.BIT_RES-1) # safety
    
        # add the actual DAC signal code
        command += int(DAC_CODE_float)
        # sending as single int doesn't work.  Try splitting into two 8-bit ints
        asBytes = int(command).to_bytes(int(T_CLICK_1.BITS_PER_TRANSACTION/8), byteorder="big")
        
        bytesList = [int(b) for b in asBytes] # separate into 8-bit chunks for the SPI channel's limitations on word length

        self.gpio_cs_pin.value = 0 # initiate transaction by pulling low
        self.spi_master.writebytes(bytesList)
        self.gpio_cs_pin.value = 0
    
    def close(self) -> None:
        return


if __name__ == "__main__":

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
    cs1 = gpiozero.DigitalOutputDevice("GPIO13") # board slot 14
    cs2 = gpiozero.DigitalOutputDevice("GPIO19") # board slot 15
    cs1.on() # default to non-active spi
    cs2.on()


    drivers = [T_CLICK_1(gpio_cs_pin = cs1, spi = spi), T_CLICK_1(gpio_cs_pin = cs2, spi = spi)]
               
    while True:
        try:
            driverIndex = int("Select index of driver to write to [0,1]: ")
            
            maValStr = input("mA value to write: ")
            
            try:
                maVal = float(maValStr)
                if maVal<4 or maVal>21:
                    raise ValueError
            except ValueError:
                print("invalid input. Try again")
                continue
            
            print(f"maVal to write is {maVal}")
            drivers[driverIndex].write_mA(maVal)
            
        except KeyboardInterrupt:
            break

    spi.close()

    for d in drivers:
        d.close()
    
    cs1.close()
    cs2.close()
