#include "apt_engine.hpp"
#include <iostream>
#include <string>
int main(int argc,char **argv) {
    if(argc!=2) { std::cerr<<"usage: apt-select model.gguf\n"; return 2; }
    apt::Engine engine;
    std::string prompt;
    while(std::getline(std::cin,prompt)) {
        try { engine.reset(); std::cout<<engine.generate(argv[1],prompt)<<std::endl; }
        catch(const std::exception &e) { std::cout<<"ERROR: "<<e.what()<<std::endl; }
    }
}
