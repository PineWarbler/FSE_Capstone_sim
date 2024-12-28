import gpiozero

class COMPARATOR_CLICK:
    def __init__(self, gpio_in_pin : gpiozero.DigitalInputDevice):
        self.gpio_in_pin = gpio_in_pin # use the gpio_manager class to fetch the GPIO object
    
    def readState(self) -> int:
        return int(self.gpio_in_pin.value)
    
    def close(self) -> None:
        pass