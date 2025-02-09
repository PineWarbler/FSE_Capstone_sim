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

# Analog Inputs
ctk.CTkLabel(analog_inputs_frame, text="Analog Inputs", font=("Arial", 16)).pack(pady=10)

# Analog Outputs
ctk.CTkLabel(analog_outputs_frame, text="Analog Outputs", font=("Arial", 16)).pack(pady=10)

UVT Gauge
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
saved_values = {}


def toggle_dropdown(frame):
    if frame.winfo_ismapped():
        frame.pack_forget()
    else:
        frame.pack(pady=5)

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
        current_label.configure(text=f"Current Input: {scaled_current:.2f} mA")
    else:
        current_label.configure(text="Current Input: 4.00 mA")

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

# Create analog outputs with separate dropdowns and input fields
units = {"DPT": "PSI", "SPT": "PSI", "MAT": "°C","OPT":"PSI"}
for label in ["DPT", "SPT", "MAT","OPT"]:
    frame = ctk.CTkFrame(analog_outputs_frame)
    frame.pack(pady=5)

    ctk.CTkLabel(frame, text=f"{label} ({units[label]})").grid(row=0, column=0, padx=5)
    input_value_entry = ctk.CTkEntry(frame, width=100)
    input_value_entry.grid(row=0, column=1, padx=5)

    current_label = ctk.CTkLabel(frame, text="Current Input: 4.00 mA")
    current_label.grid(row=0, column=2, padx=10)

    save_text_button = ctk.CTkButton(frame, text="Save", fg_color="blue",
                                     command=lambda n=label, e=input_value_entry, l=current_label: save_input_value(n, e, l))
    save_text_button.grid(row=0, column=3, padx=5)

    dropdown_frame = create_dropdown(analog_outputs_frame, label)
    arrow_button = ctk.CTkButton(frame, text="⬇", width=20, command=lambda f=dropdown_frame: toggle_dropdown(f))
    arrow_button.grid(row=0, column=4, padx=5)


ctk.CTkLabel(digital_outputs_frame, text="Digital Outputs", font=("Arial", 16)).pack(pady=10)
motor_status_switch = ctk.CTkSwitch(digital_outputs_frame, text="Motor Status", onvalue="ON", offvalue="OFF")
motor_status_switch.pack(pady=10)
motor_status_switch.select()
ctk.CTkLabel(digital_inputs_frame, text="Digital Inputs", font=("Arial", 16)).pack(pady=10)

def toggle_light():
    indicator_light.configure(fg_color="green" if motor_status_switch.get() else "red")

indicator_frame = ctk.CTkFrame(digital_inputs_frame)
indicator_frame.pack(pady=10)
indicator_label = ctk.CTkLabel(indicator_frame, text="AOT")
indicator_label.pack(side="left", padx=10)
indicator_light = ctk.CTkLabel(indicator_frame, text="", width=20, height=20, corner_radius=10, fg_color="red")
indicator_light.pack(side="left")
# Run the app
app.mainloop()

# Run the app
app.mainloop()

