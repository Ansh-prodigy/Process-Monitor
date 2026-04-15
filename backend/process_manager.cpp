#include "process_manager.h"
#include <dirent.h>
#include <signal.h>
#include <sys/resource.h>
#include <unistd.h>
#include <fstream>
#include <sstream>
#include <cstdlib>
#include <cstring>

static long systemUptime() {
    std::ifstream f("/proc/uptime");
    double up = 0;
    if (f.is_open()) f >> up;
    return static_cast<long>(up);
}

static long hertz() {
    long hz = sysconf(_SC_CLK_TCK);
    return (hz > 0) ? hz : 100;
}

static long totalMemKb() {
    std::ifstream f("/proc/meminfo");
    std::string line;
    while (std::getline(f, line)) {
        if (line.find("MemTotal:") == 0) {
            std::istringstream iss(line);
            std::string label;
            long val;
            iss >> label >> val;
            return val;
        }
    }
    return 1;
}

std::vector<Process> listProcesses() {
    std::vector<Process> procs;
    long hz = hertz();
    long uptime = systemUptime();
    long memTotal = totalMemKb();

    DIR *dir = opendir("/proc");
    if (!dir) return procs;

    struct dirent *entry;
    while ((entry = readdir(dir)) != nullptr) {
        if (entry->d_type != DT_DIR) continue;

        char *end;
        long pid = strtol(entry->d_name, &end, 10);
        if (*end != '\0' || pid <= 0) continue;

        std::string base = "/proc/" + std::string(entry->d_name);

        std::ifstream statFile(base + "/stat");
        if (!statFile.is_open()) continue;

        std::string statLine;
        std::getline(statFile, statLine);
        statFile.close();

        size_t nameStart = statLine.find('(');
        size_t nameEnd = statLine.rfind(')');
        if (nameStart == std::string::npos || nameEnd == std::string::npos) continue;

        std::string name = statLine.substr(nameStart + 1, nameEnd - nameStart - 1);
        std::string rest = statLine.substr(nameEnd + 2);

        std::istringstream iss(rest);
        std::string stateStr;
        long val;
        iss >> stateStr;

        for (int i = 0; i < 10; i++) iss >> val;

        long utime, stime;
        iss >> utime >> stime;

        for (int i = 0; i < 7; i++) iss >> val;

        long starttime;
        iss >> starttime;

        float cpuPct = 0.0f;
        long totalTime = utime + stime;
        long seconds = uptime - (starttime / hz);
        if (seconds > 0) {
            cpuPct = 100.0f * (static_cast<float>(totalTime) / hz) / seconds;
        }

        std::ifstream statusFile(base + "/status");
        long vmRss = 0;
        if (statusFile.is_open()) {
            std::string sline;
            while (std::getline(statusFile, sline)) {
                if (sline.find("VmRSS:") == 0) {
                    std::istringstream rss(sline);
                    std::string label;
                    rss >> label >> vmRss;
                    break;
                }
            }
            statusFile.close();
        }

        float memPct = (memTotal > 0) ? 100.0f * vmRss / memTotal : 0.0f;

        Process p;
        p.pid = static_cast<int>(pid);
        p.name = name;
        p.state = stateStr;
        p.cpu = cpuPct;
        p.memory = memPct;
        procs.push_back(p);
    }
    closedir(dir);
    return procs;
}

bool killProcess(int pid) {
    return kill(pid, SIGKILL) == 0;
}

bool pauseProcess(int pid) {
    return kill(pid, SIGSTOP) == 0;
}

bool resumeProcess(int pid) {
    return kill(pid, SIGCONT) == 0;
}

bool changePriority(int pid, int value) {
    return setpriority(PRIO_PROCESS, pid, value) == 0;
}
