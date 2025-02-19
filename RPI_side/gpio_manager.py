import gpiozero
from typing import Union

class GPIO_Manager:
    # keeps track of GPIO object references used as CS or digital inputs
    # create a GPIO object based on a string descriptor received from master laptop via a packet
    # `get` function to return an existing GPIO reference given a string descriptor

    # example usage
    # gm = GPIO_Manager()
    # T_2 = T_CLICK_2(spi = my_spi, cs = gm.getCS(this_sig.gpio)) # the get function will putIfAbsent
    # gm.release_all_gpios()

    def __init__(self):
        self.gpio_dict = dict()
    
    def get_gpio(self, gpio_str: str) -> Union[gpiozero.DigitalInputDevice, gpiozero.DigitalOutputDevice]:
        # gpio_str is like "GPIO26" or one of the formats specified by https://gpiozero.readthedocs.io/en/stable/recipes.html#pin-numbering

        # this function will add a gpio object to the dictionary if it doesn't already exist
        return self.gpio_dict.get(gpio_str)
    
    def put_gpio(self, gpio_str: str, chType: str) -> None:
        # gpio_str is like "GPIO26" or one of the formats specified by https://gpiozero.readthedocs.io/en/stable/recipes.html#pin-numbering
        # chType is one of ["ai", "ao", "di", "do"]; only the di will be initialized as a digital input
        # all others will be digital outputs

        if chType.lower() == "di":
            # the di input requires a pullup
            self.gpio_dict[gpio_str] = gpiozero.DigitalInputDevice(pin=gpio_str, pull_up=True)
        # elif chType.lower() == "ao":
            # TODO: remove this pullup from initialization when we've implemented hardware pullup resistors for the T2's CS line
            # self.gpio_dict[gpio_str] = gpiozero.DigitalOutputDevice(pin=gpio_str, pull_up=True)
            # ok. DigitalOutput devices cannot be configured to have a pullup resistor. Will have to settle for inital_value=1
        elif chType.lower() == "in":
            self.gpio_dict[gpio_str] = gpiozero.LED(gpio_str, active_high=True, initial_value=False)
        else:
            self.gpio_dict[gpio_str] = gpiozero.DigitalOutputDevice(pin = gpio_str, initial_value = bool(1))
    
    def release_gpio(self, gpio_str: str):
        if gpio_str in self.gpio_dict:
            self.gpio_dict[gpio_str].close()
            self.gpio_dict.pop(gpio_str)
        
    def release_all_gpios(self):
        for gpio in self.gpio_dict.values():
            gpio.close()
        self.gpio_dict.clear()
