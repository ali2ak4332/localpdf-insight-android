#include "apt_engine.hpp"
#include <algorithm>
#include <memory>
#include <stdexcept>
#include <thread>
#include <vector>

namespace apt {
Engine::Engine() { static std::once_flag flag; std::call_once(flag,[]{llama_backend_init();}); }
Engine::~Engine() { if(context_)llama_free(context_);if(model_)llama_model_free(model_); }
void Engine::load(const std::string &path) {
    if(model_&&path==path_)return;
    if(context_) {llama_free(context_);context_=nullptr;}
    if(model_) {llama_model_free(model_);model_=nullptr;}
    auto params=llama_model_default_params();params.n_gpu_layers=0;params.load_mode=LLAMA_LOAD_MODE_MMAP;
    params.progress_callback=[](float,void *p){return !static_cast<Engine*>(p)->cancelled_.load();};
    params.progress_callback_user_data=this;
    model_=llama_model_load_from_file(path.c_str(),params);
    if(!model_)throw std::runtime_error(cancelled_?"Analysis cancelled":"Could not load the verified Gemma model");
    auto ctx=llama_context_default_params();ctx.n_ctx=4096;ctx.n_batch=256;ctx.n_ubatch=128;
    ctx.n_threads=ctx.n_threads_batch=std::max(1u,std::min(4u,std::thread::hardware_concurrency()));
    ctx.offload_kqv=false;ctx.no_perf=true;
    ctx.abort_callback=[](void *p){return static_cast<Engine*>(p)->cancelled_.load();};ctx.abort_callback_data=this;
    context_=llama_init_from_model(model_,ctx);
    if(!context_){llama_model_free(model_);model_=nullptr;throw std::runtime_error("Insufficient memory for model context");}
    path_=path;
}
std::string Engine::generate(const std::string &path,const std::string &prompt) {
    std::unique_lock<std::mutex> lock(running_,std::try_to_lock);
    if(!lock.owns_lock())throw std::runtime_error("Model is busy");
    if(prompt.empty()||prompt.size()>24000)throw std::runtime_error("Prompt is outside supported bounds");
    if(cancelled_)throw std::runtime_error("Analysis cancelled");
    load(path);
    struct Clear {llama_context *ctx;~Clear(){llama_memory_clear(llama_get_memory(ctx),true);}} clear{context_};
    llama_memory_clear(llama_get_memory(context_),true);
    const auto *vocab=llama_model_get_vocab(model_);
    llama_chat_message message{"user",prompt.c_str()};
    const char *tmpl=llama_model_chat_template(model_,nullptr);
    int len=llama_chat_apply_template(tmpl,&message,1,true,nullptr,0);
    if(len<=0||len>50000)throw std::runtime_error("Unsupported model prompt template");
    std::vector<char> formatted(len+1);
    len=llama_chat_apply_template(tmpl,&message,1,true,formatted.data(),formatted.size());
    int count=-llama_tokenize(vocab,formatted.data(),len,nullptr,0,true,true);
    if(count<=0||count+96>4096)throw std::runtime_error("Section exceeds model context; reduce section size");
    std::vector<llama_token> tokens(count);
    if(llama_tokenize(vocab,formatted.data(),len,tokens.data(),tokens.size(),true,true)!=count)
        throw std::runtime_error("Model tokenization failed");
    for(int i=0;i<count;i+=256){
        if(cancelled_)throw std::runtime_error("Analysis cancelled");
        if(llama_decode(context_,llama_batch_get_one(tokens.data()+i,std::min(256,count-i))))
            throw std::runtime_error(cancelled_?"Analysis cancelled":"Prompt evaluation failed");
    }
    auto *chain=llama_sampler_chain_init(llama_sampler_chain_default_params());
    if(!chain)throw std::runtime_error("Sampler allocation failed");
    std::unique_ptr<llama_sampler,decltype(&llama_sampler_free)> sampler(chain,llama_sampler_free);
    const char *grammar="root ::= \"[\" ws (num (ws \",\" ws num)*)? ws \"]\" ws\nnum ::= [0-9] [0-9]?\nws ::= [ \\t\\n\\r]*\n";
    auto *constraint=llama_sampler_init_grammar(vocab,grammar,"root");
    if(!constraint)throw std::runtime_error("Selection grammar unavailable");
    llama_sampler_chain_add(chain,constraint);llama_sampler_chain_add(chain,llama_sampler_init_greedy());
    std::string result;
    for(int i=0;i<96;i++){
        if(cancelled_)throw std::runtime_error("Analysis cancelled");
        auto token=llama_sampler_sample(chain,context_,-1);
        if(llama_vocab_is_eog(vocab,token))return result;
        char piece[256];int n=llama_token_to_piece(vocab,token,piece,sizeof(piece),0,false);
        if(n<0||n>int(sizeof(piece)))throw std::runtime_error("Invalid model output token");
        result.append(piece,n);
        if(result.size()>4096)throw std::runtime_error("Model output exceeded bounds");
        if(result.find(']')!=std::string::npos)return result;
        if(llama_decode(context_,llama_batch_get_one(&token,1)))throw std::runtime_error("Generation failed or cancelled");
    }
    throw std::runtime_error("Incomplete model selection; findings withheld");
}
}
