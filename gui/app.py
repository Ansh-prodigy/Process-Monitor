import tkinter as tk
from tkinter import ttk
import time
from table import ProcessTable
from actions import ProcessActions

class ProcessMonitorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Process Monitor")
        self.geometry("1000x600")
        self.minsize(800, 500)
        self.configure(bg="#f5f5f5")
        
        # Apply strict safe styling
        self.apply_safe_styles()
        
        # Main Layout Container
        self.main_container = tk.Frame(self, bg="#f5f5f5", padx=20, pady=20)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Header Section
        self.create_header()
        
        # Central Table Section
        self.table_frame = tk.LabelFrame(
            self.main_container, 
            text=" Running Processes ", 
            bg="#f5f5f5", 
            fg="#333333",
            font=("Segoe UI", 10, "bold"),
            padx=10, 
            pady=10
        )
        self.table_frame.pack(fill=tk.BOTH, expand=True, pady=15)
        
        self.table_widget = ProcessTable(self.table_frame, self)
        self.table_widget.pack(fill=tk.BOTH, expand=True)
        
        # Bottom Status + Action Area
        self.create_bottom_area()
        
        # Initialize Actions
        self.actions = ProcessActions(self.table_widget, self)
        
        # Initial Load
        self.actions.refresh()

        # Bind row selection to update info
        self.table_widget.tree.bind('<<TreeviewSelect>>', self.on_select)
        
        # Center the window
        self.center_window(1000, 600)

    def center_window(self, width, height):
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def apply_safe_styles(self):
        style = ttk.Style(self)
        available_themes = style.theme_names()
        if 'vista' in available_themes:
            style.theme_use('vista')
        elif 'clam' in available_themes:
            style.theme_use('clam')
            
        style.configure("Treeview", 
                        background="#ffffff", 
                        foreground="#000000", 
                        rowheight=30, 
                        fieldbackground="#ffffff", 
                        font=("Segoe UI", 10))
                        
        style.configure("Treeview.Heading", 
                        font=("Segoe UI", 10, "bold"), 
                        background="#eaeaea", 
                        foreground="#000000")
        
        style.map("Treeview", background=[('selected', '#ccdbf0')], foreground=[('selected', '#000000')])
        style.map("Treeview.Heading", background=[('active', '#d5d5d5')])

    def create_header(self):
        header_frame = tk.Frame(self.main_container, bg="#f5f5f5")
        header_frame.pack(fill=tk.X)
        
        # Title section left
        title_frame = tk.Frame(header_frame, bg="#f5f5f5")
        title_frame.pack(side=tk.LEFT)
        
        tk.Label(title_frame, text="Process Monitor", bg="#f5f5f5", fg="#111111", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(title_frame, text="Dummy process management dashboard", bg="#f5f5f5", fg="#555555", font=("Segoe UI", 10)).pack(anchor="w")
        
        # Stats section right
        self.stats_frame = tk.Frame(header_frame, bg="#ffffff", bd=1, relief=tk.SOLID, padx=10, pady=5)
        self.stats_frame.pack(side=tk.RIGHT)
        
        self.total_label = tk.Label(self.stats_frame, text="Total Processes: 0", bg="#ffffff", fg="#000000", font=("Segoe UI", 10, "bold"))
        self.total_label.pack()
        
        self.time_label = tk.Label(self.stats_frame, text="Last Refresh: --:--:--", bg="#ffffff", fg="#666666", font=("Segoe UI", 9))
        self.time_label.pack()

    def create_bottom_area(self):
        bottom_frame = tk.Frame(self.main_container, bg="#f5f5f5")
        bottom_frame.pack(fill=tk.X)
        
        # Status labels row
        status_frame = tk.Frame(bottom_frame, bg="#f5f5f5")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.selected_label = tk.Label(status_frame, text="Selected Process: None", bg="#f5f5f5", fg="#333333", font=("Segoe UI", 10))
        self.selected_label.pack(side=tk.LEFT)
        
        self.status_label = tk.Label(status_frame, text="Ready", bg="#f5f5f5", fg="#0066cc", font=("Segoe UI", 10, "bold"))
        self.status_label.pack(side=tk.RIGHT)
        
        # Buttons row
        btn_frame = tk.Frame(bottom_frame, bg="#f5f5f5")
        btn_frame.pack(fill=tk.X)
        
        # Safe tk.Button approach for perfect text readability on all OS
        button_opts = {
            "font": ("Segoe UI", 10),
            "width": 14,
            "relief": tk.GROOVE,
            "bg": "#e6e6e6",
            "fg": "black",
            "activebackground": "#d4d4d4",
            "bd": 2
        }
        
        # Wrap buttons in another frame to center them perfectly
        center_btn_frame = tk.Frame(btn_frame, bg="#f5f5f5")
        center_btn_frame.pack(anchor=tk.CENTER)
        
        self.btn_refresh = tk.Button(center_btn_frame, text="Refresh", command=lambda: self.actions.refresh(), **button_opts)
        self.btn_refresh.pack(side=tk.LEFT, padx=5)
        
        self.btn_kill = tk.Button(center_btn_frame, text="Kill", command=lambda: self.actions.kill(), **button_opts)
        self.btn_kill.pack(side=tk.LEFT, padx=5)
        
        self.btn_pause = tk.Button(center_btn_frame, text="Pause", command=lambda: self.actions.pause(), **button_opts)
        self.btn_pause.pack(side=tk.LEFT, padx=5)
        
        self.btn_resume = tk.Button(center_btn_frame, text="Resume", command=lambda: self.actions.resume(), **button_opts)
        self.btn_resume.pack(side=tk.LEFT, padx=5)
        
        self.btn_boost = tk.Button(center_btn_frame, text="Boost Priority", command=lambda: self.actions.boost(), **button_opts)
        self.btn_boost.pack(side=tk.LEFT, padx=5)

    def on_select(self, event):
        item = self.table_widget.get_selected_item()
        if item:
            pid = item['values'][0]
            name = item['values'][1]
            self.selected_label.config(text=f"Selected Process: {name} (PID {pid})")
        else:
            self.selected_label.config(text="Selected Process: None")

    def update_header_stats(self, count):
        self.total_label.config(text=f"Total Processes: {count}")
        current_time = time.strftime("%H:%M:%S")
        self.time_label.config(text=f"Last Refresh: {current_time}")
        
    def show_status(self, message):
        self.status_label.config(text=message)
        self.after(3000, lambda: self.status_label.config(text="Ready"))
