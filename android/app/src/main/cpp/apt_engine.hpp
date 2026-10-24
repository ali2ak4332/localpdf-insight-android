#pragma once
#include <atomic>
#include <string>
#include <mutex>
#include "llama.h"
namespace apt {
class Engine {
    llama_model *model_=nullptr;
    llama_context *context_=nullptr;
    std::atomic_bool cancelled_{false};
    std::string path_;
    std::mutex running_;
    void load(const std::string &path);
public:
    Engine();
    ~Engine();
    Engine(const Engine&)=delete;
    void cancel() { cancelled_.store(true); }
    void reset() { cancelled_.store(false); }
    std::string generate(const std::string &path,const std::string &prompt);
};
}
