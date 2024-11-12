import gpiozero
import time

inPin = gpiozero.DigitalInputDevice("GPIO26")

while True:
    try:
        print(f"value is {inPin.value}")
        time.sleep(1)
    except KeyboardInterrupt:
            break
inPin.close()