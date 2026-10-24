#include "apt_engine.hpp"
#include <jni.h>
#include <map>
#include <memory>
#include <mutex>

namespace {
std::mutex registryMutex;
std::map<jlong,std::shared_ptr<apt::Engine>> engines;
jlong nextId=1;
std::shared_ptr<apt::Engine> get(jlong id){std::lock_guard<std::mutex> lock(registryMutex);
 auto it=engines.find(id);return it==engines.end()?nullptr:it->second;}
void error(JNIEnv *env,const char *message){env->ThrowNew(env->FindClass("java/lang/IllegalStateException"),message);}
}
extern "C" JNIEXPORT jlong JNICALL Java_app_localpdf_insight_AptNative_create(JNIEnv *env,jclass){
 try{std::lock_guard<std::mutex> lock(registryMutex);jlong id=nextId++;engines.emplace(id,std::make_shared<apt::Engine>());return id;}
 catch(const std::exception &e){error(env,e.what());return 0;}
}
extern "C" JNIEXPORT void JNICALL Java_app_localpdf_insight_AptNative_reset(JNIEnv*,jclass,jlong id){if(auto p=get(id))p->reset();}
extern "C" JNIEXPORT void JNICALL Java_app_localpdf_insight_AptNative_cancel(JNIEnv*,jclass,jlong id){if(auto p=get(id))p->cancel();}
extern "C" JNIEXPORT void JNICALL Java_app_localpdf_insight_AptNative_close(JNIEnv*,jclass,jlong id){
 std::lock_guard<std::mutex> lock(registryMutex);engines.erase(id);
}
extern "C" JNIEXPORT jstring JNICALL Java_app_localpdf_insight_AptNative_generate(JNIEnv *env,jclass,jlong id,jstring path,jbyteArray prompt){
 auto engine=get(id);if(!engine){error(env,"Model session closed");return nullptr;}
 const char *file=env->GetStringUTFChars(path,nullptr);if(!file)return nullptr;
 std::string fileName(file);env->ReleaseStringUTFChars(path,file);
 jsize length=env->GetArrayLength(prompt);
 if(length<1||length>24000){error(env,"Prompt outside supported bounds");return nullptr;}
 std::string text(length,'\0');env->GetByteArrayRegion(prompt,0,length,reinterpret_cast<jbyte*>(&text[0]));
 if(env->ExceptionCheck())return nullptr;
 try{auto result=engine->generate(fileName,text);return env->NewStringUTF(result.c_str());}
 catch(const std::exception &e){error(env,e.what());return nullptr;}
}
