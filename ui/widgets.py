import tkinter as tk
from tkinter import ttk
from typing import Any

class Tooltip:
    """Lightweight tooltip for Tk widgets."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip_window: tk.Toplevel | None = None
        self.widget.bind("<Enter>", self._show)
        self.widget.bind("<Leave>", self._hide)

    def _show(self, _event: tk.Event) -> None:
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(
            self.tip_window,
            text=self.text,
            background="#f4f6f8",
            foreground="#2c3e50",
            relief="solid",
            borderwidth=1,
            padding=(6, 3)
        )
        label.pack()

    def _hide(self, _event: tk.Event) -> None:
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


def create_form_row(
    parent: ttk.Frame, 
    row: int, 
    label_text: str, 
    widget_class: type, 
    hint_text: str = "",
    widget_kwargs: dict[str, Any] | None = None
) -> tuple[ttk.Label, tk.Widget, ttk.Label | None]:
    """
    Helper to generate a standard 3-column form row: 
    [Right-aligned Label] | [Widget] | [Hint Label]
    """
    # 1. Label
    lbl = ttk.Label(parent, text=label_text, font=('Consolas', 10))
    lbl.grid(row=row, column=0, sticky='e', padx=5, pady=8)
    
    # 2. Widget
    kwargs = widget_kwargs or {}
    if 'font' not in kwargs and widget_class != ttk.Frame:
        kwargs['font'] = ('Consolas', 10)
        
    widget = widget_class(parent, **kwargs)
    widget.grid(row=row, column=1, sticky='w', padx=5, pady=8)
    
    # 3. Hint (Optional)
    hint_lbl = None
    if hint_text:
        hint_lbl = ttk.Label(parent, text=hint_text, font=('Consolas', 9), foreground='gray')
        hint_lbl.grid(row=row, column=2, sticky='w', padx=5)
        
    return lbl, widget, hint_lbl

def create_treeview(
    parent: ttk.Frame,
    columns: list[tuple[str, str, int, str]],  # (id, heading, width, anchor)
    height: int = 10
) -> tuple[ttk.Frame, ttk.Treeview]:
    """Helper to create a standard Treeview with scrollbar."""
    tree_frame = ttk.Frame(parent)
    
    scrollbar = ttk.Scrollbar(tree_frame)
    scrollbar.pack(side='right', fill='y')
    
    col_ids = [c[0] for c in columns]
    tree = ttk.Treeview(
        tree_frame,
        columns=col_ids,
        show='headings',
        height=height,
        yscrollcommand=scrollbar.set
    )
    scrollbar.config(command=tree.yview)
    
    for col_id, heading, width, anchor in columns:
        tree.heading(col_id, text=heading, anchor=anchor)
        tree.column(col_id, width=width, anchor=anchor)
        
    # Scrollwheel binding
    tree.bind('<MouseWheel>', lambda e: tree.yview_scroll(int(-1 * (e.delta / 120)), "units"))
    
    tree.pack(fill='both', expand=True)
    return tree_frame, tree
