import tkinter as tk
from tkinter import ttk
from backend_bridge import get_processes

class ProcessTable(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg="#cccccc", bd=1)
        self.app = app
        
        columns = ("pid", "name", "state", "cpu", "memory")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        
        self.tree.heading("pid", text="PID")
        self.tree.heading("name", text="Name")
        self.tree.heading("state", text="State")
        self.tree.heading("cpu", text="CPU (%)")
        self.tree.heading("memory", text="Memory (MB)")
        
        self.tree.column("pid", width=100, anchor=tk.CENTER)
        self.tree.column("name", width=350, anchor=tk.W)
        self.tree.column("state", width=150, anchor=tk.CENTER)
        self.tree.column("cpu", width=120, anchor=tk.CENTER)
        self.tree.column("memory", width=150, anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.config(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree.tag_configure('oddrow', background="#fdfdfd")
        self.tree.tag_configure('evenrow', background="#f2f2f2")
        
    def get_selected_item(self):
        selection = self.tree.selection()
        if not selection:
            return None
        return self.tree.item(selection[0])
        
    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        data = get_processes()
        for idx, proc in enumerate(data):
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            self.tree.insert("", tk.END, values=(
                proc["pid"], 
                proc["name"], 
                proc["state"], 
                f"{proc['cpu']:.1f}", 
                f"{proc['memory']:.1f}"
            ), tags=(tag,))
        return len(data)
