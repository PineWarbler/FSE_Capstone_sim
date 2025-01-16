class Channel_Entry:
    ''' 
    This class defines each signal that the Master Laptop
    could send or receive to/from the simulator.  

    name: str # like "AOP", "IVT", etc. What the operator will call to send a command
    boardSlotPosition : int
        The module's position on the carrier board, as a unique key.
        It is easy to use a two-digit key. First digit is carrier board number; second
        digit is the module position on that board.  e.g. 13 -> carrier board 1, module slot 3 
        But could also be a string, float, or other datatype. 
        The position on the carrier board in which this module is installed. Used as an intermediate key
        to map to the GPIO pin. Because it's easier for the user to understand the board slot position than the GPIO pin number...
    
    sig_type : str  # one of ["ao", "ai", "do", "di"]
    # for the digital signals, there are no units, so the following three variables can be None
    units : str | None # what will be shown on the GUI. e.g. PSI, A, Fahrenheit, etc.
    realUnitsLowAmount : float | None # lower bound of the signal's magnitude
    realUnitsHighAmount : float | None # upper bound of the signal's magnitude
    '''

    # don't touch this dictionary unless you know what you're doing!
    _slot2gpio = {
    11: "GPIO26",
    12: "GPIO21",
    "r1": "GPIO19" # relay slot 1
    }

    def __init__(self, name : str, boardSlotPosition : int, sig_type : str, units : str | None,
                 realUnitsLowAmount : str | None, realUnitsHighAmount : str | None):
        self.name = name
        self.boardSlotPosition = boardSlotPosition
        self.sig_type = sig_type
        self.units = units
        self.realUnitsLowAmount = realUnitsLowAmount
        self.realUnitsHighAmount = realUnitsHighAmount

        self.gpio = self._slot2gpio.get(boardSlotPosition)
    
    def mA_to_EngineeringUnits(self, mA_val):
        if self.sig_type[0].lower() == "a":
            return ((mA_val-4.0) / (20.0 - 4.0)) * (self.realUnitsHighAmount - self.realUnitsLowAmount) + self.realUnitsLowAmount
        else:
            return None
    
    def EngineeringUnits_to_mA(self, engUnits):
        if self.sig_type[0].lower() == "a":
            return 4.0 + ((engUnits - self.realUnitsLowAmount) / (self.realUnitsHighAmount - self.realUnitsLowAmount)) * (20.0 - 4.0)
        else:
            return None
    
    def EngUnits_str(self, mA_val):
        return f"{self.mA_to_EngineeringUnits(mA_val)} {self.units}"
    
    def __str__(self):
        return f"Channel_Entry object: {self.name} at board slot position {self.boardSlotPosition} with GPIO {self.gpio}"

channels = []
channels.append(Channel_Entry(name = "Motor Status", boardSlotPosition = "r1", sig_type="do", units=None, realUnitsLowAmount=None, realUnitsHighAmount=None))
channels.append(Channel_Entry(name="UVT", boardSlotPosition=13, sig_type="ai", units="percent", 
                          realUnitsLowAmount=0, realUnitsHighAmount=100)) # note that the analog inputs are measured in percentage of open/close

channels.append(Channel_Entry(name="SPT", boardSlotPosition=12, sig_type="ao", units="PSI", 
                          realUnitsLowAmount=97.0, realUnitsHighAmount=200.0))
# other analog outputs
channels.append(Channel_Entry(name="DPT", boardSlotPosition=None, sig_type="ao", units="PSI", 
                          realUnitsLowAmount=100.0, realUnitsHighAmount=200.0))
channels.append(Channel_Entry(name="MAT", boardSlotPosition=None, sig_type="ao", units="Amps", 
                          realUnitsLowAmount=145, realUnitsHighAmount=300.0))

# other analog inputs
channels.append(Channel_Entry(name="IVT", boardSlotPosition=None, sig_type="ai", units="percent", 
                          realUnitsLowAmount=0.0, realUnitsHighAmount=100.0))

# digital inputs
channels.append(Channel_Entry(name="AOP", boardSlotPosition=12, sig_type="di", units="PSI", 
                          realUnitsLowAmount=97.0, realUnitsHighAmount=200.0))

print(channels[1].mA_to_EngineeringUnits(4.0))
print(channels[1].mA_to_EngineeringUnits(12.0))
print(channels[1].mA_to_EngineeringUnits(20.0))

print(channels[1].EngineeringUnits_to_mA(0))
print(channels[1].EngineeringUnits_to_mA(50))
print(channels[1].EngineeringUnits_to_mA(100))

print(channels[2].EngineeringUnits_to_mA(97))
print(channels[2].EngineeringUnits_to_mA(199))