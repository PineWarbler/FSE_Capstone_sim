# -*- coding: utf-8 -*-
"""
Created on Sat Oct 19 12:49:44 2024

@author: REYNOLDSPG21
"""

# from datetime import datetime
from typing import List, Union
import warnings
import socket
import json
import time

class dataEntry:
    '''
    dataEntry represents a single timestamped datum used for both analog and digital signals
    e.g. "chType": "ai", gpio_str : "GPIO26", "val": 3.14, "time": 1735346511.9356625
    n.b. pass an integer as "val" if you want to send a binary digital signal (for digital inputs/outputs)
    '''
    allowed_chTypes = ["ao", "ai", "do", "di"]
    
    def __init__(self, chType: str, gpio_str: str, val: Union[float, int], time: float = None):
        # chType must be one of ["ao", "ai", "do", "di"]
        # gpio_str is like "GPIO26" or one of the formats specified by https://gpiozero.readthedocs.io/en/stable/recipes.html#pin-numbering
        # time : a Unix-style timestamp; when initiated by the master, this timestamp determines this command's position in the outgoing socket queue
        self.chType = chType
        self.gpio_str = gpio_str
        self.val = val
        self.time = time
    
    def __lt__(self, other):
        return self.time < other.time  # to enable a heap implementation in another file...
    
    @classmethod
    def from_dict(cls, in_dict: dict) -> 'dataEntry':
        ''' alternative constructor; converts a dict into a dataEntry obj.
        Use like de = dataEntry.from_dict(my_dict)
        '''
        
        # see https://gist.github.com/stavshamir/0f5bc3e663b7bb33dd2d7822dfcc0a2b#file-book-py
        return cls(in_dict["chType"], in_dict["gpio_str"], in_dict["val"], in_dict["time"])
    
    def as_dict(self):
        time_to_send = self.time
        if self.time is None:
            time_to_send = time.time()
        return {"chType": self.chType, "gpio_str": self.gpio_str, "val": self.val, "time": time_to_send}
    
    @property
    def chType(self):
        return self._chType
    
    @chType.setter
    def chType(self, o_chType):
        if not isinstance(o_chType, str) or o_chType not in self.allowed_chTypes:
            raise TypeError(f"Expected one of {self.allowed_chTypes} as `chType`, but received {str(o_chType)}")
        self._chType = o_chType
        
    @property
    def gpio_str(self):
        return self._gpio_str
    
    @gpio_str.setter
    def gpio_str(self, o_gpio_str):
        if not isinstance(o_gpio_str, str):
            raise TypeError(f"Expected a string as `gpio_str`, but received an object of type {type(o_gpio_str)}")
        self._gpio_str = o_gpio_str
    
    @property
    def val(self):
        return self._val
    
    @val.setter
    def val(self, o_val):
        # if not isinstance(o_val, (float, int)):
            # raise TypeError(f"Expected a float or int, but received an object of type {type(o_val)}")

        self._val = o_val
    
    @property
    def time(self):
        return self._time
    
    @time.setter
    def time(self, o_time):
        if o_time is None:
            self._time=None
            return
        if not isinstance(o_time, float):
            raise TypeError(f"Expected a float (UNIX) timestamp as `time`, but received an object of type {type(o_time)}")
        self._time = o_time
    
    
    def __str__(self):
        return str(self.as_dict())
        

class errorEntry:
    ''' a general-purpose object to report errors with electrical interfaces. You can also set criticalityLevel
     to None to signify a neutral status entry
    '''
    def __init__(self, source: str, criticalityLevel: str|None, description: str, time: float = None):
        self.source = source
        self.criticalityLevel = criticalityLevel
        self.description = description
        self.time = time
    
    @classmethod
    def from_dict(cls, in_dict: dict) -> 'errorEntry':
        ''' alternative constructor; converts a dict into an errorEntry obj '''
        
        # see https://gist.github.com/stavshamir/0f5bc3e663b7bb33dd2d7822dfcc0a2b#file-book-py
        return cls(in_dict["source"], in_dict["criticalityLevel"], in_dict["description"], 
                           time=in_dict.get("time"))
    @property
    def time(self):
        return self._time
    
    @time.setter
    def time(self, o_time):
        if o_time is None:
            self._time=None
            return
        if not isinstance(o_time, float):
            raise TypeError(f"Expected a float (UNIX timestamp) as `time`, but received an object of type {type(o_time)}")
        self._time = o_time
    
    def as_dict(self) -> dict:
        ''' use this method when preparing a packet'''
        if self.time is None:
            self.time = time.time()
        return {"source": self.source, "criticalityLevel": self.criticalityLevel, 
                "description": self.description, "time": self.time}
    
    def __str__(self):
        return str(self.as_dict())


class DataPacketModel:
    '''
    Data model for signals. Can be used to generate outgoing signals packet strings or to 
    poll an active socket to parse out data values into an instance of this class
    
    Elements:
        dataEntries: a list of dataEntry objects that can hold analog or digital values
        error entries: a list of erroEntry objects
    
    msg_type is a single character that denotes the type of packet being sent/received
    `d` means that this packet contains data meant for the recipient
    `w` means that this packet is simply a write request (i.e. contains no data)
    
    Once member attributes `dataEntries` are set, call `get_packet_as_string`, which will pack into a
    string ready to be sent over a socket
    
    OR, can use DataPacketModel.from_socket(sock) to create an instance from data waiting on sock buffer
    '''
    
    allowed_msg_types = ['d', 'w']

    def __init__(self, 
                 dataEntries: List[type(dataEntry)], 
                 msg_type : str,
                 error_entries: List[type(errorEntry)]=None,
                 time: float = None):
        '''note: if `time` is unspecified, the packet timestamp will be inserted as the current time when the `get_packet_as_string` method is called'''
        
        # these are bi-directional.  If master sends a packet, all values will be outputted by the Pi
        # vice-versa: if Pi sends to master, they report input data
        self.data_entries = dataEntries
        self.error_entries = error_entries
        self.msg_type = msg_type
        self.time = time
    
    @classmethod
    def from_socket(cls, active_socket: socket) -> 'DataPacketModel':
        ''' creates an instance of DataPacketModel from the data on the socket input buffer '''
        first_slice = active_socket.recv(4).decode() # apparently, minimum buffer size is 4
        print("received first_slice: " + str(first_slice))
        
        if len(first_slice) < 4:
            # then there's actually no data to parse. Return an empty class object
            print(f"[PacketBuilder from_socket] Found data on the socket with first slice = {first_slice}. Will not parse rest of data.")
            import time
            return cls(dataEntries = None, msg_type = "d", error_entries=[], time=time.time())
            
        msg_type = first_slice[0] # first byte should be type of message
        print("msg_type is " + str(msg_type))
        
        # do something with the type? IDK yet
        
        built_msg_length = first_slice[2:] # omit the msg_type and following colon
        remainder = "" # in case we read a slice that has part of the data message in it
        
        # do-while construct in python...
        while True:
            currSlice = active_socket.recv(4).decode()
            built_msg_length += currSlice.split(":")[0] # only keep bytes before the colon
            
            if ":" in currSlice:
                remainder = currSlice.split(":")[1]
                break
        
        try:
            msg_length = int(built_msg_length)
        except ValueError:
            raise ValueError(f"Expected to find packet length as integer, but got `{built_msg_length}` instead")
            
        # print("msg_length is " + str(msg_length))
        
        data_str = remainder
        while len(data_str) < msg_length:
            data_str += active_socket.recv(msg_length-len(data_str)).decode()
        # print("data string is " + str(data_str))
            
        json_payload = json.loads(data_str)
        
        time = json_payload.get("time")
        data = json_payload["data"] # is a list of data entry dictionaries
        errors = json_payload.get("errors") # might be None
        
        # call parsing functions to load entry objects from dictionaries
        dataEntries = [dataEntry.from_dict(d) for d in data]
        
        if errors is None:
            error_entries = None
        else:
            error_entries = [errorEntry.from_dict(e) for e in errors]

        return cls(dataEntries, msg_type, error_entries=error_entries, time=time)
        

    # private method
    def _check_valid_dataEntry_type(self, dataEntryList: List[dataEntry]) -> None:
        '''throws a ValueError if any element in list is a dataEntry object'''
        # format should be like {"channel1" : VALUE, "time": time},
        if dataEntryList is None:
            return
        for de in dataEntryList:
            if not isinstance(de, dataEntry):
                raise ValueError(f"Expected all list elements to be of type `dataEntry`, but encountered object of type {type(de)}")
        return
    
    def _check_valid_errorEntry_type(self, errorEntryList: List[errorEntry]) -> None:
        if errorEntryList is None:
            return
        for ee in errorEntryList:
            if not isinstance(ee, errorEntry):
                raise ValueError(f"Expected all list elements to be of type `errorEntry`, but encountered object of type {type(ee)}")
        return

    @property  # getter
    def data_entries(self):
        return self._data_entries

    @data_entries.setter
    def data_entries(self, entry_list: List[dataEntry]):
        # check for valid list element types
        self._check_valid_dataEntry_type(entry_list)
        self._data_entries = entry_list
    
    @property  # getter
    def error_entries(self):
        return self._error_entries

    @error_entries.setter
    def error_entries(self, value_list: List[errorEntry]):
        # check for valid list element types
        self._check_valid_errorEntry_type(value_list)
        self._error_entries = value_list

    @property # getter
    def active_socket(self):
        return self._active_socket

    @active_socket.setter
    def active_socket(self, o_active_socket : socket.socket):
        if o_active_socket is None:
            self._active_socket = None
            return
        if not isinstance(o_active_socket, socket.socket):
            raise TypeError(f"Expected a socket object, but received an object of type {type(socket)}")
        self._active_socket = o_active_socket
    
    @property # getter
    def msg_type(self):
        return self._msg_type
    
    @msg_type.setter
    def msg_type(self, o_msg_type):
        castAttempt = str(o_msg_type).lower()
           
        if castAttempt not in self.allowed_msg_types:
            raise ValueError(f"Expected `msg_type` to be one of {self.allowed_msg_types}, but got {o_msg_type} instead")
        self._msg_type = o_msg_type
    
    
    def _pack_json(self, time: str) -> dict:
        json = {
            "time": time,
            "data": [ev.as_dict() for ev in self.data_entries]
        }
        # also append error entries if there are any
        if self.error_entries is not None and len(self.error_entries)>0:
            json["errors"] = [ee.as_dict() for ee in self.error_entries]
            
        return json

    def get_packet_as_string(self) -> str:
        if self.msg_type=="d" and (self.data_entries is None or len(self.data_entries)==0):
            # then we expect this packet to contain data, but it doesn't
            # raise ValueError("There are no data entries.  Did you forget to initialize them?")
            # nevermind. We might use this functionality for sending ACKs
            pass
            
        if self.time is None:
            self.time = time.time()
            
        json_section_str = str(self._pack_json(self.time))
            
        packet_string = f"{self.msg_type}:{len(json_section_str)}:{json_section_str}"
        packet_string = packet_string.replace("'", "\"") # because json.loads requires double quotes
        return packet_string
    
        
    def __str__(self):
        return f"packet: {self.get_packet_as_string()}\n msg_type: {self.msg_type}\n time: {str(self.time)}"
        
        
        
if __name__ == "__main__":
    de = [dataEntry(chType = "ao", gpio_str="GPIO26", val=3.14, time=time.time())]

    ee = [errorEntry(source="GPIO26", criticalityLevel="medium", description="something went wrong...", time=time.time())]
    sd = DataPacketModel(dataEntries=de, msg_type="d", error_entries=ee, time=time.time())    

    print(sd.get_packet_as_string())
