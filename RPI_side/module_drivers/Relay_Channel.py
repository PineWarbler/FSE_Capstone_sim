import gpiozero

class RELAY_CHANNEL:
    def __init__(self, gpio_out_pin : gpiozero.DigitalOutputDevice):
        self.gpio_out_pin = gpio_out_pin # use the gpio_manager class to fetch the GPIO object
    
    def writeState(self, state: bool) -> None:
        self.gpio_out_pin.value = state

    def close(self) -> None:
        pass

if __name__ == "__main__":
    p = gpiozero.DigitalOutputDevice("GPIO6")
    rc = RELAY_CHANNEL(gpio_out_pin = p)
    
    import time
    rc.writeState(True)
    time.sleep(3)
    rc.writeState(False)
    time.sleep(3)
    p.close()
