import json

class Channel_Entry:
    ''' 
    This class defines each signal that the master computer
    could send or receive to/from the simulator.  
    '''

    # don't touch this dictionary unless you know what you're doing!
    # the ribbon cables that connect the RPi to the carrier board
    # will not need to change during normal usage
    _slot2gpio = {
    11: "GPIO5",
    12: "GPIO6",
    13: "GPIO12",
    14: "GPIO13",
    15: "GPIO19",
    16: "GPIO16"
    
    }

    def __init__(self, name : str, boardSlotPosition : int, sig_type : str, units : str | None,
                 realUnitsLowAmount : str | None, realUnitsHighAmount : str | None, showOnGUI:bool=True, 
                 offset_calib_constant:float|None=None, slope_calib_constant:float|None=None):
        '''  
        Args:
            name (str): like "AOP 1", "IVT 3", etc. What the operator will call to send a command
            boardSlotPosition (int): location on carrier board at which this module is installed. Used as an intermediate key
                to map to the GPIO pin, because it's easier for the user to understand the board slot position than the GPIO pin number
                The module's position on the carrier board, as a unique key.
                It is easy to use a two-digit key. First digit is carrier board number; second
                digit is the module position on that board.  e.g. 13 -> carrier board 1, module slot 3 
                (or can be any unique, hashable object)

            sig_type (str): one of ["ao", "ai", "do", "di"]
            units (str|None): Engineering units for the channel (e.g. PSI, Amps, Fahrenheit, etc.)
            realUnitsLowAmount (float|None): realUnitsLowAmount: lower bound of the signal's magnitude in engineering units (Amps, PSI, etc.)
            realUnitsHighAmount (float|None) : upper bound
        '''
        self.name = name
        self.boardSlotPosition = boardSlotPosition
        self.sig_type = sig_type
        self.units = units
        self.realUnitsLowAmount = realUnitsLowAmount
        self.realUnitsHighAmount = realUnitsHighAmount
        self.showOnGUI = showOnGUI

        self.gpio = self._slot2gpio.get(boardSlotPosition)
    
        # constants for linear calibration model are only available for input signals, especially analog ones
        # calibration function transforms raw reading (from RPi) into corrected reading to be displayed on GUI
        self.useCalibration = False
        if offset_calib_constant is not None and slope_calib_constant is not None:
            self.offset_calib_constant = float(offset_calib_constant)
            self.slope_calib_constant = float(slope_calib_constant)
            self.useCalibration = True
        
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
        ''' Only external call should be by the GUI to process ai responses from RPi. 
        (otherwise, this method is should be private)
        This method also applies the linear calibration model specified by `slope_calib_constant` and
        `offset_calib_constant`
        '''
        if self.sig_type[0].lower() != "a":
            return None
        
        if self.useCalibration:
            mA_val = self.slope_calib_constant*mA_val + self.offset_calib_constant # y=mx+b

        return ((mA_val-4.0) / (20.0 - 4.0)) * (self.realUnitsHighAmount - self.realUnitsLowAmount) + self.realUnitsLowAmount
    
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

    def add_ChannelEntry(self, chEntry: Channel_Entry):
        self.channels[chEntry.name] = chEntry

    def getGPIOstr_from_signal_name(self, sigName: str) -> str | None:
        # sigName is like "AOP 1", "IVT 3", etc.
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
            self.add_ChannelEntry(Channel_Entry(name=s.get("name"), 
                                                boardSlotPosition=s.get("boardSlotPosition"), 
                                                sig_type=s.get("sig_type"), 
                                                units=s.get("engineeringUnits"),
                                                realUnitsLowAmount=s.get("engineeringUnitsLowAmount"), 
                                                realUnitsHighAmount=s.get("engineeringUnitsHighAmount"),
                                                showOnGUI=s.get("showOnGUI", False),
                                                offset_calib_constant=s.get("offset_calib_constant"),
                                                slope_calib_constant=s.get("slope_calib_constant")))
