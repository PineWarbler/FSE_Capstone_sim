# -*- coding: utf-8 -*-
"""
Created on Sat Oct 19 12:49:44 2024

@author: REYNOLDSPG21
"""

from datetime import datetime
from typing import List, Union
import warnings
import socket
import json

class dataEntry:
    '''
    dataEntry represents a single timestamped datum used for both analog and digital signals
    e.g. "sig_type": "ai", "name": "channel1", "val": 3.14, "time": "2024-10-19 19:21:08.198100"
    '''
    allowed_sig_types = ["ao", "ai", "do", "di"]
    
    def __init__(self, sig_type: str, name: str, val: float, time: str=None):
        # sig_type must be one of ["ao", "ai", "do", "di"]
        # name, val, time are parameters are to convert from discrete inputs to dataEntry 
        self.sig_type = sig_type
        self.name = name
        self.val = val
        self.time = time
    
    @classmethod
    def from_dict(cls, in_dict: dict) -> 'dataEntry':
        ''' alternative constructor; converts a dict into a dataEntry obj.
        Use like de = dataEntry.from_dict(my_dict)
        '''
        
        # see https://gist.github.com/stavshamir/0f5bc3e663b7bb33dd2d7822dfcc0a2b#file-book-py
        return cls(in_dict["sig_type"], in_dict["name"], in_dict["val"], in_dict["time"])
    
    def as_dict(self):
        if self.time is None:
            self.time = str(datetime.now())
        return {"sig_type": self.sig_type, "name": self.name, "val": self.val, "time": self.time}
    
    @property
    def sig_type(self):
        return self._sig_type
    
    @sig_type.setter
    def sig_type(self, o_sig_type):
        if not isinstance(o_sig_type, str) or o_sig_type not in self.allowed_sig_types:
            raise TypeError(f"Expected one of {self.allowed_sig_types} as `sig_type`, but received {str(o_sig_type)}")
        self._sig_type = o_sig_type
        
    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, o_name):
        if not isinstance(o_name, str):
            raise TypeError(f"Expected a string as `name`, but received an object of type {type(o_name)}")
        self._name = o_name
    
    @property
    def val(self):
        return self._val
    
    @val.setter
    def val(self, o_val):
        if not isinstance(o_val, (float, int)):
            raise TypeError(f"Expected a float or int, but received an object of type {type(o_val)}")

        self._val = o_val
    
    @property
    def time(self):
        return self._time
    
    @time.setter
    def time(self, o_time):
        if o_time is None:
            self._time=None
            return
        if not isinstance(o_time, (str, datetime)):
            raise TypeError(f"Expected a string or datetime obj as `time`, but received an object of type {type(o_time)}")
        self._time = str(o_time)
    
    
    def __str__(self):
        return str(self.as_dict())
        

class errorEntry:
    ''' a general-purpose object to report errors with electrical interfaces '''
    def __init__(self, source: str, criticalityLevel: str, description: str, time: str = None):
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
        if not isinstance(o_time, (str, datetime)):
            raise TypeError(f"Expected a string or datetime obj as `time`, but received an object of type {type(o_time)}")
        self._time = str(o_time)
    
    def as_dict(self) -> dict:
        ''' use this method when preparing a packet'''
        if self.time is None:
            self.time = str(datetime.now())
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
    
    Once member attributes `dataEntries` are set, call `get_packet_as_string`, which will pack into a
    string ready to be sent over a socket
    
    OR, can use DataPacketModel.from_socket(sock) to create an instance from data waiting on sock buffer
    '''

    def __init__(self, 
                 dataEntries: List[type(dataEntry)], 
                 msg_type : str,
                 error_entries: List[type(errorEntry)]=None,
                 time: str = None):
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
            
        print("msg_length is " + str(msg_length))
        
        data_str = remainder
        while len(data_str) < msg_length:
            data_str += active_socket.recv(msg_length-len(data_str)).decode()
        print("data string is " + str(data_str))
            
        json_payload = json.loads(data_str)
        
        time = json_payload.get("time")
        data = json_payload["data"] # is a list of data entry dictionaries
        errors = json_payload.get("errors") # might be None
        
        # call parsing functions to load entry objects from dictionaries
        dataEntries = [dataEntry.from_dict(d) for d in data]
        
        if errors is not None:
            error_entries = [errorEntry.from_dict(e) for e in errors]
            # otherwise, leave as None

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
        if o_msg_type is None:
            self._msg_type = None
            return
        castAttempt = str(o_msg_type)
           
        if len(castAttempt) != 1:
            raise ValueError(f"Expected length of `msg_type` to be 1, but got length {len(castAttempt)} ")
        self._msg_type = o_msg_type
    
    
    def _pack_json(self, time: str) -> dict:
        json = {
            "time": str(time),
            "data": [ev.as_dict() for ev in self.data_entries]
        }
        # also append error entries if there are any
        if self.error_entries is not None and len(self.error_entries)>0:
            json["errors"] = [ee.as_dict() for ee in self.error_entries]
            
        return json

    def get_packet_as_string(self) -> str:
        if self.data_entries is None or len(self.data_entries)==0:
            raise ValueError("There are no data entries.  Did you forget to initialize them?")
            
        if self.time is None:
            self.time = datetime.now()
            
        json_section_str = str(self._pack_json(self.time))
            
        packet_string = f"{self.msg_type}:{len(json_section_str)}:{json_section_str}"
        packet_string = packet_string.replace("'", "\"") # because json.loads requires double quotes
        return packet_string
    
        
    def __str__(self):
        return f"packet: {self.get_packet_as_string()}\n msg_type: {self.msg_type}\n time: {str(self.time)}"
        
        
        
if __name__ == "__main__":
    dv = [dataEntry("channeld1", 100), dataEntry("channeld2", 0.001)]
    av = [dataEntry("channela1", 109), dataEntry("channela2", 0.021)]
    ee = [errorEntry("card1", "medium", "something went wrong...")]
    
    sd = DataPacketModel(av, dv, "d", ee)
    print(sd.get_packet_as_string())