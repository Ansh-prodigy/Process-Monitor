#ifndef PROCESS_MANAGER_H
#define PROCESS_MANAGER_H

#include <string>
#include <vector>

struct Process {
    int pid;
    std::string name;
    std::string state;
    float cpu;
    float memory;
};

std::vector<Process> listProcesses();
bool killProcess(int pid);
bool pauseProcess(int pid);
bool resumeProcess(int pid);
bool changePriority(int pid, int value);

#endif
