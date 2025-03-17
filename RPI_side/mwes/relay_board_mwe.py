import gpiozero
import time

outPin = gpiozero.DigitalOutputDevice("GPIO19", initial_value=True)

while True:
    try:
        onOffStr = input("on or off? ")
        
        if onOffStr == "on":
            outPin.off()
        elif onOffStr == "off":
            outPin.on()
        else:
            print("That's not an option. Try again.")
            continue
            
    except KeyboardInterrupt:    
        outPin.close()
        break
