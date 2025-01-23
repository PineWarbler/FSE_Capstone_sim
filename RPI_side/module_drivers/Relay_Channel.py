import gpiozero

class RELAY_CHANNEL:
    def __init__(self, gpio_out_pin : gpiozero.DigitalOutputDevice):
        self.gpio_out_pin = gpio_out_pin # use the gpio_manager class to fetch the GPIO object
    
    def writeState(self, state: bool) -> None:
        self.gpio_out_pin.value = state

    def close(self) -> None:
        pass