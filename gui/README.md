# Process Monitor GUI

A lightweight, modern, Tkinter-based desktop dashboard designed to simulate system task management.

## 🚀 Features

- **Clean Dashboard UI**: Built with native standard `tk` components to ensure cross-platform text readability and a professional layout.
- **Process Table**: A visually structured list featuring striped rows, custom fonts, fixed dimensions, and a vertical scrollbar.
- **Live Status Feedback**: A built-in status area that alerts users on actions performed (e.g., "Killed PID 1004") which automatically clears after 3 seconds.
- **Dynamic Selection Management**: Safely tracks row selection to only apply actions to precisely targeted processes, rejecting invalid inputs.
- **Simulated Backend Integration**: Includes a dummy bridge capable of simulating CPU load fluctuations, process pausing, process termination, and priority boosting behaviors.

## 📁 Project Structure

The project has been modularized to ensure proper separation of concerns:

- `main.py` — The entrypoint of the application.
- `app.py` — Constructs the main Window, enforces styling defaults, builds the Header statistics, and initializes the bottom button layout bounds.
- `table.py` — Dedicated solely to building, styling, and injecting data into the central `ttk.Treeview` process table.
- `actions.py` — Maps User Interface actions (button clicks) to their corresponding backend commands and handles GUI refresh cascades.
- `backend_bridge.py` — Provides safe dummy data to populate the GUI and processes state lifecycle events without modifying real OS components.

## 🖥 How to Run

To start the Process Monitor GUI, navigate to your root project directory (e.g. `e:\os-project`) and run the application via Python:

```bash
python process-monitor/gui/main.py
```

## 🎨 UI/UX Design Philosophies

This application was redesigned to step away from the default basic Tkinter appearance without sacrificing stability:
- **No Invisible Text**: By relying on standard native `tk.Button` with custom backgrounds/reliefs instead of experimental `ttk` button themes, text remains 100% readable on all Windows versions.
- **Framed Bounds**: Extensive use of simple borders, margins, and centered paddings prevents the UI from looking like a stretched, empty demo app.
- **Subdued Professional Colors**: Employs a light-gray base with cleanly contrasting white data tables for a mature desktop feel.
