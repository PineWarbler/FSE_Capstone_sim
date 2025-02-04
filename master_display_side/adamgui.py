import customtkinter as ctk
from tkdial import Meter

# Configure the main application window
app = ctk.CTk()
app.title("ICS Phase I - Beta")
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

# Analog Outputs
ctk.CTkLabel(analog_outputs_frame, text="Analog Outputs", font=("Arial", 16)).pack(pady=10)

# DPT
dpt_frame = ctk.CTkFrame(analog_outputs_frame)
dpt_frame.pack(pady=5)
ctk.CTkLabel(dpt_frame, text="DPT").grid(row=0, column=0, padx=5)
dpt_entry = ctk.CTkEntry(dpt_frame, width=100)
dpt_entry.grid(row=0, column=1, padx=5)
dpt_send_button = ctk.CTkButton(dpt_frame, text="send", width=40, fg_color="green")
dpt_send_button.grid(row=0, column=2, padx=5)
ctk.CTkLabel(dpt_frame, text="last sent:").grid(row=1, column=2, pady=5)

# SPT
spt_frame = ctk.CTkFrame(analog_outputs_frame)
spt_frame.pack(pady=5)
ctk.CTkLabel(spt_frame, text="SPT").grid(row=0, column=0, padx=5)
spt_entry = ctk.CTkEntry(spt_frame, width=100)
spt_entry.grid(row=0, column=1, padx=5)
spt_send_button = ctk.CTkButton(spt_frame, text="send", width=40, fg_color="green")
spt_send_button.grid(row=0, column=2, padx=5)
ctk.CTkLabel(spt_frame, text="last sent:").grid(row=1, column=2, pady=5)

# MAT
mat_frame = ctk.CTkFrame(analog_outputs_frame)
mat_frame.pack(pady=5)
ctk.CTkLabel(mat_frame, text="MAT").grid(row=0, column=0, padx=5)
mat_entry = ctk.CTkEntry(mat_frame, width=100)
mat_entry.grid(row=0, column=1, padx=5)
mat_send_button = ctk.CTkButton(mat_frame, text="send", width=40, fg_color="green")
mat_send_button.grid(row=0, column=2, padx=5)
ctk.CTkLabel(mat_frame, text="last sent:").grid(row=1, column=2, pady=5)

# Analog Inputs
ctk.CTkLabel(analog_inputs_frame, text="Analog Inputs", font=("Arial", 16)).pack(pady=10)

# UVT Gauge
uvt_frame = ctk.CTkFrame(analog_inputs_frame)
uvt_frame.pack(pady=5)
uvt_gauge = Meter(uvt_frame, scroll_steps=0, interactive=False, radius=100)
uvt_gauge.set(50)
uvt_gauge.pack()
ctk.CTkLabel(uvt_frame, text="UVT").pack()

# IVT Gauge
ivt_frame = ctk.CTkFrame(analog_inputs_frame)
ivt_frame.pack(pady=5)
ivt_gauge = Meter(ivt_frame, scroll_steps=0, interactive=False, radius=100)
ivt_gauge.set(50)
ivt_gauge.pack()
ctk.CTkLabel(ivt_frame, text="IVT").pack()

# Digital Outputs
ctk.CTkLabel(digital_outputs_frame, text="Digital Outputs", font=("Arial", 16)).pack(pady=10)

motor_status_switch = ctk.CTkSwitch(digital_outputs_frame, text="Motor Status", onvalue="ON", offvalue="OFF")
motor_status_switch.pack(pady=10)
motor_status_switch.select()

# Digital Inputs
ctk.CTkLabel(digital_inputs_frame, text="Digital Inputs", font=("Arial", 16)).pack(pady=10)

def toggle_light():
    indicator_light.configure(fg_color="green" if motor_status_switch.get() else "red")

indicator_frame = ctk.CTkFrame(digital_inputs_frame)
indicator_frame.pack(pady=10)
indicator_label = ctk.CTkLabel(indicator_frame, text="Indicator Light")
indicator_label.pack(side="left", padx=10)
indicator_light = ctk.CTkLabel(indicator_frame, text="", width=20, height=20, corner_radius=10, fg_color="red")
indicator_light.pack(side="left")
motor_status_switch.configure(command=toggle_light)

# Run the app
app.mainloop()

