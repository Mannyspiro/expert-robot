// CPU-only Android JNI bridge for a separately qualified pinned GGUF model.
#include <jni.h>
#include <llama.h>
#include <mutex>
#include <thread>
#include <algorithm>
#include <string>
#include <vector>
#include <cstdint>

namespace {
std::mutex guard;
llama_model* model=nullptr;
llama_context* context=nullptr;
bool backend=false;
std::string from_java(JNIEnv* env,jstring s) {
    if(s==nullptr) return {};
    const char* c=env->GetStringUTFChars(s,nullptr);
    if(c==nullptr) return {};
    std::string value(c);
    env->ReleaseStringUTFChars(s,c);
    return value;
}
void close_model() {
    if(context){llama_free(context);context=nullptr;}
    if(model){llama_model_free(model);model=nullptr;}
}
}
extern "C" JNIEXPORT jboolean JNICALL
Java_org_merlin_studio_LocalModelRuntime_nativeLoadModel(JNIEnv* env,jclass,jstring source) {
    std::lock_guard<std::mutex> lock(guard);
    const std::string path=from_java(env,source);
    if(path.empty()||path.size()>4096)return JNI_FALSE;
    close_model();
    if(!backend){llama_backend_init();backend=true;}
    llama_model_params p=llama_model_default_params();
    p.n_gpu_layers=0;
    model=llama_model_load_from_file(path.c_str(),p);
    if(!model)return JNI_FALSE;
    llama_context_params cp=llama_context_default_params();
    cp.n_ctx=2048;cp.n_batch=512;cp.n_ubatch=512;
    cp.n_threads=std::min(4,std::max(1,static_cast<int>(std::thread::hardware_concurrency())));
    cp.n_threads_batch=cp.n_threads;
    context=llama_init_from_model(model,cp);
    if(!context){close_model();return JNI_FALSE;}
    return JNI_TRUE;
}
extern "C" JNIEXPORT jstring JNICALL
Java_org_merlin_studio_LocalModelRuntime_nativeGenerate(JNIEnv* env,jclass,jstring input,jint budget) {
    std::lock_guard<std::mutex> lock(guard);
    if(!context||!model)return env->NewStringUTF("MODEL_NOT_LOADED");
    if(budget<1||budget>256)return env->NewStringUTF("INVALID_TOKEN_BUDGET");
    std::string prompt=from_java(env,input);
    if(prompt.empty()||prompt.size()>32768)return env->NewStringUTF("PROMPT_TOO_LONG");
    const llama_vocab* vocab=llama_model_get_vocab(model);
    if(!vocab)return env->NewStringUTF("VOCAB_UNAVAILABLE");
    std::vector<llama_token> tokens(512);
    int32_t n=llama_tokenize(vocab,prompt.data(),static_cast<int32_t>(prompt.size()),
                            tokens.data(),static_cast<int32_t>(tokens.size()),true,true);
    if(n<=0||n>512)return env->NewStringUTF("PROMPT_TOKEN_LIMIT");
    tokens.resize(static_cast<size_t>(n));
    llama_memory_clear(llama_get_memory(context),true);
    llama_batch initial=llama_batch_get_one(tokens.data(),n);
    if(llama_decode(context,initial)!=0)return env->NewStringUTF("MODEL_PROMPT_FAILURE");
    llama_sampler* sampler=llama_sampler_init_greedy();
    if(!sampler)return env->NewStringUTF("SAMPLER_UNAVAILABLE");
    std::string answer;
    for(int i=0;i<budget;i++){
        llama_token token=llama_sampler_sample(sampler,context,-1);
        if(llama_vocab_is_eog(vocab,token))break;
        char buf[1024];
        int32_t bytes=llama_token_to_piece(vocab,token,buf,static_cast<int32_t>(sizeof(buf)),0,false);
        if(bytes<0||bytes>static_cast<int32_t>(sizeof(buf))){answer="TOKEN_CONVERSION_ERROR";break;}
        if(answer.size()+static_cast<size_t>(bytes)>8192)break;
        answer.append(buf,static_cast<size_t>(bytes));
        llama_sampler_accept(sampler,token);
        llama_batch step=llama_batch_get_one(&token,1);
        if(llama_decode(context,step)!=0){answer="MODEL_STEP_FAILURE";break;}
    }
    llama_sampler_free(sampler);
    return env->NewStringUTF(answer.c_str());
}
extern "C" JNIEXPORT void JNICALL
Java_org_merlin_studio_LocalModelRuntime_nativeRelease(JNIEnv*,jclass) {
    std::lock_guard<std::mutex> lock(guard);
    close_model();
}
