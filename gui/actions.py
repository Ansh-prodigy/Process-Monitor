import tkinter.messagebox as messagebox
from backend_bridge import kill_process, pause_process, resume_process, boost_priority

class ProcessActions:
    def __init__(self, table_widget, app):
        self.table = table_widget
        self.app = app

    def get_selected_pid(self):
        item = self.table.get_selected_item()
        if not item:
            messagebox.showwarning("Warning", "Please select a process first!")
            return None
        return int(item['values'][0])

    def refresh(self):
        count = self.table.load_data()
        self.app.update_header_stats(count)
        self.app.show_status("Table refreshed")
        self.app.on_select(None)

    def kill(self):
        pid = self.get_selected_pid()
        if pid:
            if messagebox.askyesno("Confirm Kill", f"Terminate process PID {pid}?\n\nThis action cannot be undone."):
                kill_process(pid)
                self.app.show_status(f"Killed PID {pid}")
                self.table.load_data()
                self.app.update_header_stats(len(self.table.tree.get_children()))
                self.app.on_select(None)

    def pause(self):
        pid = self.get_selected_pid()
        if pid:
            pause_process(pid)
            self.app.show_status(f"Paused PID {pid}")
            self.table.load_data()

    def resume(self):
        pid = self.get_selected_pid()
        if pid:
            resume_process(pid)
            self.app.show_status(f"Resumed PID {pid}")
            self.table.load_data()

    def boost(self):
        pid = self.get_selected_pid()
        if pid:
            boost_priority(pid)
            self.app.show_status(f"Priority boosted for PID {pid}")
            self.table.load_data()
