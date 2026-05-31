"""
Main Window - Trader Ledger Application

Creates the main window with notebook tabs.
Phase 1: Only Add Trade tab is functional.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
from ui.add_trade_tab import AddTradeTab
from ui.view_records_tab import ViewRecordsTab
from ui.reports_tab import ReportsTab
from ui.trade_view_tab import TradeViewTab
from core.logger import get_logger
import config

logger = get_logger('ui.main_window')


class TraderLedgerApp:
    """Main application window with tabbed interface."""
    
    def __init__(self, root: tk.Tk) -> None:
        logger.info("Initializing main window")
        self.root = root
        self.root.title("📊 Trader Ledger - Baba's Trading App")
        self.root.geometry("900x650")
        
        # Set minimum window size
        self.root.minsize(800, 600)
        logger.debug("Window size set: 900x650, minimum: 800x600")
        
        # Status bar at bottom (create before tabs so callbacks work)
        self.status_message_var = tk.StringVar(value="Ready")
        self.profile_status_var = tk.StringVar(value="Profile: (not selected)")

        status_frame = ttk.Frame(self.root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_bar = ttk.Label(status_frame, textvariable=self.status_message_var, relief=tk.SUNKEN, anchor=tk.W, font=('Arial', 9))
        self.status_bar.pack(side=tk.LEFT, fill='x', expand=True)

        self.status_profile_label = ttk.Label(status_frame, textvariable=self.profile_status_var, relief=tk.SUNKEN, anchor=tk.E, font=('Arial', 9))
        self.status_profile_label.pack(side=tk.RIGHT)
        
        # Current profile (set by profile selector)
        self.current_profile_id: int | None = None
        self.current_profile_name: str | None = None

        # Attempt to load last-selected profile; if not present, show selector
        try:
            state_path = config.PROFILE_STATE_FILE
            if state_path.exists():
                text = state_path.read_text(encoding='utf-8')
                data = json.loads(text)
                pid = data.get('id')
                pname = data.get('name')
                if pid is not None:
                    config.CURRENT_PROFILE_ID = pid
                    config.CURRENT_PROFILE_NAME = pname
                    self.current_profile_id = pid
                    self.current_profile_name = pname
                    # Update UI
                    self.root.title(f"📊 Trader Ledger - {pname}")
                    self.profile_status_var.set(f"Profile: {pname}")
                else:
                    self.show_profile_selector()
            else:
                self.show_profile_selector()
        except Exception:
            self.show_profile_selector()

        # Create notebook (tabs)
        self.toolbar = ttk.Frame(self.root)
        self.toolbar.pack(fill='x', padx=10, pady=(10, 0))

        self.walkthrough_button = ttk.Button(
            self.toolbar,
            text="Walkthrough",
            command=self.show_walkthrough,
            width=14
        )
        self.walkthrough_button.pack(side='right')

        self.profile_button = ttk.Button(
            self.toolbar,
            text="Profile",
            command=self.show_profile_selector,
            width=12
        )
        self.profile_button.pack(side='right', padx=(8, 0))

        # (Profile indicator now in persistent status bar)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Bind tab selection event
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # Create tabs
        self.create_tabs()
        self.root.after(400, self.show_onboarding_if_needed)
        logger.info("Main window initialized successfully")

    def show_profile_selector(self) -> None:
        """Modal dialog to select or create a profile at startup."""
        try:
            import sqlite3
            import config

            # Modal dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Select Profile")
            dialog.grab_set()
            dialog.resizable(True, True)
            dialog.geometry("620x360")
            dialog.minsize(520, 320)
            dialog.lift()
            dialog.focus_force()

            ttk.Label(dialog, text="Select Profile to use for this session", font=('Consolas', 12, 'bold')).pack(pady=(12, 6))

            list_frame = ttk.Frame(dialog)
            list_frame.pack(fill='both', expand=True, padx=12, pady=6)

            profiles_listbox = tk.Listbox(list_frame, height=8)
            profiles_listbox.pack(side='left', fill='both', expand=True)
            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=profiles_listbox.yview)
            scrollbar.pack(side='right', fill='y')
            profiles_listbox.config(yscrollcommand=scrollbar.set)

            def load_profiles():
                profiles_listbox.delete(0, tk.END)
                try:
                    conn = sqlite3.connect(str(config.DB_PATH))
                    cur = conn.cursor()
                    cur.execute("SELECT id, profile_name FROM profiles WHERE is_active = 1 ORDER BY profile_name")
                    rows = cur.fetchall()
                    conn.close()
                    for r in rows:
                        profiles_listbox.insert(tk.END, f"{r[0]}: {r[1]}")
                except Exception:
                    profiles_listbox.insert(tk.END, "1: Baba")

            load_profiles()

            def select_profile():
                sel = profiles_listbox.curselection()
                if not sel:
                    messagebox.showwarning("No selection", "Please select a profile or create a new one.")
                    return
                text = profiles_listbox.get(sel[0])
                pid_str, pname = text.split(':', 1)
                pid = int(pid_str.strip())
                pname = pname.strip()
                self._apply_profile_selection(pid, pname, f"📊 Trader Ledger - {pname}")
                dialog.grab_release()
                dialog.destroy()

            def select_combined():
                self._apply_profile_selection(0, "Combined Family", "📊 Trader Ledger - Combined Family View")
                dialog.grab_release()
                dialog.destroy()

            def add_profile_flow():
                def create_profile():
                    name = name_entry.get().strip()
                    if not name:
                        messagebox.showwarning("Invalid", "Profile name required")
                        return
                    try:
                        conn = sqlite3.connect(str(config.DB_PATH))
                        cur = conn.cursor()
                        cur.execute("INSERT INTO profiles (profile_name, is_active) VALUES (?, 1)", (name,))
                        conn.commit()
                        conn.close()
                        load_profiles()
                        add_dialog.destroy()
                    except Exception as exc:
                        messagebox.showerror("Error", f"Could not create profile: {exc}")

                add_dialog = tk.Toplevel(dialog)
                add_dialog.transient(dialog)
                add_dialog.grab_set()
                add_dialog.title("Add Profile")
                ttk.Label(add_dialog, text="Profile name:").pack(padx=12, pady=(12, 4))
                name_entry = ttk.Entry(add_dialog, width=30)
                name_entry.pack(padx=12, pady=(0, 12))
                ttk.Button(add_dialog, text="Create", command=create_profile).pack(pady=(0, 12))

            # Buttons
            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(pady=8)
            ttk.Button(btn_frame, text="Select", command=select_profile, width=12).pack(side='left', padx=6)
            ttk.Button(btn_frame, text="Add New Profile", command=add_profile_flow, width=16).pack(side='left', padx=6)
            ttk.Button(btn_frame, text="Edit", command=lambda: edit_profile(), width=10).pack(side='left', padx=6)
            ttk.Button(btn_frame, text="Delete", command=lambda: delete_profile(), width=10).pack(side='left', padx=6)
            ttk.Button(btn_frame, text="Combined Family View", command=select_combined, width=22).pack(side='left', padx=6)

            def edit_profile():
                sel = profiles_listbox.curselection()
                if not sel:
                    messagebox.showwarning("No selection", "Please select a profile to edit.")
                    return
                text = profiles_listbox.get(sel[0])
                pid_str, pname = text.split(':', 1)
                pid = int(pid_str.strip())
                pname = pname.strip()

                def do_update():
                    new_name = edit_entry.get().strip()
                    if not new_name:
                        messagebox.showwarning("Invalid", "Profile name required")
                        return
                    try:
                        conn = sqlite3.connect(str(config.DB_PATH))
                        cur = conn.cursor()
                        cur.execute("UPDATE profiles SET profile_name = ? WHERE id = ?", (new_name, pid))
                        conn.commit()
                        conn.close()
                        load_profiles()
                        edit_dialog.destroy()
                        # If editing current selected profile, update persisted state and UI
                        if self.current_profile_id == pid:
                            try:
                                state_path = config.PROFILE_STATE_FILE
                                state_path.write_text(json.dumps({"id": pid, "name": new_name}), encoding='utf-8')
                                self.profile_status_var.set(f"Profile: {new_name}")
                                self.root.title(f"📊 Trader Ledger - {new_name}")
                            except Exception:
                                pass
                    except Exception as exc:
                        messagebox.showerror("Error", f"Could not rename profile: {exc}")

                edit_dialog = tk.Toplevel(dialog)
                edit_dialog.transient(dialog)
                edit_dialog.grab_set()
                edit_dialog.title("Edit Profile")
                ttk.Label(edit_dialog, text="Profile name:").pack(padx=12, pady=(12, 4))
                edit_entry = ttk.Entry(edit_dialog, width=30)
                edit_entry.insert(0, pname)
                edit_entry.pack(padx=12, pady=(0, 12))
                ttk.Button(edit_dialog, text="Save", command=do_update).pack(pady=(0, 12))

            def delete_profile():
                sel = profiles_listbox.curselection()
                if not sel:
                    messagebox.showwarning("No selection", "Please select a profile to delete.")
                    return
                text = profiles_listbox.get(sel[0])
                pid_str, pname = text.split(':', 1)
                pid = int(pid_str.strip())
                pname = pname.strip()
                if messagebox.askyesno("Confirm Delete", f"Disable profile '{pname}'? This will hide it from selectors."):
                    try:
                        conn = sqlite3.connect(str(config.DB_PATH))
                        cur = conn.cursor()
                        cur.execute("UPDATE profiles SET is_active = 0 WHERE id = ?", (pid,))
                        conn.commit()
                        conn.close()
                        load_profiles()
                        # If deleting current profile, clear persisted state
                        if self.current_profile_id == pid:
                            try:
                                state_path = config.PROFILE_STATE_FILE
                                if state_path.exists():
                                    state_path.unlink()
                            except Exception:
                                pass
                            config.CURRENT_PROFILE_ID = None
                            config.CURRENT_PROFILE_NAME = None
                            self.current_profile_id = None
                            self.current_profile_name = None
                            self.profile_status_var.set("Profile: (not selected)")
                    except Exception as exc:
                        messagebox.showerror("Error", f"Could not delete profile: {exc}")

            def close_dialog() -> None:
                if self.current_profile_id is None:
                    messagebox.showwarning("Profile Required", "Please select a profile to continue.")
                    return
                dialog.grab_release()
                dialog.destroy()

            dialog.protocol("WM_DELETE_WINDOW", close_dialog)
            self.root.wait_window(dialog)
        except Exception as exc:
            logger.error(f"Profile selector failed: {exc}", exc_info=True)

    def _apply_profile_selection(self, profile_id: int, profile_name: str, title: str) -> None:
        config.CURRENT_PROFILE_ID = profile_id
        config.CURRENT_PROFILE_NAME = profile_name
        self.current_profile_id = profile_id
        self.current_profile_name = profile_name
        self.root.title(title)
        try:
            self.profile_status_var.set(f"Profile: {profile_name}")
        except Exception:
            pass
        try:
            state_path = config.PROFILE_STATE_FILE
            state_path.write_text(json.dumps({"id": profile_id, "name": profile_name}), encoding='utf-8')
        except Exception:
            pass
        self._refresh_after_profile_change()

    def _refresh_after_profile_change(self) -> None:
        if hasattr(self, 'add_trade_tab'):
            self.add_trade_tab.load_equity_dropdown()
            self.add_trade_tab.refresh_recent_trades()
            self.add_trade_tab.update_sell_reference_fields()
        if hasattr(self, 'view_records_tab'):
            self.view_records_tab.refresh_records()
        if hasattr(self, 'trade_view_tab'):
            self.trade_view_tab.refresh_units()
        if hasattr(self, 'reports_tab') and hasattr(self, 'notebook'):
            try:
                current_index = self.notebook.index(self.notebook.select())
                if current_index == 2:
                    self.reports_tab.calculate_reports()
            except Exception as exc:
                logger.warning(f"Failed to refresh reports after profile change: {exc}", exc_info=True)

        display_name = self.current_profile_name or "(not selected)"
        self.update_status(f"Profile updated: {display_name}")
    
    def create_tabs(self) -> None:
        """Create all tabs. Phase 3: All tabs functional."""
        
        # Tab 1: Add Trade (Phase 1 - functional)
        add_trade_frame = ttk.Frame(self.notebook)
        self.notebook.add(add_trade_frame, text="  Add Trade  ")
        self.add_trade_tab = AddTradeTab(add_trade_frame, self.update_status)
        
        # Tab 2: View Records (Phase 2 - functional)
        view_records_frame = ttk.Frame(self.notebook)
        self.notebook.add(view_records_frame, text="  View Records  ")
        self.view_records_tab = ViewRecordsTab(view_records_frame, self.update_status)
        
        # Tab 3: Reports (Phase 3 - functional)
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text="  Reports  ")
        self.reports_tab = ReportsTab(reports_frame, self.update_status)

        # Tab 4: Trade View (Grouped trade units)
        trade_view_frame = ttk.Frame(self.notebook)
        self.notebook.add(trade_view_frame, text="  Trade View  ")
        self.trade_view_tab = TradeViewTab(trade_view_frame, self.update_status)
    
    def on_tab_changed(self, event: tk.Event) -> None:  # type: ignore
        """Handle tab selection changes."""
        selected_tab = self.notebook.select()
        tab_index = self.notebook.index(selected_tab)
        
        # If Reports tab is selected, trigger recalculation
        if tab_index == 2:  # Reports is the 3rd tab (index 2)
            logger.debug("Reports tab selected - triggering recalculation")
            self.reports_tab.on_tab_selected()
        if tab_index == 3:  # Trade View
            logger.debug("Trade View tab selected - refreshing units")
            self.trade_view_tab.refresh_units()
    
    def update_status(self, message: str) -> None:
        """Update status bar message."""
        logger.debug(f"Status update: {message}")
        self.status_message_var.set(message)
        self.root.update_idletasks()

    def show_onboarding_if_needed(self) -> None:
        """Show first-run walkthrough unless user has dismissed it."""
        state_path = Path(config.ONBOARDING_STATE_FILE)
        if state_path.exists():
            return

        self._show_onboarding_dialog(state_path, persist_state=True)

    def show_walkthrough(self) -> None:
        """Show the onboarding walkthrough on demand."""
        self._show_onboarding_dialog(Path(config.ONBOARDING_STATE_FILE), persist_state=False)

    def _show_onboarding_dialog(self, state_path: Path, persist_state: bool) -> None:
        """Show walkthrough dialog, optionally persisting dismissal state."""
        if hasattr(self, '_onboarding_dialog') and self._onboarding_dialog.winfo_exists():
            self._onboarding_dialog.lift()
            self._onboarding_dialog.focus_force()
            return

        dialog = tk.Toplevel(self.root)
        self._onboarding_dialog = dialog
        dialog.title("Welcome to Trader Ledger")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.geometry("620x380")

        steps = [
            ("Add Trade", "Enter BUY or SELL trades, choose the stock symbol, and the app fills brokerage automatically when supported."),
            ("View Records", "Review all trades, restore deleted rows, and filter by stock, type, or date."),
            ("Reports", "See realized P/L, holding days, open positions, and trade value summaries."),
            ("Trade View", "Get grouped, human-friendly trade units with gross/net P/L and audit details."),
        ]

        index_var = tk.IntVar(value=0)
        show_again_var = tk.BooleanVar(value=True)

        container = ttk.Frame(dialog, padding=20)
        container.pack(fill='both', expand=True)

        title_label = ttk.Label(container, text="Welcome", font=('Consolas', 16, 'bold'))
        title_label.pack(anchor='w')

        step_title = ttk.Label(container, text="", font=('Consolas', 12, 'bold'))
        step_title.pack(anchor='w', pady=(14, 4))

        step_text = ttk.Label(container, text="", wraplength=560, justify='left', font=('Arial', 10))
        step_text.pack(anchor='w', pady=(0, 16))

        footer_frame = ttk.Frame(container)
        footer_frame.pack(fill='x', side='bottom')

        show_again = ttk.Checkbutton(footer_frame, text="Show this walkthrough on startup", variable=show_again_var)
        show_again.pack(side='left')

        def render_step() -> None:
            idx = index_var.get()
            title, text = steps[idx]
            step_title.config(text=f"Step {idx + 1} of {len(steps)}: {title}")
            step_text.config(text=text)
            back_btn.config(state='normal' if idx > 0 else 'disabled')
            next_btn.config(text='Finish' if idx == len(steps) - 1 else 'Next')

        def close_dialog() -> None:
            if persist_state:
                if show_again_var.get():
                    try:
                        state_path.write_text("seen\n", encoding='utf-8')
                    except Exception as exc:
                        logger.warning(f"Could not persist onboarding state: {exc}")
                else:
                    try:
                        if state_path.exists():
                            state_path.unlink()
                        state_path.write_text("disabled\n", encoding='utf-8')
                    except Exception as exc:
                        logger.warning(f"Could not persist onboarding preference: {exc}")
            dialog.destroy()

        def next_step() -> None:
            if index_var.get() >= len(steps) - 1:
                close_dialog()
                return
            index_var.set(index_var.get() + 1)
            render_step()

        def prev_step() -> None:
            if index_var.get() > 0:
                index_var.set(index_var.get() - 1)
                render_step()

        button_frame = ttk.Frame(footer_frame)
        button_frame.pack(side='right')

        back_btn = ttk.Button(button_frame, text="Back", command=prev_step, width=10)
        back_btn.pack(side='left', padx=(0, 8))
        next_btn = ttk.Button(button_frame, text="Next", command=next_step, width=10)
        next_btn.pack(side='left')

        render_step()
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        dialog.bind("<Destroy>", lambda _e: setattr(self, '_onboarding_dialog', None))
