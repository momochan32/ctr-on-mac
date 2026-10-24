// SacredFire (macOS, x86_64 under Rosetta 2): Linux names the GPU library uses, force-included
// like bb_win_compat.h on Windows. On Linux it only adds BbGregs.
#pragma once
#ifdef __APPLE__
#include <pthread.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <sys/resource.h>
#include <sys/ucontext.h>
#include <thread>
#include "../../src/compat_mac.h"

// Darwin thread state order: rax rbx rcx rdx rdi rsi rbp rsp r8..r15 rip rflags.
typedef uint64_t greg_t;
enum { REG_RAX = 0, REG_RBX, REG_RCX, REG_RDX, REG_RDI, REG_RSI, REG_RBP, REG_RSP, REG_R8, REG_R9, REG_R10,
       REG_R11, REG_R12, REG_R13, REG_R14, REG_R15, REG_RIP, REG_EFL };
inline greg_t* BbGregs(ucontext_t* uc) { return reinterpret_cast<greg_t*>(&uc->uc_mcontext->__ss); }
inline const greg_t* BbGregs(const ucontext_t* uc) { return reinterpret_cast<const greg_t*>(&uc->uc_mcontext->__ss); }
inline pid_t gettid() { uint64_t id = 0; pthread_threadid_np(nullptr, &id); return static_cast<pid_t>(id); }
inline int pthread_setname_np(pthread_t thread, const char* name) {
    return pthread_equal(thread, pthread_self()) ? pthread_setname_np(name) : 0;
}
// No affinity or idle scheduling class: every core counts, background threads get low priority.
typedef struct { unsigned count; } cpu_set_t;
#define CPU_ZERO(set) ((set)->count = 0)
#define CPU_COUNT(set) static_cast<int>((set)->count)
inline int sched_getaffinity(int, size_t, cpu_set_t* set) { set->count = std::thread::hardware_concurrency(); return 0; }
#define SCHED_IDLE SCHED_OTHER
#elif !defined(_WIN32)
#ifdef __APPLE__
#include <sys/ucontext.h>
#else
#include <ucontext.h>
#endif
inline greg_t* BbGregs(ucontext_t* uc) { return uc->uc_mcontext.gregs; }
inline const greg_t* BbGregs(const ucontext_t* uc) { return uc->uc_mcontext.gregs; }
#endif
#ifdef __APPLE__
// No SCHED_IDLE class: callers fall back to the lowest nice level.
inline int sched_setscheduler(pid_t, int, const sched_param*) { errno = ENOSYS; return -1; }
#endif
