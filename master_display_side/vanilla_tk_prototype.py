# -*- coding: utf-8 -*-
"""
Created on Sun Nov  3 15:02:49 2024

@author: REYNOLDSPG21
"""

import tkinter as tk
from tkinter import *
from tkinter import ttk
from tkinter.ttk import *
from tkinter import PhotoImage
from tkdial import Dial, Meter

class analogOutputWidget(ttk.Frame):
    def __init__(self, parent, label_text, lastVal, entry_var, labelFont=('calibre',26,'normal')):
        super().__init__(master = parent)
        self._last_val = tk.StringVar()
        self.entry_var = entry_var
        # self.entry_var.trace('w', self.setLast)
        
        
        self.rowconfigure((0,1), weight=1)
        self.columnconfigure((0,1,2), weight=1)
        
        # self.entry_var.trace('w', self.create_greeting_message)
        
        ttk.Label(self, text=label_text, font=labelFont).grid(row = 0, column = 0, sticky="e")
        ttk.Entry(self, textvariable = entry_var, font=labelFont, justify="right").grid(row = 0, column=1, sticky="w", padx=40)
        
        tk.Button(self, text="send", background="lightgreen", font=labelFont, command=self.setLast).grid(row=0, column=2, sticky="w")
        tk.Label(self, text=f"last sent: {self._last_val.get()}", font=labelFont).grid(row=1, column=2)
        
        # self.pack(expand=True, fill='both')
        # self.pack()
        
    def setLast(self):
        # self._last_val = self.entry_var
        print("being called!")
        self._last_val.set(self.entry_var.get())
        print(self._last_val.get())
        
class digitalOutputWidget(ttk.Frame):
    def __init__(self, parent, label_text, labelFont=('calibre',26,'normal')):
        super().__init__(master = parent)
        self.rowconfigure((0,1), weight=1)
        self.columnconfigure(0, weight=1)

        # there's no way to resize a checkbutton, so will have to use a button image instead
        p = PhotoImage(file="toggle_on.png")
        b = tk.Button(self, image=p, relief=None)
        b.grid(row=0, column=0)
        b.image = p # need to retain a reference. see https://stackoverflow.com/a/22200607
        
        tk.Label(self, text=label_text, font=labelFont).grid(row=0, column=1, padx=20)


class analogInputWidget(ttk.Frame):
    def __init__(self, parent, label_text, labelFont=('calibre',26,'normal')):
        super().__init__(master = parent)
        self.rowconfigure((0,1,2), weight=1)
        self.columnconfigure(0, weight=1)

        dial = Meter(self, scroll_steps=0, interactive=False, radius = 200)
        dial.set(50)
        dial.grid(row=0, column=0, padx=50)
        
        tk.Label(self, text=label_text, font=labelFont).grid(row=1, column=0, pady=20)
        
# Create the main window
window = tk.Tk()
# window.configure(bg="white")

TitleFont = ('calibre',30,'normal')
labelFont = ('calibre',20,'normal')
infoFont = ('calibre',20,'italic')

window.title("ICS Phase I - Beta")


ai_frame = tk.Frame(window, width=400, height = 200, borderwidth = 5, relief = tk.GROOVE) # sub-frame for analog input stuff

ao_frame = tk.Frame(window, width=400, height = 200, borderwidth = 5,relief = tk.GROOVE)
di_frame = tk.Frame(window, width=400, height = 200, borderwidth = 5,relief = tk.GROOVE)
do_frame = tk.Frame(window, width=400, height = 200, borderwidth = 5,relief = tk.GROOVE)

# split window into quadrants
window.columnconfigure((0,1), weight=1)
window.rowconfigure((0,1), weight=1)

# place frames into quadrants of parent window
ao_frame.grid(row=0,column=0, sticky="ns")
ai_frame.grid(row=0,column=1, sticky="ns")
do_frame.grid(row=1,column=0, sticky="ns")
di_frame.grid(row=1,column=1, sticky="ns")


DPT_last = 90.0
DPT_entry_val = tk.StringVar() # no float var exists, so will have to convert downstream
SPT_last = 51.2
SPT_entry_val = tk.StringVar()
MAT_last = 12.3
MAT_entry_val = tk.StringVar()


# analog output quadrant
ao_frame.columnconfigure(0, weight=1)
ao_frame.rowconfigure((0,1,2), weight=1)
tk.Label(ao_frame, text="Analog Outputs", font=TitleFont).grid(row=0, column=0)
analogOutputWidget(ao_frame, "DPT", DPT_last, DPT_entry_val).grid(row=1, column=0)
analogOutputWidget(ao_frame, "SPT", SPT_last, SPT_entry_val).grid(row=2, column=0)
analogOutputWidget(ao_frame, "MAT", MAT_last, MAT_entry_val).grid(row=3, column=0)

# digital output quadrant
do_frame.columnconfigure(0, weight=1)
do_frame.rowconfigure((0,1), weight=1)
tk.Label(do_frame, text="Digital Outputs", font=TitleFont).grid(row=0, column=0)
digitalOutputWidget(do_frame, "Motor Status").grid(row=1, column=0)

# analog input quadrant
ai_frame.columnconfigure((0,1), weight=1)
ai_frame.rowconfigure((0,1), weight=1)
tk.Label(ai_frame, text="Analog Inputs", font=TitleFont).grid(row=0, column=0, columnspan=2, sticky="n")
analogInputWidget(ai_frame, "UVT").grid(row=1, column=0)
analogInputWidget(ai_frame, "IVT").grid(row=1, column=1)

# digital input quadrant
di_frame.columnconfigure(0, weight=1)
di_frame.rowconfigure((0,1), weight=1)
tk.Label(di_frame, text="Digital Inputs", font=TitleFont).grid(row=0, column=0)
tk.Label(di_frame, text="<None for Phase I>", font=infoFont).grid(row=1, column=0)


# Run the main loop
window.mainloop()
