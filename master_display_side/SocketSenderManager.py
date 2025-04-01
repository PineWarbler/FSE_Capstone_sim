import os
import sys
import logging
import socket
import threading
import time
import queue
from datetime import datetime # for creation of logging filename

# libraries required to perform network ping
import platform    # For getting the operating system name
import subprocess  # For executing a shell command

current_dir = os.path.dirname(os.path.abspath(__file__)) # Get the current file's directory
parent_dir = os.path.dirname(current_dir) # Get the parent directory
sys.path.append(parent_dir) # Add the parent directory to sys.path

from CommandQueue import CommandQueue
from channel_definitions import Channel_Entry # the configuration that defines which signals are connected to the Carrier board
from PacketBuilder import dataEntry, errorEntry, DataPacketModel



class SocketSenderManager:
    logger = logging.getLogger(__name__)
    logging.basicConfig(filename=f'logs/instance_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log', 
                        encoding='utf-8', level=logging.DEBUG)

    def __init__(self, host:str, port:int, q: queue.Queue, socketTimeout:float=5, 
                 testSocketOnInit:bool=True, loopDelay:float=0.1,
                 log=True):
        '''
        An intermediary class that accepts signal commands from a GUI (use `place_single_dataEntry` or `place_ramp`)
        It will handle sending the commands as packets using its own instance of the CommandQueue class. Any responses
        from the Raspberry Pi will be placed on the queue whose reference is passed to the constructor.
        If using a GUI, you can periodically poll the queue to see if this class has received any new responses.

        if testSocketOnInit is True, this constructor will try to ping the host.
        If the host responds, a network confirmation status message will be placed on `q`. Otherwise, will place an errorEntry.

        ARGS:
        host and port correspond to the RPi (192.168.80.1:5000). Any response data that this class receives from the RPi will be 
        placed on `q` and can be read by another process
        loopDelay != 0 (seconds): defines the polling frequency for the background thread to check if any packets are waiting to
                                be sent over the socket.  Setting this delay to zero might cause the GUI to lag or become unresponsive.
                            Note that the an unresponsive socket will slow down the polling frequency because socketTimeout is elapsed 
                            at each attempt to make a socket connection. Recommended to decrease this value instead of loopDelay if you
                            want a more responsive loop effect.
        '''
        self.host = host
        self.port = port
        self.socketTimeout = socketTimeout
        self.loopDelay = loopDelay

        self.qForGUI = q # a queue of errorEntries or dataEntries; 
        # stores data that should be available to the GUI (from RPI or error messages thrown by this class or echoes of sent ramp values)

        self.log = log

        if testSocketOnInit:
            start = time.time()
            respStatus = self.pingHost()
            end = time.time()
            if not respStatus:
                self.qForGUI.put(errorEntry(source="Ethernet Socket", criticalityLevel="high", description=f"Could not receive ping response from {self.host}", time=time.time()))
            else:
                self.qForGUI.put(dataEntry(chType="ao", gpio_str="status:SocketSenderManager is online", val=1, time=time.time()))
                # send a status message to gui. We'll repurpose the errorEntry class with criticality None
                self.qForGUI.put(errorEntry(source="Ethernet Connection", criticalityLevel=None, description=f"Host {self.host} responded to a ping.", time=time.time()))
                self.logger.info(f"testSocketOnInit received ping response. Ping delay was {int((end - start)*1000)} ms.")     

        self.endcqLoop = False # semaphore to tell _loopCommandQueue thread to stop
        self.theCommandQueue = CommandQueue() # a special class to manage timestamp-organized data entries sent to the Raspberry Pi
        self.mutex = threading.Lock() # to ensure one-at-a time access to shared CommandQueue instance
        self.cqLoopThreadReference = threading.Thread(target=self._loopCommandQueue, daemon=True)
        # print(self.cqLoopThreadReference) # print the handle for debugging
        self.cqLoopThreadReference.start()
    
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
        
    def place_ramp(self, ch2send: Channel_Entry, start_mA:float, stop_mA:float, stepPerSecond_mA:float) -> bool:
        '''Note: all values must be in mA. Returns True if successful. False if bounding error.'''

        if stepPerSecond_mA == 0:
            if self.log: self.logger.warning("place_ramp: zero requested as a step value")
            return False
        # stop should have same sign as (stop-start). Assume that the user just messed up the sign of stepPerSecond_mA. Change it for them.
        if stepPerSecond_mA/abs(stepPerSecond_mA) != (stop_mA-start_mA)/abs(stop_mA-start_mA):
            stepPerSecond_mA = -stepPerSecond_mA
            if self.log: self.logger.info(f"place_ramp will assert negative step because step is {stepPerSecond_mA} but stop={stop_mA} and start={start_mA}.")

        if not ch2send.isValidmA(start_mA) or not ch2send.isValidmA(stop_mA):
            print("[ERROR] invalid start or end values")
            if self.log: self.logger.warning(f"place_ramp: Refused to place invalid ramp command with start={start_mA} and stop={stop_mA}. Request exceeded the lower or upper limit for {ch2send.name}, which are {ch2send.realUnitsLowAmount} and {ch2send.realUnitsHighAmount}, respectively.")
            return False
        
        value_entries = self._arange(start=start_mA, stop=stop_mA, step=stepPerSecond_mA)
        value_entries.append(stop_mA) # include the end point (arange omits)
        timestamp_offsets = self._arange(start=0, stop=len(value_entries), step=1)
        # print(f"value entries are {value_entries}")
        # print(f"timestamp_offsets are {timestamp_offsets}")

        refTime = time.time()
        reportErrorString = ""
        for i in range(0, len(value_entries)):
            success, errorString = self.place_single_mA(ch2send = ch2send, mA_val = value_entries[i], time = float(refTime + timestamp_offsets[i]))
            if not success and reportErrorString == "": # only retain a single error message from the entire place_ramp command
                reportErrorString = errorString

        if reportErrorString == "":
            return (True, "")
        else:
            return (False, reportErrorString)

    def place_single_EngineeringUnits(self, ch2send : Channel_Entry, val_in_eng_units : float, time : float) -> tuple[bool, str]:
        ''' use this method to put commands that are not raw mA values. Conversion from engineering units to mA values 
        will happen within this method's call to Channel_Entry.convert_to_packetUnits()
        returns true iff the place request was successful. False if value out of bounds.
        '''

        if ch2send.sig_type.lower() == "ao" and not ch2send.isValidEngineeringUnits(val_in_eng_units):
            return (False, f"Value requested ({val_in_eng_units} {ch2send.units}) for {ch2send.name} must be between {ch2send.realUnitsLowAmount} and {ch2send.realUnitsHighAmount} {ch2send.units}.")
        if ch2send.getGPIOStr() is None:
            return (False, f"GPIO for {ch2send.name} is undefined because `boardSlotPosition` is invalid in `config.json` or `channel_definitions.py` has been edited.")
    
        de = dataEntry(chType=ch2send.sig_type, gpio_str=ch2send.getGPIOStr(), val=ch2send.convert_to_packetUnits(val_in_eng_units), time=time)
        with self.mutex:
            self.theCommandQueue.put(de)
        if self.log: self.logger.info(f"place_single_EngineeringUnits: {de}")
        return (True, "")
    
    def place_single_mA(self, ch2send : Channel_Entry, mA_val : float, time : float) -> tuple[bool, str]:
        # first element of returned tuple is success status: True if no errors. Second element in
        # tuple is error string (None if no error)
        # Engineering units to mA conversion happens on the master side. RPi receives only mA values.
        if not ch2send.isValidmA(mA_val):
            return (False, f"mA value requested ({mA_val} mA) for {ch2send.name} must be between 4.0 and 20.0 mA.")
        if ch2send.getGPIOStr() is None:
            return (False, f"GPIO for {ch2send.name} is undefined. Check channel_definitions.py")
        
        de = dataEntry(chType=ch2send.sig_type, gpio_str=ch2send.getGPIOStr(), val=mA_val, time=time)
        with self.mutex:
            self.theCommandQueue.put(de)
        if self.log: self.logger.info(f"place_single_mA: {de}")
        return (True, "")

    def _loopCommandQueue(self) -> None:
        '''A continuous loop that should be run in a background thread. Checks to see if any data entries are (over)due
        to be sent over the socket. If so, initiates a single-use socket connection with `self.host`, sends those entries, awaits a response,
        and places response(s) on `self.qForGUI`. Note that even ACK responses (generated by output commands and identified by "ack" as their `gpio_str`) will be placed on the queue, so the GUI must filter the queue 
        to select meaningful responses to display'''
        
        if self.log: self.logger.info("_loopCommandQueue thread has started successfully")

        while not self.endcqLoop:
            with self.mutex:
                outgoings = self.theCommandQueue.pop_all_due() # returns a list of dataEntry objects or an empty list
                # note that we pop the due entries regardless of whether the socket is viable. But we re-place
                # entries that are not auto-polling requests (see below)

            if self.loopDelay>0: # the GUI freezes at first if this loop is run unchecked
                time.sleep(self.loopDelay)

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
                self.qForGUI.put(errorEntry(source="Ethernet Client Socket", criticalityLevel="high", description=f"Attempted socket connection with {self.host} failed within timeout={self.socketTimeout} s. Error message: {e}", time=time.time()))
                if self.log: self.logger.critical(f"_loopCommandQueue Could not establish a socket connection with host within timeout={self.socketTimeout} seconds. Debug str is {e}")
                # re-place requests that failed to send back on the queue, unless they're auto-poll requests
                for el in outgoings:
                    if isinstance(el, dataEntry) and el.chType.lower()[1]=="o":
                        # then it's probably a user-requested output signal. Re-place the element
                        # back on the queue to be treated when the socket comes online again
                        # this behavior is needed to reactivate the do toggle switch on the UI
                        self.theCommandQueue.put(el)
                continue
            
            # print(f"packet sent is {dpm_out.get_packet_as_string()}")
            self.sock.send(dpm_out.get_packet_as_string().encode())
            try:
                dpm_catch = DataPacketModel.from_socket(self.sock)
            except Exception as e:
                self.qForGUI.put(errorEntry(source="Ethernet Client Socket", criticalityLevel="high", description=f"{e}", time=time.time()))

            self.sock.close()
            
            # sometimes returns None, in which case 0 errors
            if dpm_catch.error_entries is None:
                numErrors = 0
            else:
                numErrors = len(dpm_catch.error_entries)
            
            if dpm_catch.data_entries is None:
                dpm_catch.data_entries = []

            if self.log: self.logger.info(f"_loopCommandQueue: received response from socket in {time.time() - startRTT:.2f} s containing {len(dpm_catch.data_entries)} entries and {numErrors} errors.")
            
            # place the received entries onto the shared queue to be read by the gui
            for de in dpm_catch.data_entries:
                self.qForGUI.put(de) # queues are thread-safe
            for i in range(0, numErrors):
                self.qForGUI.put(dpm_catch.error_entries[i]) 
        if self.log: self.logger.info("_loopCommandQueue has shut down after having received semaphore")

    def _arange(self, start, stop, step):
        ''' functional clone of numpy's arange function. Defined here so that we can remove the numpy dependency'''
        # If only one argument is provided, assume it is the stop value
        if stop is None:
            stop = start
            start = 0
        # Handle case where step is 0 (this would result in an infinite loop)
        if step == 0:
            raise ValueError("step cannot be zero")

        # Initialize the result list
        result = []
        # Generate the numbers using a while loop
        current = start
        while (step > 0 and current < stop) or (step < 0 and current > stop):
            result.append(current)
            current += step

        return result

    def clearGUIQueue(self):
        while not self.qForGUI.empty():
            self.qForGUI.get()
    
    def clearAllEntriesWithGPIOStr(self, gpio_str:str) -> int:
        # returns number of entries removed
        return self.theCommandQueue.pop_all_with_gpio_str(gpio_str=gpio_str)
        
    def clearCommandQueue(self):
        self.theCommandQueue.clear_all()
    
    def close(self) -> None:
        self.endcqLoop = True
        self.cqLoopThreadReference.die = True
        # don't need to call cqLoopThreadReference.join() because we don't want main gui thread to hang while the thread closes
        # and the Threading class will automatically do thread cleanup
        self.theCommandQueue.clear_all() # clear any remaining ramp entries
        try: # recall that self.socket is created for the first time when data has been put on the queue
            self.sock.close()
        except:
            pass
        if self.log: self.logger.info("SocketSenderManager has closed successfully")
