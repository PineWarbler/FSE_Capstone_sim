import os
os.chdir('../') #equivalent to %cd ../ # go to parent folder
from PacketBuilder import dataEntry, errorEntry, DataPacketModel
os.chdir('./master_display_side') #equivalent to %cd tests # return to base dir

import logging
import socket
import threading
from threading import Thread, Lock
from typing import Union
import time
import numpy as np # for generating the ramp vectors
import queue


from channel_definitions import Channel_Entries # the configuration that defines which signals are connected to the Carrier board
from CommandQueue import CommandQueue
from channel_definitions import Channel_Entry, Channel_Entries

class SocketSenderManager:
    logger = logging.getLogger(__name__)
    logging.basicConfig(filename='runtime.log', encoding='utf-8', level=logging.DEBUG)

    def __init__(self, host:str, port:int, q: queue.Queue, testSocketOnInit=True): #, verbose=False
        '''
        An intermediary class that accepts signal commands from a GUI (use `place_single_dataEntry` or `place_ramp`)
        It will handle sending the commands as packets using its own instance of teh CommandQueue class. Any responses
        from the Raspberry Pi will be based on the queue whose reference is passed to the constructor.
        If using a GUI, you can periodically poll the queue to see if this class has received any new responses.
        ARGS:
        host and port correspond to the RPi (192.168.80.1:5000). Any response data that this class receives from the RPi will be 
        placed on `q` and can be read by another process'''
        self.host = host
        self.port = port

        if testSocketOnInit:
            # test the socket validity before proceeding; will not catch any Timeout error
            startSocketCreation = time.time()
            self.sock = socket.socket()
            self.sock.settimeout(5)
            self.sock.connect((self.host, self.port))
            self.logger.info(f"Socket responded in {time.time() - startSocketCreation:.2f} seconds.")
            self.sock.settimeout(None)

        self.fromRPIq = q # to store data received from the Raspberry Pi

        self.endcqLoop = False # semaphore to tell _loopCommandQueue thread to stop
        self.theCommandQueue = CommandQueue() # a special class to manage timestamp-organized data entries sent to the Raspberry Pi
        self.mutex = Lock() # to ensure one-at-a time access to shared CommandQueue instance
        self.cqLoopThreadReference = threading.Thread(target=self._loopCommandQueue, daemon=True)
        self.cqLoopThreadReference.start()
        
    def place_ramp(self, ch2send: Channel_Entry, start:float, stop:float, stepPerSecond:float) -> bool:
        ''' returns True if successful. False if bounding error.'''
        if stepPerSecond == 0:
            self.logger.warning(f"place_ramp: zero requested as a step value")
            return False
        # stop should have same sign as (stop-start). Assume that the user just messed up the sign of stepPerSecond. Change it for them.
        if stepPerSecond/abs(stepPerSecond) != (stop-start)/abs(stop-start):
            stepPerSecond = -stepPerSecond
            self.logger.info(f"place_ramp will assert negative step because step is {stepPerSecond} but stop={stop} and start={start}.")
        if start<ch2send.realUnitsLowAmount or stop>ch2send.realUnitsHighAmount:
            print("[ERROR] invalid start or end values")
            self.logger.warning(f"place_ramp: Either start={start} or stop={stop} exceeded the lower or upper limit for {ch2send.name}, which are 
            {ch2send.realUnitsLowAmount} and {ch2send.realUnitsHighAmount}, respectively.")
            return False
        
        value_entries = np.arange(start=start, stop=stop, step=stepPerSecond)
        timestamp_offsets = np.arange(start=0, stop=len(value_entries), step=1)
        refTime = time.time()
        for i in range(0, len(value_entries)):
            val2send = value_entries[i]
            # print(f" {i}: {val2send} at t={refTime + timestamp_offsets[i]}")
            de = dataEntry(chType = ch2send.sig_type, gpio_str = ch2send.gpio, 
                        val = ch2send.convert_to_packetUnits(val2send), 
                        time = refTime + timestamp_offsets[i])
            with self.mutex:
                self.theCommandQueue.put(entry = de)
        self.logger.info(f"[place_ramp] placed ramp command for {ch2send.name} start={start}, stop={stop}, stepPerSecond={stepPerSecond}")
        return True
    
    def place_single_dataEntry(self, de : dataEntry) -> None:
        with self.mutex:
            self.theCommandQueue.put(de)
        self.logger.info(f"place_single_dataEntry: {de}")

    def _loopCommandQueue(self) -> None:
        self.logger.info("_loopCommandQueue thread has started successfully")

        while not self.endcqLoop:
            with self.mutex:
                outgoings = self.theCommandQueue.pop_all_due() # returns a list of dataEntry objects or an empty list

            if len(outgoings) == 0:
                continue

            dpm_out = DataPacketModel(dataEntries = outgoings, msg_type = "d", error_entries = None, time = time.time())

            startRTT = time.time()
            self.sock.send(dpm_out.get_packet_as_string().encode())

            dpm_catch = DataPacketModel.from_socket(s)
            
            numErrors = dpm_catch.error_entries or 0 # sometimes returns None, in which case 0 errors
            self.logger.info(f"_loopCommandQueue: received response from socket in {time.time() - startRTT:.2f} s 
                             containing {len(dpm_catch.dataEntries)} entries and {numErrors} errors.")
            
            # place the received entries onto the shared queue to be read by the gui
            for de in dpm_catch.dataEntries:
                self.fromRPIq.put(de) # queues are thread-safe
            for i in range(0, numErrors):
                self.fromRPIq.put(dpm_catch.error_entries[i]) 
        self.logger.info("_loopCommandQueue has shut down after having received semaphore")
    
    def close(self) -> None:
        self.endcqLoop = True
        self.cqLoopThreadReference.die = True
        self.cqLoopThreadReference.join()
        self.sock.close()
        self.logger.info("SocketSenderManager has closed successfully")


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

    
