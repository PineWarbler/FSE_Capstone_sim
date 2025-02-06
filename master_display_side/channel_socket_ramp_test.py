import os
os.chdir('../') #equivalent to %cd ../ # go to parent folder
from PacketBuilder import dataEntry, errorEntry, DataPacketModel
os.chdir('./master_display_side') #equivalent to %cd tests # return to base dir

import socket
import threading
from threading import Thread, Lock
from typing import Union
import time
import numpy as np # for generating the ramp vectors


from channel_definitions import Channel_Entries # the configuration that defines which signals are connected to the Carrier board
from CommandQueue import CommandQueue
from channel_definitions import Channel_Entry, Channel_Entries

mutex = Lock()

host = "192.168.80.1" # the RPI's addr
port = 5000

endThread = False

dataPacketResponses = [] # to share between the command queue thread and the main thread

def loopCommandQueue(cq: CommandQueue):
    print("[loopCommandQueue] started the function")
    while not endThread:
        # nd = theCommandQueue.get_num_due()
        # print(f"num due: {nd} out of {len(theCommandQueue)} total")
        # time.sleep(0.2)
        # if nd == 0:
            # continue

        with mutex:
            outgoings = cq.pop_all_due() # returns a list of dataEntry objects or an empty list

        # print(f"found numdue={len(outgoings)} out of {len(theCommandQueue)} total elements")
        if len(outgoings) == 0:
            continue
            # print(f"[loopCommandQueue] ERROR: len(outgoings)={len(outgoings)}")
        
        # print(f"[loopCommandQueue] found {len(theCommandQueue)} due elements on the queue")

        startSocketCreation = time.time()
        s = socket.socket() # for speed, could try to move this outside of the loop
        print("[loopCommandQueue] making a socket connection...", end="")
        s.connect((host, port))
        print("done!")
        endSocketCreation = time.time()

        dpm_out = DataPacketModel(dataEntries = outgoings, msg_type = "d", error_entries = None, time = time.time())

        startRTT = time.time()
        s.send(dpm_out.get_packet_as_string().encode())

        dpm_catch = DataPacketModel.from_socket(s)
        dataPacketResponses.append(dpm_catch)
        # print("[loopCommandQueue] dataPacketResponses is {dataPacketResponses}")

        print(f"[timing] socket creation time is {endSocketCreation - startSocketCreation} seconds")
        print(f"[timing] RTT is {time.time() - startRTT} seconds")
        print(f"[timing] total time (socket creation + RTT) is {time.time() - startSocketCreation} seconds")

        print(f"received dpm obj response from server: {str(dpm_catch)}")
        s.close()

all_threads = []

print("Spinning up the CommandQueue thread...", end="")
theCommandQueue = CommandQueue()
gp = threading.Thread(target=loopCommandQueue, args=(theCommandQueue,), daemon=True) # 
gp.start()
all_threads.append(gp)
print("done")

my_channel_list = Channel_Entries() # initialize to empty
my_channel_list.add_ChannelEntry(Channel_Entry(name="SPT", boardSlotPosition=12, sig_type="ao", units="PSI", 
                                               realUnitsLowAmount=97.0, realUnitsHighAmount=200.0))
my_channel_list.channels["SPT"].gpio = "GPIO19" # override for now

my_channel_list.add_ChannelEntry(Channel_Entry(name="UVT", boardSlotPosition=13, sig_type="ai", units="percent", 
                                               realUnitsLowAmount=100, realUnitsHighAmount=0)) # note that the analog inputs are measured in percentage of open/close
# and that UVT is reversed, meaning that 4mA corresponds to 100%
my_channel_list.channels["UVT"].gpio = "GPIO13" # override for now

my_channel_list.add_ChannelEntry(Channel_Entry(name = "Motor Status", boardSlotPosition = "r1", sig_type="do", units="binary", realUnitsLowAmount=0, realUnitsHighAmount=1))
my_channel_list.channels["Motor Status"].gpio = "GPIO6" # override for now

my_channel_list.add_ChannelEntry(Channel_Entry(name="AOP", boardSlotPosition=12, sig_type="di", units="PSI", 
                                               realUnitsLowAmount=97.0, realUnitsHighAmount=200.0))
my_channel_list.channels["AOP"].gpio = "GPIO5" # override for now

print("Finished loading channel list. Here they are:")
for value in my_channel_list.channels.values():
    print(f"   > {value}")


def start_stop_dur_to_entries(start, stop, timestep):
    commandRateLimit = 0.5 # don't send more than 3 commands per second (would overload the link)
    if timestep < commandRateLimit:
        print("[WARNING] the requested timestep might exceed the estimated link rate!")
    return list(np.arange(start=start, stop=stop, step=timestep))

print("Testing the socket...", end="")
s = socket.socket()
s.connect((host, port))
s.close()
print("success!")

print("Now commencing user input loop")

try:
    while True:
        sigName = input("Signal name (-h for list): ")
        if sigName.lower().strip() == "-h":
            print(", ".join(my_channel_list.channels.keys()))
            continue
        
        ch2send = my_channel_list.getChannelEntry(sigName = sigName)
        if ch2send is None:
            print(">> INVALID signal name chosen. Try again.")
            continue
        
        elif ch2send.sig_type.lower()[1] == "o":
            if ch2send.sig_type.lower() == "ao":
                renable = input("Ramped input? [y/n] or [c] to clear: ")
                if renable.lower() == "c":
                    _ = theCommandQueue.pop_all()
                    print("Cleared the command queue of all entries")
                    continue

                elif renable.lower() == "y":
                    print(f"Ok. The following two input must be between {ch2send.realUnitsLowAmount} and {ch2send.realUnitsHighAmount} {ch2send.units}.")
                    startRampVal = float(input("    starting value: "))
                    endRampVal = float(input("    ending value: "))
                    valStep = float(input(f"    every 1s, step _ {ch2send.units}: "))

                    if valStep > 0 and (endRampVal<startRampVal):
                        valStep = -valStep
                        print(f"[TIP] Expected a negative step because end<start. Will assert valStep={valStep}")
                    if startRampVal<ch2send.realUnitsLowAmount or endRampVal>ch2send.realUnitsHighAmount:
                        print("[ERROR] invalid start or end values")
                        continue
                    
                    value_entries = np.arange(start=startRampVal, stop=endRampVal, step=valStep)
                    timestamp_offsets = np.arange(start=0, stop=len(value_entries), step=1)
                    print(f"value entries are {value_entries}")
                    print(f"Timestamp offsets are {timestamp_offsets}")
                    
                    refTime = time.time()
                    for i in range(0, len(value_entries)):
                        val2send = value_entries[i]
                        print(f" {i}: {val2send} at t={refTime + timestamp_offsets[i]}")
                        de = dataEntry(chType = ch2send.sig_type, gpio_str = ch2send.gpio, 
                                    val = ch2send.convert_to_packetUnits(val2send), 
                                    time = refTime + timestamp_offsets[i])
                        with mutex:
                            theCommandQueue.put(entry = de)
                elif renable.lower() == "n":
                    val = input(f"   Enter a value for {ch2send.name} between {ch2send.realUnitsLowAmount} and {ch2send.realUnitsHighAmount} {ch2send.units} ")
                    de = dataEntry(chType = ch2send.sig_type, gpio_str = ch2send.gpio, 
                                   val = ch2send.convert_to_packetUnits(float(val)), 
                                   time = time.time())
                    with mutex:
                        theCommandQueue.put(entry = de)
                    print("awaiting ACK...", end="")
                    while len(dataPacketResponses) == 0:
                        pass
                    print("received ACK")
                    dataPacketResponses.clear()


            elif ch2send.sig_type.lower() == "do":
                val = input(f"   Enter a value for {ch2send.name} between {ch2send.realUnitsLowAmount} and {ch2send.realUnitsHighAmount} {ch2send.units} ")
            # now build the outgoing data packet
                try:
                    valF = float(val)
                except ValueError:
                    print(">> INVALID numerical input. Try again.")
                    continue

                # todo: revert to gpio_str = ch2send.getGPIOstr()
                de = dataEntry(chType = ch2send.sig_type, gpio_str = ch2send.gpio, 
                            val = ch2send.convert_to_packetUnits(valF), 
                            time = time.time())
                print(f"[debug] prepared dataEntry is {de}")
                with mutex:
                    theCommandQueue.put(entry = de)
                print("awaiting ACK...", end="")
                while len(dataPacketResponses) == 0:
                    pass
                print("received ACK")
                dataPacketResponses.clear()

        elif ch2send.sig_type.lower()[1] == "i":
            # then send a dummy datapacket to prompt a reading of the sig name
            # I just realized we can use a "ramped" queue strategy to get automatic readings
            de = dataEntry(chType = ch2send.sig_type, gpio_str = ch2send.gpio, 
                    val = -99, 
                    time = time.time())
            with mutex:
                theCommandQueue.put(entry = de)
            print("  since this is an input signal, we will automatically send a packet with null data")
            print("  waiting for a response...")
            while len(dataPacketResponses) == 0:
                pass
            print(f"done. Found {len(dataPacketResponses)} response with the following dataEntries:")
            for el in dataPacketResponses:
                for i in el.data_entries:
                    print(f" > {i}")
            dataPacketResponses.clear()

except KeyboardInterrupt:
    print(f"\nclosing {len(all_threads)} threads...", end="")
    endThread = True
    for t in all_threads:
        t.die = True
        t.join()
    print("done")

    
