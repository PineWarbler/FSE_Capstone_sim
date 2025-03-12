# -*- coding: utf-8 -*-
"""
Created on Sun Nov 10 19:35:40 2024

@author: REYNOLDSPG21
"""
import socket
import threading
from threading import Thread, Lock
from typing import Union
import time
import heapq
from datetime import datetime

from PacketBuilder import dataEntry, errorEntry, DataPacketModel
# from CommandQueue import CommandQueue

import sys
sys.path.append(r'C:\Users\REYNOLDSPG21\OneDrive - Grove City College\Documents\BAA Fall Semester Courses\Capstone\FSE_Capstone_sim\RPI_side')

# commandQueue = CommandQueue() # initialize to empty
# outQueue = CommandQueue() # data to be sent to master
# errorList = [] # most recent at end

host = 'localhost'
port = 5000

s = socket.socket()
s.connect((host, port))

print("Connected to the server")

print("_____________________")
print("-- now trying a duplex transaction --")
print("_____________________")
de = dataEntry("ai", "channeld2", 0.001, time=time.time())
dpm_out = DataPacketModel([de], "d", None, time.time())
    
s.send(dpm_out.get_packet_as_string().encode())

dpm_catch = DataPacketModel.from_socket(s)
print(f"received dpm obj response from server: {str(dpm_catch)}")
s.close()

print("_____________________")
print("-- now trying a read-only request --")
print("_____________________")

s = socket.socket()
s.connect((host, port))
dpm_out2 = DataPacketModel([], "w", None, time.time())
s.send(dpm_out2.get_packet_as_string().encode()) # send the read request
dpm_catch = DataPacketModel.from_socket(s) # receive response
print(f"response to empty dpm: {str(dpm_catch)}")


s.close()