import subprocess
import hashlib
import os
import tkinter as tk
from tkinter import simpledialog, messagebox

# --- SECRET PASSWORD (MUST MATCH KEYGEN) ---
SECRET_SALT = "CardioFlow_Secret_2025_Nagpur_Key" 

def get_machine_id():
    """ Gets the unique Motherboard UUID and Cleans it """
    try:
        cmd = 'wmic csproduct get uuid'
        # Get raw output
        raw_output = subprocess.check_output(cmd).decode()
        # Split by line and take the second line (the actual UUID)
        lines = raw_output.split('\n')
        if len(lines) > 1:
            uuid = lines[1].strip()
            # CRITICAL: Remove all spaces and force Uppercase
            clean_uuid = uuid.replace(" ", "").upper()
            return clean_uuid
        return "UNKNOWN_ID"
    except:
        return "UNKNOWN_ID"

def generate_key_for_machine(machine_id):
    """ Generates the Unlock Code """
    # Ensure the input ID is also clean
    clean_id = machine_id.strip().upper().replace(" ", "")
    
    raw_string = clean_id + SECRET_SALT
    return hashlib.sha256(raw_string.encode()).hexdigest()[:16].upper()

def check_license(root_window):
    machine_id = get_machine_id()
    expected_key = generate_key_for_machine(machine_id)
    license_file = "license.key"
    
    # 1. Check existing
    if os.path.exists(license_file):
        with open(license_file, "r") as f:
            saved_key = f.read().strip()
            if saved_key == expected_key:
                return True 
    
    # 2. ASK FOR KEY (Custom Dialog to allow Copy-Paste)
    root_window.withdraw() # Hide main app
    
    # Create a custom popup window
    dialog = tk.Toplevel(root_window)
    dialog.title("Activation Required")
    dialog.geometry("400x250")
    dialog.attributes('-topmost', True) # Keep on top
    
    tk.Label(dialog, text="Hardware ID (Copy this):", font=("Arial", 10)).pack(pady=10)
    
    # Read-only Entry for ID (So you can copy it)
    entry_id = tk.Entry(dialog, width=40, font=("Arial", 10, "bold"))
    entry_id.insert(0, machine_id)
    entry_id.configure(state='readonly')
    entry_id.pack(pady=5)
    
    tk.Label(dialog, text="Enter Activation Key:", font=("Arial", 10)).pack(pady=10)
    entry_key = tk.Entry(dialog, width=40)
    entry_key.pack(pady=5)
    
    # Result Variable
    result = {"success": False}

    def on_submit():
        user_key = entry_key.get().strip().upper()
        if user_key == expected_key:
            with open(license_file, "w") as f:
                f.write(expected_key)
            messagebox.showinfo("Success", "Software Activated!")
            result["success"] = True
            dialog.destroy()
        else:
            messagebox.showerror("Error", "Invalid Key!")

    tk.Button(dialog, text="Activate", command=on_submit, bg="#008000", fg="white", width=20).pack(pady=20)
    
    # Handle Window Close (X button)
    def on_close():
        dialog.destroy()
    dialog.protocol("WM_DELETE_WINDOW", on_close)
    
    root_window.wait_window(dialog) # Wait here until dialog closes
    
    if result["success"]:
        root_window.deiconify() # Show main app
        return True
    return False