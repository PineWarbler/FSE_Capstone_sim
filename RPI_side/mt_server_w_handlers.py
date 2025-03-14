# -*- coding: utf-8 -*-
"""
Created on Fri Dec 20 15:30:19 2024

@author: REYNOLDSPG21
"""

# this runs on the RPI
# the main loop that contains the socket server, carrier board objects, and all the other
# functions for a funcional simulator.

import socket
import threading
from threading import Thread, Lock
import time
from datetime import datetime
import spidev
import os

import sys
sys.path.insert(0, "/home/fsepi51/Documents/FSE_Capstone_sim") # allow this file to find other project modules

from PacketBuilder import dataEntry, errorEntry, DataPacketModel
from module_manager import Module_Manager

# these are not special queues because the RPI is not resposible for managing
# the timing of output data
commandQueue = list() # initialize to empty; a list of dataEntries that received from the master
outQueue = list() # list of dataEntries to be sent back to master
errorList = [] # most recent at end

mutex = Lock()

# assumes that one spi bus is connected to all modules
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 10000
spi.no_cs

my_module_manager = Module_Manager(spi = spi)
indicator_gpio_str = "GPIO13"
my_module_manager.make_module_entry(gpio_str=indicator_gpio_str, chType="in") # indicator light
        
# --- functions ---

def handle_client(conn, addr, commandQueue):

    # this thread reads data from the active socket, passes to the commandQueue, and waits
    # for the GPIO handler thread to place outgoing data onto the outQueue.
    # Once the outqueue is non-empty, this thread sends a response over the active socket

    print("[thread] new thread for handling the client has started")

    # recv message
    try:
        dpm = DataPacketModel.from_socket(conn)
    except ValueError as e:
        print(f"ValueError: unexpected error parsing socket data. Will close socket connection. Error is {e}")
        conn.close()
        return

    

    # if dpm.msg_type == "d":
    if dpm.data_entries is not None:
        with mutex:
            commandQueue += dpm.data_entries # now the GPIO handler can start executing thes commands
        print(f"[handle client] placed {len(dpm.data_entries)} dpm entries on command queue")
    else :
        print("[handle client] received empty data packet")
    
    
    # immediately send data back to waiting client...
    # the GPIO handler thread will place at least one element onto the outQueue
    # even if its just an ACK

    # loop infinitely while there's not stuff on the outQueue
    # and there's still stuff remaining on the commandQueue
    while len(commandQueue) > 0: # len(outQueue) != 0 and 
        # the commandQueueManager will clear the commandQueue when it finishes the batch
        pass
        
    dpm_out = DataPacketModel(dataEntries = outQueue, 
                              msg_type = "d", 
                              error_entries = errorList, 
                              time = time.time())
    
    print(f"[mt_server_w_handlers.handle_client] dpm_out is {str(dpm_out)}")
    packet_contents = dpm_out.get_packet_as_string().encode()
    try:
        conn.send(packet_contents)
    except Exception as e:
        print(f"[mt_server_w_handlers.handle_client] encountered the following error on send: {e}")
        conn.close()
        return

    outQueue.clear() # reset because we've sent all of them to the master
    errorList.clear()
    
    conn.close() # this will flush out all data on output buffer

    print("[thread] ended")

   
def commandQueueManager(commandQueue, outQueue):
    # this function runs in a continuous loop, checking for new entries
    # placed on the commandQueue by the handle_client thread

    # call the carrier board object to execute the data entries placed on the outQueue
    print("[commandQueueManager] thread has started")
    while True:
        try:
            if len(commandQueue) != 0:
                # send data to R1000
                for de in commandQueue: # a list of data entries
                    print(f"GPIO thread is treating the data for command {str(de)}...")
                    
                    # try to find the carrier board object that corresponds to the data entry
                    # this execute_command method handles the different behaviors necessary for inputs vs outputs
                    de_resp, err_resp = my_module_manager.execute_command(gpio_str = de.gpio_str, chType = de.chType, val = de.val)
                    
                    print(f"   [mt_server_w_handlesr.commandQueueManager] de_resp is {str(de_resp)}")

                    # now place the responses onto the outgoing queues for the handle_client thread
                    if err_resp is not None:
                        with mutex:
                            errorList.append(err_resp)

                    if de_resp is not None:
                        with mutex:
                            outQueue.append(de_resp)
                    else:
                        # populate with an ack response
                        with mutex:
                            outQueue.append(dataEntry(chType = f"{de.chType}", gpio_str = de.gpio_str, val = de.val, time = time.time())) # chtype as ao to avoid error raised by dataEntry class

                    
                
                with mutex:
                    # clearing the command queue is the designated
                    # way of informing the client socket thread that 
                    # this thread has finished treating the current batch of 
                    # commands. Now it can send a response
                    commandQueue.clear()
               
        except KeyboardInterrupt:
            print("commandQueueManager process terminated by keyboardinterrupt")
            return
        # except Exception as e:
            # print(f"commandQueueManager process encountered the unknown error: {str(e)}. Will exit after closing modules.")
            # my_module_manager.release_all_modules()
            # return
            # continue
        
    


    
# --- main ---
# we have this as a loop so that if child connections die, the master display can always 
# re-initiate a connection

# host = 'localhost'
host = "192.168.80.1"
port = 5000

os.system(f"sudo ip addr add {host}/24 dev eth0")

s = socket.socket()
s.settimeout(5) # Set a timeout of n seconds for the accept() call
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # solution for "[Error 89] Address already in use". Use before bind()
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # tell TCP to send out data as soon as it arrives in its buffer
s.bind((host, port))
s.listen(1)

print(f"socket listening on {socket.gethostbyname(socket.gethostname())}")

all_threads = []

gp = threading.Thread(target=commandQueueManager, args=(commandQueue, outQueue,), daemon=True)
gp.start()
all_threads.append(gp)


# turn on the network status indicator
# 2:blink rapidly, 1:solid on, 0:off
_, _ = my_module_manager.execute_command(gpio_str = indicator_gpio_str, chType = "in", val = 1)

shouldStop = False

try:
    while not shouldStop:
               
        if not shouldStop:
            # print("entered if")
            try:
                conn, addr = s.accept()
            except TimeoutError:
                # print("socket timed out... begin next loop")
                continue
        
            print("Client:", addr)
            
            t = threading.Thread(target=handle_client, args=(conn, addr, commandQueue), daemon=True)
            # set daemon to True so that the thread will terminate when the main thread terminates
            t.start()
        
            all_threads.append(t)
        
except KeyboardInterrupt:
    print("Stopped by Ctrl+C")
finally:
    print("closing all modules and GPIOs...", end="")
    my_module_manager.release_all_modules()
    print("done")
    
    print("closing spi...", end = "")
    spi.close()
    print("done")
    
    print("shutting down threads.")
    # actually, daemon=True threads will automatically close when main thread finishes
    # if s:
        # s.close()
    # for t in all_threads:
        # t.join()




print("end of script")
