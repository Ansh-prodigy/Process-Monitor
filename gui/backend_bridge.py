import time
import random

# Dummy data store
_processes = [
    {"pid": 1001, "name": "chrome.exe", "state": "Running", "cpu": 12.5, "memory": 512.0},
    {"pid": 1002, "name": "explorer.exe", "state": "Running", "cpu": 2.1, "memory": 128.5},
    {"pid": 1003, "name": "vscode.exe", "state": "Running", "cpu": 5.4, "memory": 768.2},
    {"pid": 1004, "name": "python.exe", "state": "Running", "cpu": 45.2, "memory": 256.0},
    {"pid": 1005, "name": "spotify.exe", "state": "Paused", "cpu": 0.0, "memory": 180.4},
    {"pid": 1006, "name": "slack.exe", "state": "Running", "cpu": 3.8, "memory": 402.1},
    {"pid": 1007, "name": "discord.exe", "state": "Running", "cpu": 4.1, "memory": 310.5},
    {"pid": 1008, "name": "winword.exe", "state": "Paused", "cpu": 0.0, "memory": 85.0},
]

def get_processes():
    for p in _processes:
        if p["state"] == "Running":
            p["cpu"] = max(0.0, min(100.0, round(p["cpu"] + random.uniform(-1.5, 1.5), 1)))
            p["memory"] = max(10.0, round(p["memory"] + random.uniform(-2, 2), 1))
    return _processes

def kill_process(pid):
    global _processes
    _processes = [p for p in _processes if p["pid"] != pid]

def pause_process(pid):
    for p in _processes:
        if p["pid"] == pid:
            p["state"] = "Paused"
            p["cpu"] = 0.0
            break

def resume_process(pid):
    for p in _processes:
        if p["pid"] == pid:
            p["state"] = "Running"
            p["cpu"] = round(random.uniform(1.0, 10.0), 1)
            break

def boost_priority(pid):
    for p in _processes:
        if p["pid"] == pid:
            if p["state"] == "Running":
                p["cpu"] = min(100.0, round(p["cpu"] + 15.0, 1))
            break
