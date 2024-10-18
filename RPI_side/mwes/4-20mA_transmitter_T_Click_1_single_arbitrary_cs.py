# interactively interface with a single Mikroe T-Click 1 using an arbitrary CS pin
# Note: the MCP4921's SPI interface is three-wire (i.e. no MISO)

import spidev
import time
import RPi.GPIO as GPIO

def is_requested_mA_in_bounds(mA_value):
    return mA_value <= 25 # datasheet: XTR11x provide accurate, linear output up to 25 mA


def convert_mA_to_DAC_code(mA_value: float) -> int:
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
    R_IN = 20E3 # ohms
    V_REF = 4.096 # Volts
    BIT_RES = 12 # for the MCP4921
    DAC_CODE_float = (Amps_value * R_IN * 2**BIT_RES) / (100*V_REF)
    DAC_CODE_float = min(DAC_CODE_float, 2**BIT_RES) # safety
    return int(DAC_CODE_float)


def writeToSPI(spi, msgList: list):
    ''' 
    a wrapper for spi.xfer2 that allows custom CS pins
    '''
    GPIO.output(CS_PIN, False) # initiate transaction by pulling low
    spi.xfer2(msgList)
    GPIO.output(CS_PIN, True) # end transaction


def mainLoop():
    while True:
        try:
            maValStr = input("mA value to write: ")
            
            try:
                maVal = int(maValStr)
                if not is_requested_mA_in_bounds(maVal):
                    raise ValueError
            except ValueError:
                print("invalid input. Try again")

            writeToSPI(spi, [convert_mA_to_DAC_code(maVal)])
            
        except KeyboardInterrupt:
            break
    spi.close()

if __name__ == "__main__":

    CS_PIN = 24 # arbitrary CS pin number on RPI


    # bus zero supports up to 2 CS assignments; bus one supports up to 3 CS pins
    # https://forums.raspberrypi.com/viewtopic.php?t=126912
    bus = 0 # RPI has only two SPI buses: 0 and 1
    device = 1 # Device is the chip select pin. Set to 0 or 1, depending on the connections

    spi = spidev.SpiDev()

    # Open a connection to a specific bus and device (chip select pin)
    spi.open(bus, device) # connects to /dev/spidev<bus>.<device>

    # Set SPI speed and mode
    spi.max_speed_hz = 5000 # start slow at first
    spi.mode = 0
    # disable the default CS pin
    spi.no_cs(False) # slightly unintuitive. see https://forums.raspberrypi.com/viewtopic.php?t=178629
    spi.threewire(True) # the MCP4921 doesn't have a MISO pin

    #config GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(CS_PIN, GPIO.OUT)
    GPIO.setwarnings(False)
    
    mainLoop()
