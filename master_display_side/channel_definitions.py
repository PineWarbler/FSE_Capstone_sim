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
    13: "GPIO20"
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
    
    def __str__(self):
        return f"Channel_Entry object: {self.name} at board slot position {self.boardSlotPosition} with GPIO {self.gpio}"

channels = []
channels.append(Channel_Entry(name = "DPT", boardSlotPosition = 11, sig_type="ao", units="PSI", realUnitsLowAmount=60.0, realUnitsHighAmount=80.0))
channels.append(Channel_Entry(name="IVT", boardSlotPosition=12, sig_type="ai", units="mA", 
                          realUnitsLowAmount=0.0, realUnitsHighAmount=20.0))
