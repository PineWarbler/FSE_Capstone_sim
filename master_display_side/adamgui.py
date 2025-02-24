import customtkinter as ctk
from tkdial import Meter
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
import os
os.chdir('../') #equivalent to %cd ../ # go to parent folder
from PacketBuilder import dataEntry, errorEntry, DataPacketModel
os.chdir('./master_display_side') #equivalent to %cd tests # return to base dir
from channel_definitions import Channel_Entries, Channel_Entry
from SocketSenderManager import SocketSenderManager
# enable logging
import sys
import logging
import traceback
from datetime import datetime


# log uncaught exceptions to file
def exception_handler(type, value, tb):
    for line in traceback.TracebackException(type, value, tb).format(chain=True):
        logging.exception(line)
        print(line)
    logging.exception(value)
    print(value)
    

# load channel entries from config file
my_channel_entries = Channel_Entries()
my_channel_entries.load_from_config_file(config_file_path="config.json")

socketRespQueue = queue.Queue() # will contain responses from the RPi
SSM = SocketSenderManager(host="192.168.80.1", port=5000,
                          q=socketRespQueue, socketTimeout=5, testSocketOnInit=False, startupLoopDelay=1)
# # we will call this object's methods: `place_ramp`, `place_single_mA`, and `place_single_EngineeringUnits`
# # to send commands to the RPi

# Configure the main application window
app = ctk.CTk()
app.wm_iconbitmap('app_icon.ico')
app.title("ICS Phase II - Beta")
app.geometry(f"{app.winfo_screenwidth()}x{app.winfo_screenheight()}")
app.grid_rowconfigure(0, weight=1)
app.grid_columnconfigure(0, weight=1)

# enable logging. TKinter requires a weird trick. See https://stackoverflow.com/a/44004413
logging.basicConfig(filename=f'instance_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log', encoding='utf-8', level="critical")
app.report_callback_exception = exception_handler # this here.

def shutdown():
    SSM.close() # removes any enqueued command requests
    app.destroy()
    
app.protocol("WM_DELETE_WINDOW", shutdown)

# Main container frame
main_frame = ctk.CTkFrame(app)
main_frame.grid(row=0, column=0, sticky="nsew")
main_frame.grid_rowconfigure((0, 1, 2, 3), weight=1)
main_frame.grid_columnconfigure((0, 1), weight=1)

# Create frames for organization
analog_outputs_frame = ctk.CTkFrame(main_frame, corner_radius=10)
analog_outputs_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

analog_inputs_frame = ctk.CTkFrame(main_frame, corner_radius=10)
analog_inputs_frame.grid(row=0, column=1, padx=10, pady=10, sticky="ne")

digital_outputs_frame = ctk.CTkFrame(main_frame, corner_radius=10)
digital_outputs_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

digital_inputs_frame = ctk.CTkFrame(main_frame, corner_radius=10)
digital_inputs_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

error_frame = ctk.CTkFrame(main_frame, corner_radius=10)
error_frame.grid(row=2, column=1, padx=10, pady=10, sticky="nsew")

connector_frame = ctk.CTkFrame(main_frame, corner_radius=10)
connector_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")



# Analog Outputs with Scrollbar
analog_outputs_label = ctk.CTkLabel(analog_outputs_frame, text="Analog Outputs", font=("Arial", 16))
analog_outputs_label.pack(pady=10)

ai_label = ctk.CTkLabel(analog_inputs_frame, text="Analog Inputs", font=("Arial", 16))#.pack(pady=10)
ai_label.grid(row=0, column=0, pady=10, sticky="nsew")


scrollable_frame = ctk.CTkScrollableFrame(master=analog_outputs_frame, width=500)
scrollable_frame.pack(fill="both", expand=True)


# we'll need to keep references to the meter objects so we can update the meter readings
ai_meter_objects = dict() # key:value = "IVT":<Meter obj>

currCol = 0
currRow = 0
numInCurrCol=0
for name, ch_entry in my_channel_entries.channels.items():

    if ch_entry.sig_type.lower() != "ai" or not ch_entry.showOnGUI:
        continue
    # UVT Gauge
    meter_frame = ctk.CTkFrame(analog_inputs_frame)
    # currRow + 1 because first row is reserved for AI frame label
    meter_frame.grid(column=currCol, row=currRow+1, padx=10, pady=0, sticky="nsew")
    print(f"row,col={currRow},{currCol}")
    meter = Meter(meter_frame, scroll_steps=0, interactive=False, radius=200)
    
    
    meter.grid(row=0,column=0, padx=10, pady=10, sticky="nsew")

    l = ctk.CTkLabel(meter_frame, text=f"{name} ({ch_entry.units})")
    l.grid(row=1, column=0, pady=10, sticky="s")
    ai_meter_objects[name] = meter
    
    numInCurrCol += 1
    currRow = (currRow + 1)%2
    
    if numInCurrCol == 2:
        numInCurrCol = 0
        currCol +=1
    
    
saved_values = {}


def toggle_dropdown(frame,parent_frame,sendBtn, arrowBtn):
    if frame.winfo_ismapped():
        sendBtn.configure(state="normal")
        frame.pack_forget()
        arrowBtn.configure(text="⬇")
    else:
        frame.pack(after=parent_frame, pady=5)
        current_dropdown = frame
        sendBtn.configure(state="disabled")
        arrowBtn.configure(text="↑")

def save_range_values(name, start_entry, end_entry, rate_entry, frame):
    start = float(start_entry.get()) if start_entry.get() else 0
    end = float(end_entry.get()) if end_entry.get() else 100
    rate = float(rate_entry.get()) if rate_entry.get() else 1

    saved_values[name] = {"start": start, "end": end, "rate": rate}
    frame.pack_forget()

def save_input_value(name, input_value_entry, current_label):
    input_value = float(input_value_entry.get()) if input_value_entry.get() else 0

    if name in saved_values:
        start = saved_values[name].get("start", 0)
        end = saved_values[name].get("end", 100)

        # Linear scaling from input value to 4-20 mA
        scaled_current = 4 + ((input_value - start) / (end - start)) * (20 - 4)
        scaled_current = max(4, min(20, scaled_current))  # Ensure within bounds
        saved_values[name]["current"] = scaled_current
        current_label.configure(text=f"{scaled_current:.2f} mA")
    else:
        current_label.configure(text="4.00 mA")

def create_dropdown(parent, name):
    frame = ctk.CTkFrame(parent)

    ddminLabel = ctk.CTkLabel(frame, text="Minimum Value")
    ddminLabel.pack()
    ddminEntry = ctk.CTkEntry(frame, width=100)
    ddminEntry.pack()

    ddmaxLabel = ctk.CTkLabel(frame, text="Maximum Value")
    ddmaxLabel.pack()
    ddmaxEntry = ctk.CTkEntry(frame, width=100)
    ddmaxEntry.pack()

    ddrateLabel = ctk.CTkLabel(frame, text="Rate")
    ddrateLabel.pack()
    ddrateEntry = ctk.CTkEntry(frame, width=100)
    ddrateEntry.pack()

    button_frame = ctk.CTkFrame(frame)
    button_frame.pack(pady=5)

    sendBtn = ctk.CTkButton(button_frame, text="Save", fg_color="blue")# ,
                #   command=lambda: save_range_values(name, start_entry, end_entry, rate_entry, frame))
    sendBtn.pack(side="left", padx=5)

    # disabled because cancel would need to toggle the active state of the send button, but we don't have scope access to that btn obj
    ctk.CTkButton(button_frame, text="Cancel", fg_color="red", command=lambda: frame.pack_forget()).pack(side="left", padx=5)

    return [frame, ddminLabel, ddminEntry, ddmaxLabel, ddmaxEntry, ddrateLabel, ddrateEntry, sendBtn]

def place_single(name:str, entry, segmentedUnitButton):
    val = float(entry.get())
    unit = str(segmentedUnitButton.get())
    print(f"[place_single] name is {name}, entry is {val}, unit is {unit}")
    if unit == "mA":
        SSM.place_single_mA(ch2send=my_channel_entries.getChannelEntry(sigName=name), mA_val=float(val), time=time.time())
    else:
        SSM.place_single_EngineeringUnits(ch2send=my_channel_entries.getChannelEntry(sigName=name), val_in_eng_units=float(val), time=time.time())
    entry.delete(0, ctk.END) # clear entry contents. See https://stackoverflow.com/a/74507736

def place_ramp(name:str, startEntry, stopEntry, rateEntry, segmentedUnitButton):
    startVal = float(startEntry.get())
    stopVal = float(stopEntry.get())
    rateVal = float(rateEntry.get())
    unit = str(segmentedUnitButton.get())
    chEntry = my_channel_entries.getChannelEntry(sigName=name)
    # print(f"[place_ramp] name is {name}, entry is {val}, unit is {unit}")
    if unit != "mA": # convert to mA if not already
        startVal = chEntry.EngineeringUnits_to_mA(startVal)
        stopVal = chEntry.EngineeringUnits_to_mA(stopVal)
        rateVal = chEntry.EngineeringUnitsRate_to_mARate(rateVal)
    print(f"start:{startVal}, stop:{stopVal}, rate:{rateVal}")
    success = SSM.place_ramp(ch2send=chEntry, start_mA=startVal, stop_mA=stopVal, stepPerSecond_mA=rateVal)
    if success:
        startEntry.delete(0, ctk.END) # clear entry contents. See https://stackoverflow.com/a/74507736
        stopEntry.delete(0, ctk.END) # clear entry contents. See https://stackoverflow.com/a/74507736
        rateEntry.delete(0, ctk.END) # clear entry contents. See https://stackoverflow.com/a/74507736
        

def segmented_button_callback(unit, dminLabel, dmaxLabel, drateLabel):
    # print(f"unit is {unit}")
    # unit = str(segmentedUnitButton.get())
    dminLabel.configure(text=f"Start ({unit})")
    dmaxLabel.configure(text=f"Stop ({unit})")
    drateLabel.configure(text=f"Rate ({unit}/s)")

# Create analog outputs with separate dropdowns and input fields
# or whatever element of the row that will need to be updated with value
ao_label_objects = dict() # key:value = "SPT":[<label obj>,dd1,dd2,dd3] where ddx are labels of start, stop, and rate boxes
for name, ch_entry in my_channel_entries.channels.items():
    if ch_entry.sig_type.lower() != "ao" or not ch_entry.showOnGUI:
        continue
    frame = ctk.CTkFrame(scrollable_frame)
    frame.pack(pady=5, fill='x')

    ctk.CTkLabel(frame, text=f"{name}").grid(row=0, column=0, padx=5, sticky="w")
    input_value_entry = ctk.CTkEntry(frame, width=100)
    input_value_entry.grid(row=0, column=1, padx=5)

    unitSelector = ctk.CTkSegmentedButton(frame, values=[f"{ch_entry.units}", "mA"], selected_color="green", selected_hover_color="green")
    
    save_text_button = ctk.CTkButton(frame, text="Save", fg_color="blue", command=lambda n=name, e=input_value_entry, s=unitSelector: place_single(n, e, s))
    save_text_button.grid(row=0, column=3, padx=5)
    
    dropdown_frame, ddminLabel, ddminEntry, ddmaxLabel, ddmaxEntry, ddrateLabel, ddrateEntry, sendBtn = create_dropdown(scrollable_frame, name)
    # dropdown_frame, ddmin, ddmax, ddrate, sendBtn = create_dropdown(scrollable_frame, name)
    arrow_button = ctk.CTkButton(frame, text="⬇", width=20)
    arrow_button.configure(command=lambda f=dropdown_frame, p=frame, b=save_text_button, ab=arrow_button: toggle_dropdown(f, p, b, ab))
    arrow_button.grid(row=0, column=4, padx=5)
    dropdown_frame.pack_forget()
    
    # dropdown menu send ramp command
    sendBtn.configure(command=lambda n=name, dmin=ddminEntry, dmax=ddmaxEntry, drate=ddrateEntry, us=unitSelector: place_ramp(n, dmin, dmax, drate, us))
    
    
    unitSelector.configure(command = lambda unit=unitSelector.get(), dmin=ddminLabel, dmax=ddmaxLabel, drate=ddrateLabel: segmented_button_callback(unit,dmin,dmax,drate))
    segmented_button_callback(ch_entry.units, ddminLabel, ddmaxLabel, ddrateLabel) # set default units to engineering
    unitSelector.set(f"{ch_entry.units}")
    unitSelector.grid(row=0, column=2, padx=5)
        
    lastSentLabel = ctk.CTkLabel(frame, text="") # initialize empty at first
    lastSentLabel.grid(row=0, column=5, padx=5, sticky="e")
    ao_label_objects[name] = lastSentLabel

def toggleDOswitch(name:str, ctkSwitch):
    val = ctkSwitch.get()
    SSM.place_single_EngineeringUnits(ch2send=my_channel_entries.getChannelEntry(sigName=name), val_in_eng_units=int(val), time=time.time())
    # if ctkSwitch.state == "normal":
    ctkSwitch.configure(state="disabled")
    # else:
        # ctkSwitch.configure(state="normal")
        
# digital outputs
do_switches = dict() # like name:<switch obj>
ctk.CTkLabel(digital_outputs_frame, text="Digital Outputs", font=("Arial", 16)).pack(pady=10)


for name, ch_entry in my_channel_entries.channels.items():

    if ch_entry.sig_type.lower() != "do" or not ch_entry.showOnGUI:
        continue

    motor_status_switch = ctk.CTkSwitch(digital_outputs_frame, text=ch_entry.name, onvalue=1, offvalue=0)
    motor_status_switch.configure(command = lambda n=name, switchObj=motor_status_switch: toggleDOswitch(n, motor_status_switch))
    motor_status_switch.pack(pady=10)
    motor_status_switch.select()
    do_switches[name] = motor_status_switch

# Digital Inputs
def toggle_light():
    indicator_light.configure(fg_color="green" if motor_status_switch.get() else "red")

di_label_objects = dict() # key:value = "AOP":<label obj>. Change the fg_color
ctk.CTkLabel(digital_inputs_frame, text="Digital Inputs", font=("Arial", 16)).pack(pady=10)

ctk.CTkLabel(error_frame, text="Errors", font=("Arial", 16)).pack(pady=10)
for name, ch_entry in my_channel_entries.channels.items():

    if ch_entry.sig_type.lower() != "di" or not ch_entry.showOnGUI:
        continue

    indicator_frame = ctk.CTkFrame(digital_inputs_frame)
    indicator_frame.pack(pady=10)
    indicator_label = ctk.CTkLabel(indicator_frame, text=ch_entry.name)
    indicator_label.pack(side="left", padx=10)
    indicator_light = ctk.CTkLabel(indicator_frame, text="", width=20, height=20, corner_radius=10, fg_color="red")
    di_label_objects[name] = indicator_light
    indicator_light.pack(side="left")


def process_queue():
    while not socketRespQueue.empty():
        sockResp = socketRespQueue.get() # could be a dataEntry or an errorEntry
        print(f"sockResp is {sockResp}")
        if isinstance(sockResp, dataEntry):
            if sockResp.gpio_str == "SocketSenderManager is online":
                # TODO: online status gui element?
                continue

            chEntry = my_channel_entries.get_channelEntry_from_GPIOstr(sockResp.gpio_str)
            if chEntry is None:
                if sockResp.gpio_str == "ack":
                    print("received ack packet")
                continue

            if chEntry.sig_type.lower() == "ai":
                meterObj = ai_meter_objects[chEntry.name]
                meterObj.set(chEntry.mA_to_EngineeringUnits(sockResp.val)) # move needle on meter
            elif chEntry.sig_type.lower() == "di":
                if int(sockResp.val) == 1:
                    di_label_objects[chEntry.name].configure(fg_color = "green")
                else:
                    di_label_objects[chEntry.name].configure(fg_color = "gray")
            elif chEntry.sig_type.lower() == "do":
                # then the response is ack from RPI
                do_switches[chEntry.name].configure(state="normal") # make togglable again
                # after receive confirmation of execution
                # print("empty branch for do")
            elif "ao" in chEntry.sig_type.lower(): # response is like "ao ack"
                # then the response is ack from RPI
                labelObj = ao_label_objects.get(chEntry.name)
                # labelObj.text = 
                labelObj.configure(text=f"{sockResp.val:.{1}f} mA")
                print(f"updated label to {sockResp.val} mA")
                # labelObj.text_color = "green"
                
        elif isinstance(sockResp, errorEntry):
            print(f"received error entry: {sockResp}")
            # pass

    # TODO: finally, place read periodic read requests for ai and di channels
    for name,meter in ai_meter_objects.items():
        # only the ch2send name is important. value can be whatever
        ch = my_channel_entries.getChannelEntry(name)
        if ch.getGPIOStr() is None:
            pass # print("invalid gpio config?")
        else:
            pass
            # print(f"auto-placing read request for {ch.name}")
            # SSM.place_single_EngineeringUnits(ch2send=ch, val_in_eng_units=3.14, time=time.time())
            
    # this di placer has the same problem with unmapped gpios, so I've commented it out until i fix the ai ^^
    # for name,label_obj in di_label_objects.items():
    # SSM.place_single_EngineeringUnits(ch2send=my_channel_entries.getChannelEntry(name), val_in_eng_units=0, time=time.time())

    app.after(500, process_queue)  # Check queue again after 100ms

# print("after defined process_queue")
app.after(0, func=process_queue)
SSM.startupLoopDelay=0.1
print(f"for tkinter file: {threading.current_thread()}")


import socket

# Function to display error message in error_frame
def show_error(message):
    for widget in error_frame.winfo_children():
        widget.destroy()  # Clear previous content

    # Title
    title_label = ctk.CTkLabel(error_frame, text="Error", font=("Arial", 16))
    title_label.pack(pady=(5, 2))

    # Error message
    error_label = ctk.CTkLabel(error_frame, text=message, text_color="red", font=("Arial", 14))
    error_label.pack(padx=10, pady=5)

# Function to check network connection and update connector_frame
def check_connection():
    for widget in connector_frame.winfo_children():
        widget.destroy()  # Clear previous content

    # Title
    title_label = ctk.CTkLabel(connector_frame, text="Connection Status", font=("Arial", 16))
    title_label.pack(pady=(5, 2))

    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        status_label = ctk.CTkLabel(connector_frame, text="Connected ✅", text_color="green", font=("Arial", 14))
    except OSError:
        status_label = ctk.CTkLabel(connector_frame, text="No Connection ❌", text_color="red", font=("Arial", 14))

    status_label.pack(padx=10, pady=5)

# Example usage
show_error("Invalid Input!")
check_connection()





app.mainloop()
