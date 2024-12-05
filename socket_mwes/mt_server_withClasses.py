# -*- coding: utf-8 -*-
"""
Created on Sun Nov 10 18:55:20 2024

@author: REYNOLDSPG21
"""

# this code from https://stackoverflow.com/a/68425926
# this would run on the RPI

import socket
import threading
from threading import Thread, Lock
from typing import Union
import time
import heapq
from datetime import datetime



import sys
sys.path.append(r'C:\Users\REYNOLDSPG21\OneDrive - Grove City College\Documents\BAA Fall Semester Courses\Capstone\FSE_Capstone_sim\RPI_side')

from PacketBuilder import dataEntry, errorEntry, DataPacketModel
from CommandQueue import CommandQueue

commandQueue = CommandQueue() # initialize to empty
outQueue = CommandQueue() # data to be sent to master
errorList = [] # most recent at end

mutex = Lock()
    
        
# --- functions ---

def handle_client(conn, addr, commandQueue):
    # this thread will handle waiting for new data on socket input buffer
    # to read data sent from master and place on commandQueue datastructure
    print("[thread] starting")

    # recv message
    dpm = DataPacketModel.from_socket(conn)
    
    # in either branch, we need to fill the outQueue...
    if dpm.msg_type == "d":
        with mutex:
            commandQueue.put_all(dpm.data_entries) # now the GPIO handler can start executing thes commands
            print("[handle client] placed dpm entries on command queue")
    elif dpm.msg_type == "w":
        # don't put anything on command queue
        readAllInputChannels(outQueue) # put data on outqueue
        
    # print("parsed data entries on socket")
    # print(f"commandQueue is now {str(commandQueue)}")
    
    
    # immediately send data back to waiting client...
    while len(outQueue)!=0:
        pass # wait until GPIO handler thread has read inputs from R1000
        # now there's data to send back to client
        
    print("sending data to client...")
    print("   popping all...", end="")
    de = outQueue.pop_all()
    print(f"popped de is {str(de)}")
    print("done")
    dpm_out = DataPacketModel(de, "d", None, time.time())
    
        
    conn.send(dpm_out.get_packet_as_string().encode())
    print("done.")
    
    conn.close() # this will flush out all data on output buffer

    print("[thread] ending")

def readAllInputChannels(outQueue):
    # read data from R1000 and send to master
    # case if msg_type is 'w'
    de = dataEntry("ai", "channeld2", 0.001, time=time.time())
    outQueue.put(de)
    print("readAllInputChannels finished.")
    
def handleGPIO(commandQueue):
    # case if msg_type is 'd'
    # read the commandQueue datastructure, do action, them pop
    # also place read data from R1000 on the appropriate ds
    print("spinning up gpio handler...")
    try:
        while True:
            ToDo = commandQueue.pop_all_due() # a list of entries
            if len(ToDo) != 0:
                # send data to R1000
                for el in ToDo:
                    print(f"GPIO thread is outputting the data for entry {str(el)}...")
                
                readAllInputChannels(outQueue)
                print(f"[handleGPIO] read all channels")
                
    except KeyboardInterrupt:
        print("GPIO process terminated by keyboardinterrupt")
        return


    
# --- main ---
# we have this as a loop so that if child connections die, the master display can always 
# re-initiate a connection

host = 'localhost'
port = 5000

s = socket.socket()
s.settimeout(5) # Set a timeout of n seconds for the accept() call
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # solution for "[Error 89] Address already in use". Use before bind()
s.bind((host, port))
s.listen(1)

all_threads = []

gp = threading.Thread(target=handleGPIO, args=(commandQueue,))
gp.start()
all_threads.append(gp)

shouldStop = False

try:
    while not shouldStop:
        # print("Waiting for client")
        # print(commandQueue)
        
        # with mutex:
        #     print("main thread sees commandQueue="+str(commandQueue))
            # if len(commandQueue)!=0:
            #     print("main thread sees commandQueue[0][0]=" + str(commandQueue[0][0]))
            #     if commandQueue[0][0] == "stop":
            #         shouldStop = True
            # else:
            #     print("main thread sees commandQueue is empty")
                
        if not shouldStop:
            # print("entered if")
            try:
                conn, addr = s.accept()
            except TimeoutError:
                # print("socket timed out... begin next loop")
                continue
        
            print("Client:", addr)
            
            t = threading.Thread(target=handle_client, args=(conn, addr, commandQueue))
            t.start()
        
            all_threads.append(t)
        
except KeyboardInterrupt:
    print("Stopped by Ctrl+C")
finally:
    print("shutting down threads.")
    if s:
        s.close()
    for t in all_threads:
        t.join()
        
print("end of script")