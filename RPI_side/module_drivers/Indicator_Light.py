import gpiozero

class INDICATOR_LIGHT:
    '''controls a status light on the outside of the simulator box'''
    def __init__(self, gpio_cs_pin: gpiozero.DigitalOutputDevice):
        self.gpio_cs_pin = gpio_cs_pin
        self.led_obj = gpiozero.LED(self.gpio_cs_pin, active_high=True, initial_value=False)
    
    def setBlink(self, on_time=1, off_time=1):
        # configure the led to blink forever with for a given on_time and off_time
        self.led_obj.blink(on_time=on_time, off_time=off_time, n=None, background=True)
    
    def turnOn(self):
        self.led_obj.on()

    def turnOff(self):
        self.led_obj.off()
    
    def close(self) -> None:
        self.led_obj.close()
    
    def __str__(self) -> str:
        return f"Indicator Light driver assigned to gpio pin: {self.gpio_cs_pin}"

