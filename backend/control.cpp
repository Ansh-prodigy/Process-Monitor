#include "control.h"
#include "process_manager.h"
#include <iostream>
#include <sstream>
#include <iomanip>
#include <vector>
#include <cstdlib>

static bool parseIntArg(const std::string &str, int &out) {
    char *end;
    long val = strtol(str.c_str(), &end, 10);
    if (*end != '\0') return false;
    out = static_cast<int>(val);
    return true;
}

void handleList() {
    std::vector<Process> procs = listProcesses();
    std::cout << "[\n";
    for (size_t i = 0; i < procs.size(); i++) {
        const Process &p = procs[i];
        std::cout << " {\"pid\":" << p.pid
                  << ",\"name\":\"" << p.name << "\""
                  << ",\"state\":\"" << p.state << "\""
                  << ",\"cpu\":" << std::fixed << std::setprecision(1) << p.cpu
                  << ",\"memory\":" << std::fixed << std::setprecision(1) << p.memory
                  << "}";
        if (i + 1 < procs.size()) std::cout << ",";
        std::cout << "\n";
    }
    std::cout << "]\n";
}

void handleKill(const std::string &pidStr) {
    int pid;
    if (!parseIntArg(pidStr, pid)) {
        std::cerr << "Error: invalid PID '" << pidStr << "'\n";
        return;
    }
    if (killProcess(pid))
        std::cout << "Process " << pid << " killed successfully\n";
    else
        std::cerr << "Error: failed to kill process " << pid << "\n";
}

void handlePause(const std::string &pidStr) {
    int pid;
    if (!parseIntArg(pidStr, pid)) {
        std::cerr << "Error: invalid PID '" << pidStr << "'\n";
        return;
    }
    if (pauseProcess(pid))
        std::cout << "Process " << pid << " paused successfully\n";
    else
        std::cerr << "Error: failed to pause process " << pid << "\n";
}

void handleResume(const std::string &pidStr) {
    int pid;
    if (!parseIntArg(pidStr, pid)) {
        std::cerr << "Error: invalid PID '" << pidStr << "'\n";
        return;
    }
    if (resumeProcess(pid))
        std::cout << "Process " << pid << " resumed successfully\n";
    else
        std::cerr << "Error: failed to resume process " << pid << "\n";
}

void handlePriority(const std::string &pidStr, const std::string &valStr) {
    int pid, val;
    if (!parseIntArg(pidStr, pid)) {
        std::cerr << "Error: invalid PID '" << pidStr << "'\n";
        return;
    }
    if (!parseIntArg(valStr, val)) {
        std::cerr << "Error: invalid priority value '" << valStr << "'\n";
        return;
    }
    if (changePriority(pid, val))
        std::cout << "Priority of process " << pid << " set to " << val << "\n";
    else
        std::cerr << "Error: failed to change priority of process " << pid << "\n";
}

void printUsage(const std::string &progName) {
    std::cout << "Usage:\n"
              << "  " << progName << " list\n"
              << "  " << progName << " kill <pid>\n"
              << "  " << progName << " pause <pid>\n"
              << "  " << progName << " resume <pid>\n"
              << "  " << progName << " priority <pid> <value>\n";
}
