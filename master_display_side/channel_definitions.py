from dataclasses import dataclass

@dataclass
class Channel_Entry:
    ''' 
    This class defines each signal that the Master Laptop
    could send or receive to/from the simulator.  
    `name`: like "AOP", "IVT", etc. What the operator will call to send a command
    `boardSlotPosition`: the module's position on the carrier board, as a unique key.
        It is easy to use a two-digit key. First digit is carrier board number; second
        digit is the module position on that board.  e.g. 13 -> carrier board 1, module slot 3 
        But could also be a string, float, or other datatype.
        The simulator will try to output the requested value to the module
        at that position. 
    `sig_type`: one of ["ao", "ai", "do", "di"]

    '''
    name: str # like "AOP", "IVT", etc. What the operator will call to send a command
    boardSlotPosition : int # the actual command that the Pi will understand
    
    sig_type : str  # one of ["ao", "ai", "do", "di"]
    units : str # what will be shown on the GUI. e.g. PSI, A, Fahrenheit, etc.
    realUnitsLowAmount : float # lower bound of the signal's magnitude
    realUnitsHighAmount : float # upper bound of the signal's magnitude

channels = []
channels += Channel_Entry(name = "DPT", boardSlotPosition = 11,
                          sig_type="ao", units="PSI", 
                          realUnitsLowAmount=60.0, realUnitsHighAmount=80.0)
# etc...
