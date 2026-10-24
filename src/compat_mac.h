/* macOS (x86_64 under Rosetta 2) counterparts of the Linux calls the runtime uses. Included
 * through runtime.h after the C library headers, as compat_win.h is on Windows. */
#ifndef BB_COMPAT_MAC_H
#define BB_COMPAT_MAC_H
#ifdef __APPLE__
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/uio.h>
#include <sys/random.h>
#include <sys/resource.h>
#include <mach/mach_init.h>
#include <mach/mach_vm.h>
#undef round_page
#undef trunc_page

#define st_atim st_atimespec
#define st_mtim st_mtimespec
#define st_ctim st_ctimespec
#ifndef CLOCK_REALTIME_COARSE
#define CLOCK_REALTIME_COARSE CLOCK_REALTIME
#endif
#ifndef TIMER_ABSTIME
#define TIMER_ABSTIME 1
#endif
#define RUSAGE_THREAD RUSAGE_SELF
/* No MAP_FIXED_NOREPLACE: without MAP_FIXED the address is a hint and callers check the result. */
#define MAP_FIXED_NOREPLACE 0
#define MFD_CLOEXEC 0
#ifndef PTHREAD_RECURSIVE_MUTEX_INITIALIZER_NP
#define PTHREAD_RECURSIVE_MUTEX_INITIALIZER_NP PTHREAD_RECURSIVE_MUTEX_INITIALIZER
#endif

/* Anonymous shared memory: a POSIX shared memory object unlinked right away. macOS sizes it
 * with one ftruncate, which is all the runtime does. */
static inline int memfd_create(const char *name, unsigned flags) {
    (void)flags;
    static unsigned counter;
    char path[64];
    snprintf(path, sizeof(path), "/bb%d.%u.%.16s", (int)getpid(), __atomic_fetch_add(&counter, 1, __ATOMIC_RELAXED), name);
    const int fd = shm_open(path, O_RDWR | O_CREAT | O_EXCL, 0600);
    if (fd >= 0) shm_unlink(path);
    return fd;
}
static inline ssize_t getrandom(void *buffer, size_t size, unsigned flags) {
    (void)flags;
    for (size_t done = 0; done < size;) {
        const size_t n = size - done < 256 ? size - done : 256;
        if (getentropy((char *)buffer + done, n)) return -1;
        done += n;
    }
    return (ssize_t)size;
}
static inline int sched_getcpu(void) { return 0; }
static inline int pthread_condattr_setclock(pthread_condattr_t *attr, clockid_t clock) { (void)attr; (void)clock; return 0; }
static inline ssize_t process_vm_readv(pid_t pid, const struct iovec *local, unsigned long liovcnt,
                                       const struct iovec *remote, unsigned long riovcnt, unsigned long flags) {
    (void)pid; (void)liovcnt; (void)riovcnt; (void)flags;
    mach_vm_size_t got = 0;
    if (mach_vm_read_overwrite(mach_task_self(), (mach_vm_address_t)(uintptr_t)remote->iov_base, remote->iov_len,
                               (mach_vm_address_t)(uintptr_t)local->iov_base, &got) != KERN_SUCCESS) {
        errno = EFAULT;
        return -1;
    }
    return (ssize_t)got;
}
static inline int clock_nanosleep(clockid_t clock, int flags, const struct timespec *t, struct timespec *rest) {
    (void)rest;
    struct timespec d = *t;
    if (flags & TIMER_ABSTIME) {
        struct timespec now;
        clock_gettime(clock, &now);
        d.tv_sec -= now.tv_sec;
        d.tv_nsec -= now.tv_nsec;
        if (d.tv_nsec < 0) { d.tv_nsec += 1000000000L; --d.tv_sec; }
        if (d.tv_sec < 0) return 0;
    }
    return nanosleep(&d, NULL) ? errno : 0;
}
/* Timed locks poll: macOS has none. The deadline is on CLOCK_REALTIME, as POSIX defines. */
#define BB_MAC_TIMED_LOCK(trylock, object, deadline)                                                \
    for (;;) {                                                                                       \
        const int r_ = trylock(object);                                                              \
        if (r_ != EBUSY) return r_;                                                                  \
        struct timespec now_;                                                                        \
        clock_gettime(CLOCK_REALTIME, &now_);                                                        \
        if (now_.tv_sec > (deadline)->tv_sec ||                                                      \
            (now_.tv_sec == (deadline)->tv_sec && now_.tv_nsec >= (deadline)->tv_nsec)) return ETIMEDOUT; \
        const struct timespec nap_ = {0, 100000};                                                    \
        nanosleep(&nap_, NULL);                                                                      \
    }
static inline int pthread_mutex_timedlock(pthread_mutex_t *m, const struct timespec *t) { BB_MAC_TIMED_LOCK(pthread_mutex_trylock, m, t) }
static inline int pthread_rwlock_timedrdlock(pthread_rwlock_t *l, const struct timespec *t) { BB_MAC_TIMED_LOCK(pthread_rwlock_tryrdlock, l, t) }
static inline int pthread_rwlock_timedwrlock(pthread_rwlock_t *l, const struct timespec *t) { BB_MAC_TIMED_LOCK(pthread_rwlock_trywrlock, l, t) }
/* Top of the calling thread's stack. */
static inline uintptr_t compat_thread_stack_high(void) { return (uintptr_t)pthread_get_stackaddr_np(pthread_self()); }

/* Signal context registers (Linux names). */
#include <sys/ucontext.h>
#define BB_UC_RIP(uc) ((uc)->uc_mcontext->__ss.__rip)
#define BB_UC_RSP(uc) ((uc)->uc_mcontext->__ss.__rsp)
#endif
#endif
