// Host diagnostics only. Frame full responses independently of model whitespace.
#include "apt_engine.hpp"
#include <iostream>
#include <string>
static std::string quoted(const std::string &text){
    std::string out="\"";const char *hex="0123456789abcdef";
    for(unsigned char c:text){
        if(c=='"'||c=='\\'){out+='\\';out+=c;}
        else if(c<32){out+="\\u00";out+=hex[c>>4];out+=hex[c&15];}
        else out+=c;
    }
    return out+'"';
}
static void response(unsigned long n,bool ok,const std::string &text){
    std::cout<<"{\"sequence\":"<<n<<",\"ok\":"<<(ok?"true":"false")
        <<(ok?",\"text\":":",\"error\":")<<quoted(text)<<"}"<<std::endl;
}
int main(int argc,char **argv){
    if(argc!=2)return 2;
    if(std::string(argv[1])=="--framing-test"){
        response(1,true,"\n[\n  2\n]\n");response(2,true,"[]");response(3,false,"test \"error\"\nwith newline");return 0;
    }
    apt::Engine engine;std::string prompt;unsigned long n=0;
    while(std::getline(std::cin,prompt)){
        ++n;
        try{engine.reset();response(n,true,engine.generate(argv[1],prompt));}
        catch(const std::exception &e){response(n,false,e.what());}
    }
}
