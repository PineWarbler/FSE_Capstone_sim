# -*- coding: utf-8 -*-
print("Importing libraries...", end="")
import customtkinter as ctk
from tkdial import Meter
import queue
import time
import os
import sys
from collections import deque
import json

current_dir = os.path.dirname(os.path.abspath(__file__)) # Get the current file's directory
parent_dir = os.path.dirname(current_dir) # Get the parent directory
sys.path.append(parent_dir) # Add the parent directory to sys.path

from PacketBuilder import dataEntry, errorEntry # this class is in the parent dir
from channel_definitions import Channel_Entries
from SocketSenderManager import SocketSenderManager
# enable logging
import logging
import traceback
from datetime import datetime

print("done.")

# log uncaught exceptions to file
def exception_handler(type, value, tb):
    for line in traceback.TracebackException(type, value, tb).format(chain=True):
        logging.exception(line)
        print(line)
    logging.exception(value)
    print(value)
    
print("Reading config.json...", end="")

# load channel entries from config file
my_channel_entries = Channel_Entries()
my_channel_entries.load_from_config_file(config_file_path="config.json")

# now read the `runtime_settings`
with open("config.json", 'r') as f:
    all_json = json.load(f)

try:
    runtime_settings = all_json.get("runtime_settings")
    error_stack_max_len = max(runtime_settings.get("error_stack_max_len", 20), 1) # second parameter to `get` is default value if key doesn't exist
    enable_verbose_logging = runtime_settings.get("enable_verbose_logging", True)
    ai_LPF_boxcar_length = max(runtime_settings.get("ai_LPF_boxcar_length", 5), 1)
    poll_buffer_period_ms = max(runtime_settings.get("poll_buffer_period_ms", 200), 1)
    socket_timeout_s = max(runtime_settings.get("socket_timeout_s", 3), 0)
except Exception as e:
    logging.exception(f"Failed to parse `config.json` file because of error: {e}. Will assert default values.")

print("done")

print("Initializing window and background processes...")


socketRespQueue = queue.Queue() # will contain responses from the RPi
SSM = SocketSenderManager(host="192.168.80.1", port=5000,
                          q=socketRespQueue, socketTimeout=socket_timeout_s, 
                          testSocketOnInit=False, loopDelay=1, log=enable_verbose_logging)
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
logging.basicConfig(filename=f'./logs/instance_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log', encoding='utf-8', level="critical")
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
analog_inputs_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

digital_outputs_frame = ctk.CTkFrame(main_frame, corner_radius=10)
digital_outputs_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

digital_inputs_frame = ctk.CTkFrame(main_frame, corner_radius=10)
digital_inputs_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

##### error reporting frame ######
error_frame = ctk.CTkFrame(main_frame, corner_radius=10)
error_frame.grid(row=2, column=1, padx=10, pady=10, sticky="nsew")
error_frame_label = ctk.CTkLabel(error_frame, text="Errors", font=("Arial", 16))
error_frame_label.pack(pady=(5, 2))
# Error message label that can be updated
error_label = ctk.CTkLabel(error_frame, text="", text_color="red", font=("Arial", 15), wraplength=400, justify="left")
error_label.pack(padx=10, pady=5, side="left")
# clear button that clears the most recent error
error_clear_btn = ctk.CTkButton(error_frame, text="x", fg_color="red", hover_color="red", width=40) # , command=lambda f=frame, n=name: cancel_ramp_callback(frame=f, sigName=n)
error_clear_btn.pack(padx=0, pady=5, side="right")
error_clear_btn.pack_forget()

error_stack  = deque(maxlen = error_stack_max_len) # only store the last 20 messages to prevent memory hogged by time out errors

#### connection status frame #####
connector_frame = ctk.CTkFrame(main_frame, corner_radius=10)
connector_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

# Connection status pane: write once
ctk.CTkLabel(connector_frame, text="Connection Status", font=("Arial", 16)).pack(pady=(5, 2))
status_label = ctk.CTkLabel(connector_frame, text="Unknown", text_color="gray", font=("Arial", 15))
status_label.pack(padx=10, pady=5)


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
    # print(f"row,col={currRow},{currCol}")
    meter = Meter(meter_frame, scroll_steps=0, interactive=False, radius=170, text_font = ctk.CTkFont("Arial", size=14), integer=False)
    # integer=True because we're displaying a percentage that doesn't require the default 2 decimal places
    
    
    meter.grid(row=0,column=0, padx=10, pady=10, sticky="nsew")

    l = ctk.CTkLabel(meter_frame, text=f"{name} ({ch_entry.units})")
    l.grid(row=1, column=0, pady=10, sticky="s")
    ai_meter_objects[name] = meter
    
    numInCurrCol += 1
    currRow = (currRow + 1)%2
    
    if numInCurrCol == 2:
        numInCurrCol = 0
        currCol +=1
    
    
def toggle_dropdown(frame,parent_frame,sendBtn, arrowBtn):
    if frame.winfo_ismapped():
        sendBtn.configure(state="normal")
        frame.pack_forget()
        arrowBtn.configure(text="⬇ Ramp")
    else:
        frame.pack(after=parent_frame, pady=5)
        sendBtn.configure(state="disabled")
        arrowBtn.configure(text="⬆")

def cancel_ramp_callback(frame, sigName:str):
    # frame.pack_forget()
    ch = my_channel_entries.getChannelEntry(sigName)
    if ch.getGPIOStr() is None:
        return
    # print(f"SSM.theCommandQueue.len is {len(SSM.theCommandQueue)}")
    # print(f"Entire SSM.theCommandQueue is {SSM.theCommandQueue}")
    numRemoved = SSM.clearAllEntriesWithGPIOStr(ch.getGPIOStr())
    # print(f"removed {numRemoved} entries with sigName={sigName}")
    # SSM.clearCommandQueue()
    
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

    sendBtn = ctk.CTkButton(button_frame, text="Send", fg_color="blue")
    sendBtn.pack(side="left", padx=5)

    clear_btn = ctk.CTkButton(button_frame, text="Cancel", fg_color="red", command=lambda f=frame, n=name: cancel_ramp_callback(frame=f, sigName=n))
    clear_btn.pack(side="left", padx=5)
    

    return [frame, ddminLabel, ddminEntry, ddmaxLabel, ddmaxEntry, ddrateLabel, ddrateEntry, sendBtn]

def place_single(name:str, entry, segmentedUnitButton):
    try:
        val = float(entry.get())
    except ValueError:
        return
    
    unit = str(segmentedUnitButton.get())
    if enable_verbose_logging:
        print(f"[place_single] name is {name}, entry is {val}, unit is {unit}")
    
    success = None
    if unit == "mA":
        success, errorString = SSM.place_single_mA(ch2send=my_channel_entries.getChannelEntry(sigName=name), mA_val=float(val), time=time.time())
        # print(f"mA placement success: {success}")
    else:
        success, errorString = SSM.place_single_EngineeringUnits(ch2send=my_channel_entries.getChannelEntry(sigName=name), val_in_eng_units=float(val), time=time.time())
    print(f"success for place_single is {success}")  
    if success:
        entry.delete(0, ctk.END) # clear entry contents. See https://stackoverflow.com/a/74507736    
    else:
        socketRespQueue.put(errorEntry(f"{name} single input", criticalityLevel="medium", description=errorString))
    

def place_ramp(name:str, startEntry, stopEntry, rateEntry, segmentedUnitButton):
    try:
        startVal = float(startEntry.get())
        stopVal = float(stopEntry.get())
        rateVal = float(rateEntry.get())
    except ValueError:
        return
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
    else:
        if unit == "mA":
            socketRespQueue.put(errorEntry(f"{name} ramp input", criticalityLevel="medium", description=f"Invalid ramp command for {chEntry.name}. Valid range: 4 - 20 mA."))
        else:
            socketRespQueue.put(errorEntry(f"{name} ramp input", criticalityLevel="medium", description=f"Invalid ramp command for {chEntry.name}. Valid range: {chEntry.realUnitsLowAmount} - {chEntry.realUnitsHighAmount} {chEntry.units}"))
        

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
    
    save_text_button = ctk.CTkButton(frame, text="Send", fg_color="blue", command=lambda n=name, e=input_value_entry, s=unitSelector: place_single(n, e, s))
    save_text_button.grid(row=0, column=3, padx=5)
    
    dropdown_frame, ddminLabel, ddminEntry, ddmaxLabel, ddmaxEntry, ddrateLabel, ddrateEntry, sendBtn = create_dropdown(scrollable_frame, name)
    # dropdown_frame, ddmin, ddmax, ddrate, sendBtn = create_dropdown(scrollable_frame, name)
    arrow_button = ctk.CTkButton(frame, text="⬇ Ramp", width=20)
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
    val = ctkSwitch.get() # should be an integer already
    success = SSM.place_single_EngineeringUnits(ch2send=my_channel_entries.getChannelEntry(sigName=name), val_in_eng_units=int(val), time=time.time())
    
    ctkSwitch.configure(state="disabled") # wait for a response from RPi to enable again
        
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
    indicator_light.configure(fg_color="green" if motor_status_switch.get() else "gray")

di_label_objects = dict() # key:value = "AOP":<label obj>. Change the fg_color
ctk.CTkLabel(digital_inputs_frame, text="Digital Inputs", font=("Arial", 16)).pack(pady=10)

for name, ch_entry in my_channel_entries.channels.items():

    if ch_entry.sig_type.lower() != "di" or not ch_entry.showOnGUI:
        continue

    indicator_frame = ctk.CTkFrame(digital_inputs_frame)
    indicator_frame.pack(pady=10, padx=20, side="left", expand=True)
    indicator_label = ctk.CTkLabel(indicator_frame, text=ch_entry.name)
    indicator_label.pack(side="left", padx=10)
    indicator_light = ctk.CTkLabel(indicator_frame, text="", width=20, height=20, corner_radius=10, fg_color="gray")
    di_label_objects[name] = indicator_light
    indicator_light.pack(side="left")

def pop_error():
    if len(error_stack) == 0:
        show_error("")
        return
    error_stack.pop()
    if len(error_stack) == 0:
        show_error("")
        return
    err_to_show = error_stack.pop()
    show_error(err_to_show) # this function will append it back onto the stack
    
error_clear_btn.configure(command = pop_error)
    
# Function to display error message in error_frame
def show_error(message:str):
    error_label.configure(text=message)
    error_label.configure(text_color="red")
    if message == "":
        error_clear_btn.pack_forget()
    else:
        error_clear_btn.pack(padx=0, pady=5, side="right")
        error_stack.append(message)
    # print(len(error_stack))
    if len(error_stack) >= error_stack_max_len:
        error_frame_label.configure(text=f"Errors ({len(error_stack)}+)")
    else:
        error_frame_label.configure(text=f"Errors ({len(error_stack)})")


# Function to write connector_frame with network status
def show_connection_status(online:bool|None, message:str=""):
    if online is None:
        status_label.configure(text="Unknown")
        status_label.configure(text_color="gray")
        
    if online:
        status_label.configure(text=f"Connected ✓{message}")
        status_label.configure(text_color="green")
    else:
        status_label.configure(text=f"No Connection ❌{message}")
        status_label.configure(text_color="red")

    

# we have to call these on startup for them to initialize their frames
show_error(message="")
show_connection_status(online=None)
    
def process_queue():
    while not socketRespQueue.empty():
        sockResp = socketRespQueue.get() # could be a dataEntry or an errorEntry
        
        if enable_verbose_logging:
            print(f"sockResp is {sockResp}")

        if isinstance(sockResp, errorEntry):
            if sockResp.source.lower()[0] == "a" and "loop error" in sockResp.description.lower(): # a loop error
                gpio_str = sockResp.description.split(":")[1].strip() # description is in form: Loop error detected:{gpio_str}
                chEntry_to_blame = my_channel_entries.get_channelEntry_from_GPIOstr(gpio_str)
                # if chEntry_to_blame is None:
                #     print()
                #     continue
                show_error(message=f"loop error detected for {chEntry_to_blame.name} at board slot {chEntry_to_blame.boardSlotPosition}")

            elif "ethernet" in sockResp.source.lower():
                show_connection_status(online=False)
                show_error(message=sockResp.description)

            else:
                show_error(message=sockResp.description)
                print(f"received error entry: {sockResp}")
            
        elif isinstance(sockResp, dataEntry):
            show_connection_status(online=True)
        
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
                # print(f"chEntry.sig_type is {chEntry.sig_type.lower()}")
                labelObj = ao_label_objects.get(chEntry.name)
                # the dataEntry packet response might have NAK for the value if the ao module has a loop error
                if sockResp.val == "NAK":
                    labelObj.configure(text="ERR")
                else:
                    # update label to indicate receiving of ACK echo from RPi
                    labelObj.configure(text=f"{sockResp.val:.{1}f} mA")
                

    ## finally, place read periodic read requests for ai and di channels
    ## ai channels first
    for name,meter in ai_meter_objects.items():
        # only the ch2send name is important. value can be whatever
        ch = my_channel_entries.getChannelEntry(name)
        if ch.getGPIOStr() is None:
            pass # print("invalid gpio config?")
        else:
            # using place_single_mA instead of place_single_EngineeringUnits
            # because the mA_val is interpreted for `ai` channels only as the number of samples to take
            # in the averaging filter
            SSM.place_single_mA(ch2send=ch, mA_val=ai_LPF_boxcar_length, time=time.time())
            
    ## this di placer has the same problem with unmapped gpios, so I've commented it out until i fix the ai ^^
    for name,label_obj in di_label_objects.items():
        try:
            SSM.place_single_EngineeringUnits(ch2send=my_channel_entries.getChannelEntry(name), val_in_eng_units=0, time=time.time())
        except Exception as e:
            print(f"Encountered error: {e}")

    app.after(poll_buffer_period_ms, process_queue)  # Check queue again after specified period

# print("after defined process_queue")
app.after(0, func=process_queue)
SSM.loopDelay=0.1
# print(f"for tkinter file: {threading.current_thread()}")

app.mainloop()
