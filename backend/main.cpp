#include "control.h"
#include <iostream>
#include <string>
#include <cstring>

int main(int argc, char *argv[]) {
    std::string prog = argv[0];

    if (argc < 2) {
        printUsage(prog);
        return 1;
    }

    std::string cmd = argv[1];

    if (cmd == "list") {
        handleList();
    } else if (cmd == "kill") {
        if (argc < 3) {
            std::cerr << "Error: 'kill' requires a PID argument\n";
            return 1;
        }
        handleKill(argv[2]);
    } else if (cmd == "pause") {
        if (argc < 3) {
            std::cerr << "Error: 'pause' requires a PID argument\n";
            return 1;
        }
        handlePause(argv[2]);
    } else if (cmd == "resume") {
        if (argc < 3) {
            std::cerr << "Error: 'resume' requires a PID argument\n";
            return 1;
        }
        handleResume(argv[2]);
    } else if (cmd == "priority") {
        if (argc < 4) {
            std::cerr << "Error: 'priority' requires <pid> and <value> arguments\n";
            return 1;
        }
        handlePriority(argv[2], argv[3]);
    } else {
        std::cerr << "Error: unknown command '" << cmd << "'\n";
        printUsage(prog);
        return 1;
    }

    return 0;
}
