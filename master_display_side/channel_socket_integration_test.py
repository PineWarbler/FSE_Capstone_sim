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
from channel_definitions import Channel_Entry, Channel_Entries

my_channel_list = Channel_Entries() # initialize to empty
my_channel_list.add_ChannelEntry(Channel_Entry(name="SPT", boardSlotPosition=12, sig_type="ao", units="PSI", 
                                               realUnitsLowAmount=97.0, realUnitsHighAmount=200.0))
my_channel_list[-1].gpio = "GPIO19" # override for now

my_channel_list.add_ChannelEntry(Channel_Entry(name="UVT", boardSlotPosition=13, sig_type="ai", units="percent", 
                                               realUnitsLowAmount=100, realUnitsHighAmount=0)) # note that the analog inputs are measured in percentage of open/close
# and that UVT is reversed, meaning that 4mA corresponds to 100%
my_channel_list[-1].gpio = "GPIO13" # override for now

my_channel_list.add_ChannelEntry(Channel_Entry(name = "Motor Status", boardSlotPosition = "r1", sig_type="do", units=None, realUnitsLowAmount=None, realUnitsHighAmount=None))
my_channel_list[-1].gpio = "GPIO6" # override for now

print(f"Finished loading channel list. Here they are:")
for value in my_channel_list.channels.values():
    print(f"   > {value}")



host = "192.168.80.1" # the RPI's addr
port = 5000

print("Testing the socket...", end="")
s = socket.socket()
s.connect((host, port))
s.close()
print("success!")

print("Now commencing user input loop")

while True:
    sigName = input("Signal name (-h for list): ")
    if sigName.lower().strip() == "-h":
        print(", ".join(my_channel_list.channels.keys()))
    ch2send = my_channel_list.getChannelEntry(sigName = sigName)
    if ch2send is None:
        print(">> INVALID signal name chosen. Try again.")
        continue
    if ch2send.sig_type.lower()[1] == "o":
        val = input(f"   Enter a value for {ch2send.name} between {ch2send.realUnitsLowAmount} and {ch2send.realUnitsHighAmount} {ch2send.units} ")
        # now build the outgoing data packet
        try:
            valF = float(val)
        except ValueError:
            print(">> INVALID numerical input. Try again.")
            continue

        de = dataEntry(chType = ch2send.sig_type, gpio_str = ch2send.getGPIOStr(), 
                       val = ch2send.convert_to_packetUnits(valF), 
                       time = time.time())
        print(f"[debug] prepared dataEntry is {de}")

    elif ch2send.sig_type.lower()[1] == "i":
        # then send a dummy datapacket to prompt a reading of the sig name
        de = dataEntry(chType = ch2send.sig_type, gpio_str = ch2send.getGPIOStr(), 
                val = -99, 
                time = time.time())
        print("  since this is an input signal, we will automatically send a packet with null data")

    # actually send the packet
    s = socket.socket()
    print("hang on while we connect over socket...", end="")
    s.connect((host, port))
    print("Connected to the RPi!")

    dpm_out = DataPacketModel(dataEntries = [de], msg_type = "d", error_entries = None, time = time.time())

    start = time.time()
    s.send(dpm_out.get_packet_as_string().encode())

    dpm_catch = DataPacketModel.from_socket(s)
    print(f"[timing] elapsed time for RTT is {time.time() - start} seconds")

    print(f"received dpm obj response from server: {str(dpm_catch)}")
    s.close()
