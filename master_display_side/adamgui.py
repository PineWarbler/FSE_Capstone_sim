import customtkinter as ctk
from tkdial import Meter
import queue
import threading
import time
import tkinter as tk
import os
os.chdir('../') #equivalent to %cd ../ # go to parent folder
from PacketBuilder import dataEntry, errorEntry, DataPacketModel
os.chdir('./master_display_side') #equivalent to %cd tests # return to base dir
from channel_definitions import Channel_Entries, Channel_Entry
# from SocketSenderManager import SocketSenderManager

# load channel entries from config file
my_channel_entries = Channel_Entries()
my_channel_entries.load_from_config_file(config_file_path="config.json")

# socketRespQueue = queue.Queue() # will contain responses from the RPi
# SSM = SocketSenderManager(host="192.168.80.1", port=5000,
#                           q=socketRespQueue, socketTimeout=1.5, testSocketOnInit=False, startupLoopDelay=1)
# bth = threading.Thread(target=SSM._loopCommandQueue, daemon=True)
# SSM.setThread(th=bth)
# SSM.cqLoopThreadReference.start()
# # we will call this object's methods: `place_ramp`, `place_single_mA`, and `place_single_EngineeringUnits`
# # to send commands to the RPi

# Configure the main application window
app = ctk.CTk()
app.title("ICS Phase II - Beta")
app.geometry(f"{app.winfo_screenwidth()}x{app.winfo_screenheight()}")
app.grid_rowconfigure(0, weight=1)
app.grid_columnconfigure(0, weight=1)

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
digital_outputs_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

digital_inputs_frame = ctk.CTkFrame(main_frame, corner_radius=10)
digital_inputs_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

# Analog Outputs with Scrollbar
analog_outputs_label = ctk.CTkLabel(analog_outputs_frame, text="Analog Outputs", font=("Arial", 16))
analog_outputs_label.pack(pady=10)

ctk.CTkLabel(analog_inputs_frame, text="Analog Inputs", font=("Arial", 16)).pack(pady=10)

canvas_frame = ctk.CTkFrame(analog_outputs_frame)
canvas_frame.pack(fill="both", expand=True)

DARK_GREY= "#333333"
canvas = tk.Canvas(canvas_frame, bg=DARK_GREY)
scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
scrollable_frame = ctk.CTkFrame(canvas)

scrollable_frame.bind(
    "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# we'll need to keep references to the meter objects so we can update the meter readings
ai_meter_objects = dict() # key:value = "IVT":<Meter obj>
for name, ch_entry in my_channel_entries.channels.items():

    if ch_entry.sig_type.lower() != "ai" or not ch_entry.showOnGUI:
        continue
    # UVT Gauge
    meter_frame = ctk.CTkFrame(analog_inputs_frame)
    meter_frame.pack(pady=5)
    meter = Meter(meter_frame, scroll_steps=0, interactive=False, radius=200)
    # meter.set(50)
    meter.pack()
    ctk.CTkLabel(meter_frame, text=f"{name} ({ch_entry.units})").pack()
    ai_meter_objects[name] = meter

saved_values = {}


def toggle_dropdown(frame,parent_frame):
    if frame.winfo_ismapped():
        frame.pack_forget()
    else:
        frame.pack(after=parent_frame, pady=5)
        current_dropdown = frame

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

    ctk.CTkLabel(frame, text="Minimum Value").pack()
    start_entry = ctk.CTkEntry(frame, width=100)
    start_entry.pack()

    ctk.CTkLabel(frame, text="Maximum Value").pack()
    end_entry = ctk.CTkEntry(frame, width=100)
    end_entry.pack()

    ctk.CTkLabel(frame, text="Rate").pack()
    rate_entry = ctk.CTkEntry(frame, width=100)
    rate_entry.pack()

    button_frame = ctk.CTkFrame(frame)
    button_frame.pack(pady=5)

    ctk.CTkButton(button_frame, text="Save", fg_color="blue",
                  command=lambda: save_range_values(name, start_entry, end_entry, rate_entry, frame)).pack(side="left", padx=5)

    ctk.CTkButton(button_frame, text="Cancel", fg_color="red", command=lambda: frame.pack_forget()).pack(side="left", padx=5)

    return frame

def place_single(name:str, entry):
    val = float(entry.get())
    print(f"name is {name}, entry is {val}")
    SSM.place_single_EngineeringUnits(ch2send=my_channel_entries.getChannelEntry(sigName=name), val_in_eng_units=float(val), time=time.time())

# Create analog outputs with separate dropdowns and input fields
# or whatever element of the row that will need to be updated with value
ao_label_objects = dict() # key:value = "SPT":<label obj>
for name, ch_entry in my_channel_entries.channels.items():
    if ch_entry.sig_type.lower() != "ao" or not ch_entry.showOnGUI:
        continue
    frame = ctk.CTkFrame(scrollable_frame)
    frame.pack(pady=5)
    ctk.CTkLabel(frame, text=f"{name} ({ch_entry.units})").grid(row=0, column=0, padx=5)
    input_value_entry = ctk.CTkEntry(frame, width=100)
    input_value_entry.grid(row=0, column=1, padx=5)
    current_label = ctk.CTkLabel(frame, text="4.00 mA")
    current_label.grid(row=0, column=2, padx=10)
    save_text_button = ctk.CTkButton(frame, text="Save", fg_color="blue", command=lambda n=name, e=input_value_entry, l=current_label: save_input_value(n, e, l))
    save_text_button.grid(row=0, column=3, padx=5)
    dropdown_frame = create_dropdown(scrollable_frame, name)
    arrow_button = ctk.CTkButton(frame, text="⬇", width=20, command=lambda f=dropdown_frame, p=frame: toggle_dropdown(f, p))
    arrow_button.grid(row=0, column=4, padx=5)
    dropdown_frame.pack_forget()

# digital outputs
ctk.CTkLabel(digital_outputs_frame, text="Digital Outputs", font=("Arial", 16)).pack(pady=10)
for name, ch_entry in my_channel_entries.channels.items():

    if ch_entry.sig_type.lower() != "do" or not ch_entry.showOnGUI:
        continue

    motor_status_switch = ctk.CTkSwitch(digital_outputs_frame,  text=ch_entry.name, onvalue="ON", offvalue="OFF")
    motor_status_switch.pack(pady=10)
    motor_status_switch.select()

# Digital Inputs
def toggle_light():
    indicator_light.configure(fg_color="green" if motor_status_switch.get() else "red")

di_label_objects = dict() # key:value = "AOP":<label obj>. Change the fg_color
ctk.CTkLabel(digital_inputs_frame, text="Digital Inputs", font=("Arial", 16)).pack(pady=10)
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


# def process_queue():
#     while not socketRespQueue.empty():
#         sockResp = socketRespQueue.get() # could be a dataEntry or an errorEntry
#         print(f"sockResp (might be echoed by SSM).is {sockResp}")
#         if isinstance(sockResp, dataEntry):
#             if sockResp.gpio_str == "SocketSenderManager is online":
#                 # TODO: online status gui element?
#                 continue
#
#             chEntry = my_channel_entries.get_channelEntry_from_GPIOstr(sockResp.gpio_str)
#             if chEntry is None:
#                 if sockResp.gpio_str == "ack":
#                     print("received ack packet")
#                 continue
#
#             if chEntry.sig_type.lower() == "ai":
#                 meterObj = ai_meter_objects[chEntry.name]
#                 meterObj.set(chEntry.mA_to_EngineeringUnits(sockResp.val)) # move needle on meter
#             elif chEntry.sig_type.lower() == "di":
#                 if int(sockResp.val) == 1:
#                     di_label_objects[chEntry.name].fg_color = "green"
#                 else:
#                     di_label_objects[chEntry.name].fg_color = "red"
#
#         elif isinstance(sockResp, errorEntry):
#             print(f"received error entry: {sockResp}")
#             # pass
#
#     # TODO: finally, place read periodic read requests for ai and di channels
#     for name,meter in ai_meter_objects.items():
#         # only the ch2send name is important. value can be whatever
#         ch = my_channel_entries.getChannelEntry(name)
#         if ch.getGPIOStr() is None:
#             pass # print("invalid gpio config?")
#         else:
#             print(f"channel is {ch}")
#             SSM.place_single_EngineeringUnits(ch2send=ch, val_in_eng_units=3.14, time=time.time())
#     # this di placer has the same problem with unmapped gpios, so I've commented it out until i fix the ai ^^
#     # for name,label_obj in di_label_objects.items():
#     # SSM.place_single_EngineeringUnits(ch2send=my_channel_entries.getChannelEntry(name), val_in_eng_units=0, time=time.time())
#
#     app.after(100, process_queue)  # Check queue again after 100ms
#
# # print("after defined process_queue")
# app.after(0, func=process_queue)
# SSM.startupLoopDelay=0.1
# print(f"for tkinter file: {threading.current_thread()}")
# Run the app
app.mainloop()
