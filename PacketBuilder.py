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
    e.g. "name": "channel1", "val": 3.14, "time": "2024-10-19 19:21:08.198100"
    '''
    def __init__(self, name: str, val: float, time: str=None):
        # name, val, time are parameters are to convert from discrete inputs to dataEntry 
        self.name = name
        self.val = val
        self.time = time
    
    @classmethod
    def from_dict(cls, in_dict: dict) -> 'dataEntry':
        ''' alternative constructor; converts a dict into a dataEntry obj.
        Use like de = dataEntry.from_dict(my_dict)
        '''
        
        # see https://gist.github.com/stavshamir/0f5bc3e663b7bb33dd2d7822dfcc0a2b#file-book-py
        return cls(in_dict["name"], in_dict["val"], in_dict["time"])
    
    def as_dict(self):
        if self.time is None:
            self.time = str(datetime.now())
        return {"name": self.name, "val": self.val, "time": self.time}
        
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
        analog values
        digital values
        error entries
    
    msg_type is a single character that denotes the type of packet being sent/received

    example usage:
    1. Set member attributes `analog_values`, `digital_values`, and (optionally) `error_entries`
    2. call `get_packet_as_string`
    '''

    def __init__(self, 
                 analog_values: List[type(dataEntry)], 
                 digital_values: List[type(dataEntry)], 
                 msg_type : str,
                 error_entries: List[type(errorEntry)]=None,
                 time: str = None):
        '''note: if `time` is unspecified, the packet timestamp will be inserted as the current time when the `get_packet_as_string` method is called'''
        
        # these are bi-directional.  If master sends a packet, all values will be outputted by the Pi
        # vice-versa: if Pi sends to master, they report input data
        self.analog_values = analog_values
        self.digital_values = digital_values
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
            
        data = json.loads(data_str)
        
        time = data.get("time")
        data_list = data["data"]
        analog_entries = data_list[0]
        digital_entries = data_list[1]
        analog_values = [dataEntry.from_dict(a) for a in analog_entries.get("analog_values")]
        digital_values = [dataEntry.from_dict(d) for d in digital_entries.get("digital_values")]
        error_entries = [errorEntry.from_dict(e) for e in data.get("errors")]

        return cls(analog_values, digital_values, msg_type, error_entries, time=time)
        

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
    def analog_values(self):
        return self._analog_values

    @analog_values.setter
    def analog_values(self, value_list: List[dataEntry]):
        # check for valid list element types
        self._check_valid_dataEntry_type(value_list)
        self._analog_values = value_list

    @property  # getter
    def digital_values(self):
        return self._digital_values

    @digital_values.setter
    def digital_values(self, value_list: List[dataEntry]):
        self._check_valid_dataEntry_type(value_list)
        self._digital_values = value_list
    
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
            "data": [
                {
                    "analog_values": [av.as_dict() for av in self.analog_values]  # a list of dictionaries
                },
                {
                    "digital_values": [dv.as_dict() for dv in self.digital_values]
                },
            ]
        }
        if self.error_entries is not None and len(self.error_entries)>0:
            json["errors"] = [ee.as_dict() for ee in self.error_entries]
            
        return json

    def get_packet_as_string(self) -> str:
        if self.analog_values is None and self.digital_values is None:
            warnings.warn("Both analog_values and digital_values are None.  Did you forget to initialize them?")
            
        if self.time is None:
            self.time = datetime.now()
            
        json_section_str = str(self._pack_json(self.time))
            
        packet_string = f"{self.msg_type}:{len(json_section_str)}:{json_section_str}"
        packet_string = packet_string.replace("'", "\"") # because json.loads requires double quotes
        return packet_string
    
        
    def __str__(self):
        return f"packet: {self.get_packet_as_string()}\n msg_type: {self.msg_type}\n time: {self.time}"
        
        
        
if __name__ == "__main__":
    dv = [dataEntry("channeld1", 100), dataEntry("channeld2", 0.001)]
    av = [dataEntry("channela1", 109), dataEntry("channela2", 0.021)]
    ee = [errorEntry("card1", "medium", "something went wrong...")]
    
    sd = DataPacketModel(av, dv, "d", ee)
    print(sd.get_packet_as_string())