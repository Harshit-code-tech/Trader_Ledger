"""
Profile picker dialog utilities for import/export operations.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional
from core.db_operations import get_active_profiles
from core.logger import get_logger

logger = get_logger('ui.profile_picker')


def pick_export_profiles(parent: tk.Widget) -> Optional[list[tuple[int, str]]]:
    """
    Show a dialog to let the user pick which profiles to export.

    Returns:
        list of (profile_id, profile_name) tuples if user confirms,
        None if user cancels.
    """
    profiles = get_active_profiles()
    if not profiles:
        return None

    # If only one profile exists, return it directly — no dialog needed
    if len(profiles) == 1:
        return profiles

    result: list[tuple[int, str]] = []
    dialog = tk.Toplevel(parent)
    dialog.title("Select Profiles to Export")
    dialog.geometry("360x400")
    dialog.resizable(False, True)
    dialog.transient(parent)
    dialog.grab_set()

    ttk.Label(
        dialog,
        text="Select which profiles to export:",
        font=('Consolas', 11, 'bold')
    ).pack(padx=20, pady=(20, 10), anchor='w')

    # Checkbutton variables
    vars_map: dict[int, tk.BooleanVar] = {}
    frame = ttk.Frame(dialog)
    frame.pack(fill='both', expand=True, padx=20)

    for profile_id, profile_name in profiles:
        var = tk.BooleanVar(value=True)
        vars_map[profile_id] = var
        cb = ttk.Checkbutton(
            frame,
            text=profile_name,
            variable=var,
            style='TCheckbutton'
        )
        cb.pack(anchor='w', pady=4)

    # Select All / Deselect All
    btn_frame_top = ttk.Frame(dialog)
    btn_frame_top.pack(padx=20, pady=(5, 0), fill='x')

    def select_all():
        for v in vars_map.values():
            v.set(True)

    def deselect_all():
        for v in vars_map.values():
            v.set(False)

    ttk.Button(btn_frame_top, text="Select All", command=select_all).pack(side='left', padx=(0, 5))
    ttk.Button(btn_frame_top, text="Deselect All", command=deselect_all).pack(side='left')

    # OK / Cancel
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(padx=20, pady=20, fill='x')

    def on_ok():
        nonlocal result
        for profile_id, profile_name in profiles:
            if vars_map[profile_id].get():
                result.append((profile_id, profile_name))
        dialog.destroy()

    def on_cancel():
        nonlocal result
        result = []  # empty means cancelled
        dialog.destroy()

    ttk.Button(btn_frame, text="Export", command=on_ok).pack(side='right', padx=(5, 0))
    ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side='right')

    dialog.protocol("WM_DELETE_WINDOW", on_cancel)
    dialog.wait_window()

    return result if result else None


def pick_import_profile(parent: tk.Widget) -> Optional[tuple[int, str]]:
    """
    Show a dialog to let the user pick a single target profile for import.

    Returns:
        (profile_id, profile_name) if user confirms,
        None if user cancels.
    """
    profiles = get_active_profiles()
    if not profiles:
        return None

    # If only one profile, return it directly
    if len(profiles) == 1:
        return profiles[0]

    result: Optional[tuple[int, str]] = None
    dialog = tk.Toplevel(parent)
    dialog.title("Select Target Profile")
    dialog.geometry("320x220")
    dialog.resizable(False, False)
    dialog.transient(parent)
    dialog.grab_set()

    ttk.Label(
        dialog,
        text="Import trades into which profile?",
        font=('Consolas', 11, 'bold')
    ).pack(padx=20, pady=(20, 10), anchor='w')

    profile_var = tk.StringVar()
    profile_names = [name for _, name in profiles]
    profile_var.set(profile_names[0])

    combo = ttk.Combobox(
        dialog,
        textvariable=profile_var,
        values=profile_names,
        state='readonly',
        font=('Consolas', 10),
        width=25
    )
    combo.pack(padx=20, pady=10)

    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(padx=20, pady=20, fill='x')

    def on_ok():
        nonlocal result
        selected_name = profile_var.get()
        for pid, pname in profiles:
            if pname == selected_name:
                result = (pid, pname)
                break
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    ttk.Button(btn_frame, text="Import", command=on_ok).pack(side='right', padx=(5, 0))
    ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side='right')

    dialog.protocol("WM_DELETE_WINDOW", on_cancel)
    dialog.wait_window()

    return result
