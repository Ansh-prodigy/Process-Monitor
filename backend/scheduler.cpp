#include "scheduler.h"
#include "process_manager.h"
#include <vector>
#include <iostream>

void monitorAndAdjust() {
    std::vector<Process> procs = listProcesses();
    for (size_t i = 0; i < procs.size(); i++) {
        if (procs[i].cpu > 80.0f) {
            if (changePriority(procs[i].pid, 10)) {
                std::cout << "Scheduler: reduced priority of '"
                          << procs[i].name << "' (pid " << procs[i].pid
                          << ") due to high CPU (" << procs[i].cpu << "%)\n";
            }
        }
    }
}
