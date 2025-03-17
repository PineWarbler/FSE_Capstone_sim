import spidev
import time
import gpiozero # because RPi.GPIO is unsupported on RPi5

CS_PIN = "GPIO20" # arbitrary CS pin number on RPI
    # or an supply an integer. see https://gpiozero.readthedocs.io/en/stable/recipes.html#pin-numbering

def twoBytes_to_counts(byteList: list[int]) -> int:
    # byteList should be a list containing two 8-bit integers
    mask = 0x1F7E
    combined_word = (byteList[0]<<8) + byteList[1]
    return (combined_word & mask) >> 1

def counts_to_mA(counts: int) -> float:
    V_REF = 2.048 # voltage reference for the ADC chip
    R_SHUNT = 4.99 # ohms.  shunt resistor through which the signal current flows.
    BIT_RES = 12
    return (1000 * V_REF * counts)/(R_SHUNT * 2**BIT_RES * 20) # see derivation in design notes

def twoBytes_to_mA(byteList: list[int]) -> float:
    # print(f"count is {twoBytes_to_counts(byteList)}")
    return counts_to_mA(twoBytes_to_counts(byteList))
    
try:

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
    
    while True:
        try:
            
            cs.off() # default to non-active spi

            resp = spi.readbytes(2) # read 16 bits, even though there will be four dummy bits

            cs.on() # end transaction

            print(f"resp is {resp}")
            print(f"  in mA: {twoBytes_to_mA(resp)}")
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            break

except Exception as e:
    print("handle the error")
    print(e)
finally:

    spi.close()

    cs.close()
