import json

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
    11: "GPIO5",
    12: "GPIO6",
    13: "GPIO12",
    14: "GPIO13",
    15: "GPIO19",
    16: "GPIO16"
    
    }

    def __init__(self, name : str, boardSlotPosition : int, sig_type : str, units : str | None,
                 realUnitsLowAmount : str | None, realUnitsHighAmount : str | None, showOnGUI:bool=True):
        self.name = name
        self.boardSlotPosition = boardSlotPosition
        self.sig_type = sig_type
        self.units = units
        self.realUnitsLowAmount = realUnitsLowAmount
        self.realUnitsHighAmount = realUnitsHighAmount
        self.showOnGUI = showOnGUI

        self.gpio = self._slot2gpio.get(boardSlotPosition)
    
    def convert_to_packetUnits(self, val):
        # analog (mA) values are converted from engineering units to a mA value
        # digital values are left as 0 or 1
        if self.sig_type[0].lower() == "a":
            return self.EngineeringUnits_to_mA(val)
        elif self.sig_type[0].lower() == "d":
            return int(val)
        else:
            return "invalid sig type"
    
    def mA_to_EngineeringUnits(self, mA_val):
        ''' Only external call should be by the GUI. (otherwise, this method is should be private)'''
        if self.sig_type[0].lower() == "a":
            return ((mA_val-4.0) / (20.0 - 4.0)) * (self.realUnitsHighAmount - self.realUnitsLowAmount) + self.realUnitsLowAmount
        else:
            return None
    
    def EngineeringUnits_to_mA(self, engUnits):
        ''' Only external call should be by the GUI. (otherwise, this method is should be private)'''
        if self.sig_type[0].lower() == "a":
            return 4.0 + ((engUnits - self.realUnitsLowAmount) / (self.realUnitsHighAmount - self.realUnitsLowAmount)) * (20.0 - 4.0)
        elif self.sig_type[0].lower() == "d":
            return int(engUnits)
        else:
            return None
        
    def isValidmA(self, mA_val) -> bool:
        return 4 <= mA_val <= 20
    
    def isValidEngineeringUnits(self, engUnits) -> bool:
        return self.isValidmA(self.EngineeringUnits_to_mA(engUnits=engUnits))

    def EngineeringUnitsRate_to_mARate(self, engUnitRate:float):
        ''' engUnitRate has units like PSI/second'''
        return (20-4) * engUnitRate / (self.realUnitsHighAmount-self.realUnitsLowAmount)
       
    def EngUnits_str(self, mA_val):
        return f"{self.mA_to_EngineeringUnits(mA_val)} {self.units}"
    
    
    def getGPIOStr(self):
        return self._slot2gpio.get(self.boardSlotPosition)
    
    def __str__(self):
        return f"Channel_Entry object: {self.name} at board slot position {self.boardSlotPosition} with GPIO {self.gpio}"

class Channel_Entries:
    def __init__(self):        
        self.channels = dict() # key is name, value is ChannelEntryObj
        # because the main feature of this class is to map the user-friendly name for the signal (e.g. "AOP") with its board slot position and other info
        # self.channels["Motor Status"] = Channel_Entry(name = "Motor Status", boardSlotPosition = "r1", sig_type="do", units=None, realUnitsLowAmount=None, realUnitsHighAmount=None)
        # self.channels["UVT"] = Channel_Entry(name="UVT", boardSlotPosition=13, sig_type="ai", units="percent", 
        #                         realUnitsLowAmount=100, realUnitsHighAmount=0) # note that the analog inputs are measured in percentage of open/close
        # and that UVT is reversed, meaning that 4mA corresponds to 100%

        # self.channels["SPT"] = Channel_Entry(name="SPT", boardSlotPosition=12, sig_type="ao", units="PSI", 
                                # realUnitsLowAmount=97.0, realUnitsHighAmount=200.0)
        # other analog outputs
        # self.channels["DPT"] = Channel_Entry(name="DPT", boardSlotPosition=None, sig_type="ao", units="PSI", 
        #                         realUnitsLowAmount=100.0, realUnitsHighAmount=200.0)
        # self.channels["MAT"] = Channel_Entry(name="MAT", boardSlotPosition=None, sig_type="ao", units="Amps", 
        #                         realUnitsLowAmount=145, realUnitsHighAmount=300.0)

        # other analog inputs
        # self.channels["IVT"] = Channel_Entry(name="IVT", boardSlotPosition=None, sig_type="ai", units="percent", 
        #                         realUnitsLowAmount=0.0, realUnitsHighAmount=100.0)

        # digital inputs
        # self.channels["AOP"] = Channel_Entry(name="AOP", boardSlotPosition=12, sig_type="di", units="PSI", 
        #                         realUnitsLowAmount=97.0, realUnitsHighAmount=200.0)

    def add_ChannelEntry(self, chEntry: Channel_Entry):
        self.channels[chEntry.name] = chEntry

    def getGPIOstr_from_signal_name(self, sigName: str) -> str | None:
        # sigName is like "AOP", "IVT", etc.
        # will return None if that signal name doesn't exist
        ch = self.channels.get(sigName)
        if ch is None:
            return None
        return ch.getGPIOStr_from_slotPosition(slotPosition = ch.boardSlotPosition)

    def get_channelEntry_from_GPIOstr(self, gpio_str:str):
        # used by the gui to retrieve the name of the signal
        for k,v in self.channels.items():
            if v.gpio == gpio_str:
                return v
        return None
    
    def getChannelEntry(self, sigName:str) -> Channel_Entry:
        return self.channels.get(sigName)
    
    def load_from_config_file(self, config_file_path: str) -> None:
        ''' reads a json config file. Reads the channel contents from the config file and adds channel entries to this instance
        '''
        with open(config_file_path, 'r') as f:
            all_json = json.load(f)
        chs_from_json = all_json.get("signals")
        for s in chs_from_json:
            self.add_ChannelEntry(Channel_Entry(name=s.get("name"), boardSlotPosition=s.get("boardSlotPosition"), sig_type=s.get("sig_type"), units=s.get("engineeringUnits"),
                 realUnitsLowAmount=s.get("engineeringUnitsLowAmount"), realUnitsHighAmount=s.get("engineeringUnitsHighAmount"), showOnGUI=s.get("showOnGUI")))
            
# print(channels[1].mA_to_EngineeringUnits(4.0))
# print(channels[1].mA_to_EngineeringUnits(12.0))
# print(channels[1].mA_to_EngineeringUnits(20.0))

# print(channels[1].EngineeringUnits_to_mA(0))
# print(channels[1].EngineeringUnits_to_mA(50))
# print(channels[1].EngineeringUnits_to_mA(100))

# print(channels[2].EngineeringUnits_to_mA(97))
# print(channels[2].EngineeringUnits_to_mA(199))