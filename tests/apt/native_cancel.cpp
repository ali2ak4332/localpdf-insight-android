#include "apt_engine.hpp"
#include <chrono>
#include <iostream>
#include <thread>
int main(int argc,char **argv){
 if(argc!=2)return 2;
 apt::Engine engine;engine.cancel();
 try{engine.generate(argv[1],"Select passages. Return [].");return 3;}catch(const std::exception&){}
 engine.reset();bool stopped=false;
 std::thread worker([&]{try{engine.generate(argv[1],"Select passages. Return [].");}catch(const std::exception&){stopped=true;}});
 std::this_thread::sleep_for(std::chrono::milliseconds(5));engine.cancel();worker.join();
 if(!stopped)return 4;
 std::cout<<"Native pre-start and in-flight cancellation passed\n";
}
