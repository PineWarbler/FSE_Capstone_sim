import os
os.chdir('../') #equivalent to %cd ../ # go to parent folder
from PacketBuilder import dataEntry, errorEntry, DataPacketModel
os.chdir('./master_display_side') #equivalent to %cd tests # return to base dir

import socket
import threading
from threading import Thread, Lock
from typing import Union
import time
import heapq
from datetime import datetime

from channel_definitions import Channel_Entries # the configuration that defines which signals are connected to the Carrier board
from CommandQueue import CommandQueue

# import sys
# sys.path.append(r'C:\Users\REYNOLDSPG21\OneDrive - Grove City College\Documents\BAA Fall Semester Courses\Capstone\FSE_Capstone_sim\RPI_side')

# commandQueue = CommandQueue() # initialize to empty
# outQueue = CommandQueue() # data to be sent to master
# errorList = [] # most recent at end

host = "192.168.80.1" # the RPI's addr
port = 5000

s = socket.socket()
print("hang on while we connect over socket...", end="")
s.connect((host, port))

print("Connected to the RPi!")

print("_____________________")
print("-- now trying a duplex transaction --")
print("_____________________")
ce = Channel_Entries()
ch2send = ce.getChannelEntry(sigName = "SPT")

de = dataEntry(chType = ch2send.sig_type, gpio_str = ch2send.getGPIOStr(), val = 12.0, time = time.time())
print(f"de to send is: {str(de)}")

dpm_out = DataPacketModel(dataEntries = [de], msg_type = "d", error_entries = None, time = time.time())

start = time.time()
s.send(dpm_out.get_packet_as_string().encode())

dpm_catch = DataPacketModel.from_socket(s)
print(f"[timing] elapsed time for RTT is {time.time() - start} seconds")

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

