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

# libraries required to perform network pingf
import platform    # For getting the operating system name
import subprocess  # For executing a shell command

from channel_definitions import Channel_Entries # the configuration that defines which signals are connected to the Carrier board
from CommandQueue import CommandQueue
from channel_definitions import Channel_Entry, Channel_Entries

class SocketSenderManager:
    logger = logging.getLogger(__name__)
    logging.basicConfig(filename='runtime.log', encoding='utf-8', level=logging.DEBUG)

    def __init__(self, host:str, port:int, q: queue.Queue, socketTimeout:float=5, testSocketOnInit:bool=True, startupLoopDelay:float=0.1): #, verbose=False
        '''
        An intermediary class that accepts signal commands from a GUI (use `place_single_dataEntry` or `place_ramp`)
        It will handle sending the commands as packets using its own instance of the CommandQueue class. Any responses
        from the Raspberry Pi will be placed on the queue whose reference is passed to the constructor.
        If using a GUI, you can periodically poll the queue to see if this class has received any new responses.
        Also, this class will echo AO ramp steps back to the `q`--based on the currently-asserted entry, so that the GUI can show the
        current output value in mA.

        if testSocketOnInit is True, this constructor will try to ping the host.
        If the host responds, a network confirmation status message will be placed on `q`. Otherwise, will place an errorEntry.

        ARGS:
        host and port correspond to the RPi (192.168.80.1:5000). Any response data that this class receives from the RPi will be 
        placed on `q` and can be read by another process'''
        self.host = host
        self.port = port
        self.socketTimeout = socketTimeout
        self.startupLoopDelay = startupLoopDelay

        self.qForGUI = q # a queue of errorEntries or dataEntries; 
        # stores data that should be available to the GUI (from RPI or error messages thrown by this class or echoes of sent ramp values)

        if testSocketOnInit:
            start = time.time()
            respStatus = self.pingHost()
            end = time.time()
            if not respStatus:
                self.qForGUI.put(errorEntry(source="Ethernet Socket", criticalityLevel="high", description=f"Could not receive ping response from {self.host}", time=time.time()))
            else:
                self.qForGUI.put(dataEntry(chType="ao", gpio_str="SocketSenderManager is online", val=1, time=time.time()))
                self.logger.info(f"testSocketOnInit received ping response. Ping delay was {int((end - start)*1000)} ms.")     

        self.endcqLoop = False # semaphore to tell _loopCommandQueue thread to stop
        self.theCommandQueue = CommandQueue() # a special class to manage timestamp-organized data entries sent to the Raspberry Pi
        self.mutex = Lock() # to ensure one-at-a time access to shared CommandQueue instance
        self.cqLoopThreadReference = threading.Thread(target=self._loopCommandQueue, daemon=True)
        print(self.cqLoopThreadReference) # print the handle for debugging
        self.cqLoopThreadReference.start()
    
    # def setThread(self, th):
    #     self.cqLoopThreadReference = th
    #     self.cqLoopThreadReference.start()
    def pingHost(self):
        """
        Returns True if host (str) responds to a ping request.
        Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
        https://stackoverflow.com/a/32684938
        """

        # Option for the number of packets as a function of
        param = '-n' if platform.system().lower()=='windows' else '-c'
        # Building the command. Ex: "ping -c 1 google.com"
        command = ['ping', param, '1', self.host]
        return subprocess.call(command) == 0
        
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
            self.logger.warning(f"place_ramp: Either start={start} or stop={stop} exceeded the lower or upper limit for {ch2send.name}, which are {ch2send.realUnitsLowAmount} and {ch2send.realUnitsHighAmount}, respectively.")
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

    def place_single_EngineeringUnits(self, ch2send : Channel_Entry, val_in_eng_units : float, time : float) -> None:
        ''' use this method to put commands that are not raw mA values. Conversion from engineering units to mA values 
        will happen within this method's call to Channel_Entry.convert_to_packetUnits()'''
        if ch2send.getGPIOStr() is None:
            raise ValueError(f"[technician] you don't have a gpio pin mapped to board slot {ch2send.boardSlotPosition}, even though the user requested {ch2send.name}")
        de = dataEntry(chType=ch2send.sig_type, gpio_str=ch2send.getGPIOStr(), val=ch2send.convert_to_packetUnits(val_in_eng_units), time=time)
        with self.mutex:
            self.theCommandQueue.put(de)
        self.logger.info(f"place_single_EngineeringUnits: {de}")
    
    def place_single_mA(self, ch2send : Channel_Entry, mA_val : float, time : float) -> None:
        # !!!!!!!!!! Use only for analog outputs!!!!!!
        # Engineering units to mA conversion happens on the master side. RPi receives only mA values.
        de = dataEntry(chType=ch2send.sig_type, gpio_str=ch2send.getGPIOStr(), val=mA_val, time=time)
        with self.mutex:
            self.theCommandQueue.put(de)
        self.logger.info(f"place_single_mA: {de}")

    def _loopCommandQueue(self) -> None:
        '''A continuous loop that should be run in a background thread. Checks to see if any data entries are (over)due
        to be sent over the socket. If so, initiates a single-use socket connection with `self.host`, sends those entries, awaits a response,
        and places response(s) on `self.qForGUI`. Note that even ACK responses (generated by output commands and identified by "ack" as their `gpio_str`) will be placed on the queue, so the GUI must filter the queue 
        to select meaningful responses to display'''
        
        self.logger.info("_loopCommandQueue thread has started successfully")

        while not self.endcqLoop:
            with self.mutex:
                outgoings = self.theCommandQueue.pop_all_due() # returns a list of dataEntry objects or an empty list

            if self.startupLoopDelay>0: # the GUI freezes at first if this loop is run unchecked
                time.sleep(self.startupLoopDelay)

            if len(outgoings) == 0:
                continue
        
            # echo back outgoing commands to the queue. In practice, only ramped AO signals are of interest--to show the operator that
            # the requested ramp command is successfully running
            # for el in outgoings:
                # self.qForGUI.put(el)

            dpm_out = DataPacketModel(dataEntries = outgoings, msg_type = "d", error_entries = None, time = time.time())

            startRTT = time.time()

            # create a single-use socket
            self.sock = socket.socket()
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # tell TCP to send out data as soon as it arrives in its buffer
            self.sock.settimeout(self.socketTimeout)
            
            try:
                self.sock.connect((self.host, self.port))
            except Exception as e:
                self.qForGUI.put(errorEntry(source="Ethernet Client Socket", criticalityLevel="high", description=f"Could not establish a socket connection with {self.host} within timeout={self.socketTimeout} seconds. \n{e}", time=time.time()))
                self.logger.critical(f"_loopCommandQueue Could not establish a socket connection with host within timeout={self.socketTimeout} seconds. Debug str is {e}")
                continue

            self.sock.send(dpm_out.get_packet_as_string().encode())
            dpm_catch = DataPacketModel.from_socket(self.sock)

            self.sock.close()
            
            numErrors = dpm_catch.error_entries or 0 # sometimes returns None, in which case 0 errors
            self.logger.info(f"_loopCommandQueue: received response from socket in {time.time() - startRTT:.2f} s containing {len(dpm_catch.data_entries)} entries and {numErrors} errors.")
            
            # place the received entries onto the shared queue to be read by the gui
            for de in dpm_catch.data_entries:
                self.qForGUI.put(de) # queues are thread-safe
            for i in range(0, numErrors):
                self.qForGUI.put(dpm_catch.error_entries[i]) 
        self.logger.info("_loopCommandQueue has shut down after having received semaphore")
    
    def clearGUIQueue(self):
        while not self.qForGUI.empty():
            self.qForGUI.get()
    
    def close(self) -> None:
        self.endcqLoop = True
        self.cqLoopThreadReference.die = True
        self.cqLoopThreadReference.join()
        self.sock.close()
        self.logger.info("SocketSenderManager has closed successfully")