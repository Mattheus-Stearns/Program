import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime, timedelta
import os
import shutil
import sys
import subprocess

# Import your scheduling logic
from camp_scheduler.scheduler import ProgramSchedules

# ---- Helper Functions ----

def get_next_monday(today=None):
    today = today or datetime.today()
    days_ahead = (7 - today.weekday()) % 7
    days_ahead = 7 if days_ahead == 0 else days_ahead
    return (today + timedelta(days=days_ahead)).strftime("%d/%m/%Y")

def refresh_file_list():
    file_listbox.delete(0, tk.END)
    output_dir = os.path.join(os.getcwd(), "Output")
    os.makedirs(output_dir, exist_ok=True)
    files = sorted(os.listdir(output_dir))
    if not files:
        file_listbox.insert(tk.END, "(no files in /Output/)")
    else:
        for f in files:
            file_listbox.insert(tk.END, f)

def import_files():
    file_paths = filedialog.askopenfilenames(
        title="Select CSV Files to Import",
        filetypes=[("CSV files", "*.csv")]
    )
    if file_paths:
        dest_dir = os.path.join(os.getcwd(), "camp_scheduler/data")
        os.makedirs(dest_dir, exist_ok=True)
        for path in file_paths:
            if path.lower().endswith(".csv"):
                dest_path = os.path.join(dest_dir, os.path.basename(path))
                shutil.copy(path, dest_path)
        messagebox.showinfo("Success", f"Imported {len(file_paths)} file(s) to /data/")
        refresh_file_list()

def run_command(command):
    week_start = week_start_var.get().strip()
    try:
        if week_start:
            datetime.strptime(week_start, "%d/%m/%Y")
        else:
            week_start = get_next_monday()
    except ValueError:
        messagebox.showerror("Invalid Date", "Please use DD/MM/YYYY format.")
        return

    scheduler = ProgramSchedules(week_start)

    try:
        if command == "run-full-schedule":
            scheduler.run_full_schedule()
        elif command == "assign-off-times":
            scheduler.assign_off_times()
            scheduler.clean_output_files()
        elif command == "assign-freetime-locations":
            scheduler.assign_freetime_locations()
            scheduler.clean_output_files()
        elif command == "generate-coverage-schedule":
            scheduler.generate_coverage_schedule()
            scheduler.clean_output_files()
        elif command == "assign-skills-classes":
            scheduler.assign_skills_classes()
            scheduler.clean_output_files()
        elif command == "assign-campers-to-skills":
            scheduler.assign_campers_to_skills()
            scheduler.clean_output_files()
        else:
            messagebox.showwarning("Unknown Command", f"Unknown command: {command}")
            return

        messagebox.showinfo("Success", f"Command '{command}' executed successfully!")
        refresh_file_list()

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")

# ---- GUI Setup ----

root = tk.Tk()
root.title("Abnaki Program Scheduler")

# Week Start Input
tk.Label(root, text="Week Start (DD/MM/YYYY):").grid(row=0, column=0, padx=10, pady=5, sticky="w")
week_start_var = tk.StringVar(value=get_next_monday())
tk.Entry(root, textvariable=week_start_var, width=20).grid(row=0, column=1, padx=10, pady=5, sticky="w")

# Command Buttons
commands = [
    ("Run Full Schedule", "run-full-schedule"),
    ("Assign Off Times", "assign-off-times"),
    ("Assign Freetime Locations", "assign-freetime-locations"),
    ("Generate Coverage Schedule", "generate-coverage-schedule"),
    ("Assign Skills Classes", "assign-skills-classes"),
    ("Assign Campers to Skills", "assign-campers-to-skills"),
]

for i, (label, cmd) in enumerate(commands, start=1):
    tk.Button(root, text=label, width=30, command=lambda c=cmd: run_command(c)).grid(
        row=i, column=0, columnspan=2, padx=10, pady=2
    )

# Import File Button
tk.Button(root, text="Import CSV File(s) to /data/", command=import_files, width=30).grid(
    row=len(commands)+1, column=0, columnspan=2, pady=10
)

# File List Display
tk.Label(root, text="Output Folders:").grid(row=len(commands)+2, column=0, columnspan=2, sticky="w", padx=10)
file_listbox = tk.Listbox(root, width=50, height=10)
file_listbox.grid(row=len(commands)+3, column=0, columnspan=2, padx=10, pady=5)

def open_selected_file(event):
    selection = file_listbox.curselection()
    if not selection:
        return
    filename = file_listbox.get(selection[0])
    if filename == "(no files in /Output/)":
        return
    filepath = os.path.join(os.getcwd(), "Output", filename)
    if not os.path.exists(filepath):
        messagebox.showerror("File Not Found", f"File does not exist:\n{filepath}")
        return

    try:
        if sys.platform == "win32":
            os.startfile(filepath)
        elif sys.platform == "darwin":
            subprocess.run(["open", filepath])
        else:
            subprocess.run(["xdg-open", filepath])
    except Exception as e:
        messagebox.showerror("Error", f"Could not open file:\n{e}")

# Bind double-click event
file_listbox.bind("<Double-Button-1>", open_selected_file)

refresh_file_list()
root.mainloop()