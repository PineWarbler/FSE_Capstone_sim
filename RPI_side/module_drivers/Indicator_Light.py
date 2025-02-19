import gpiozero

class INDICATOR_LIGHT:
    '''controls a status light on the outside of the simulator box'''
    def __init__(self, led_pin: gpiozero.LED):
        self.led_pin = led_pin
        # self.led_obj = gpiozero.LED(self.gpio_cs_pin, active_high=True, initial_value=False)
    
    def setBlink(self, on_time=1, off_time=1):
        # configure the led to blink forever with for a given on_time and off_time
        self.led_pin.blink(on_time=on_time, off_time=off_time, n=None, background=True)
    
    def turnOn(self):
        self.led_pin.on()

    def turnOff(self):
        self.led_pin.off()
    
    def close(self) -> None:
        self.led_pin.close()
    
    def __str__(self) -> str:
        return f"Indicator Light driver assigned to LED pin: {self.led_pin}"

