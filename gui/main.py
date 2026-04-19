from app import ProcessMonitorApp

if __name__ == "__main__":
    app = ProcessMonitorApp()
    app.mainloop()
from backend_bridge import get_processes

def load_processes(tree):
    for row in tree.get_children():
        tree.delete(row)

    data = get_processes()

    for proc in data:
        tree.insert("", "end", values=(
            proc["pid"],
            proc["name"],
            proc["state"],
            proc["cpu"],
            proc["memory"]
        ))
