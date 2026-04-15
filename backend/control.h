#ifndef CONTROL_H
#define CONTROL_H

#include <string>

void handleList();
void handleKill(const std::string &pidStr);
void handlePause(const std::string &pidStr);
void handleResume(const std::string &pidStr);
void handlePriority(const std::string &pidStr, const std::string &valStr);
void printUsage(const std::string &progName);

#endif
