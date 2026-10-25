/* CTR-Online on Mac: the app's main executable. Runs Contents/Resources/launch.sh (the launcher
 * setup) with the same arguments; a Mach-O main executable keeps the app's signature in the binary. */
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char exe[PATH_MAX], real[PATH_MAX], script[PATH_MAX];
    uint32_t size = sizeof(exe);
    if (_NSGetExecutablePath(exe, &size) != 0 || !realpath(exe, real)) return 1;
    char *slash = strrchr(real, '/');           /* .../Contents/MacOS/CTR-Online */
    if (!slash) return 1;
    *slash = 0;
    snprintf(script, sizeof(script), "%s/../Resources/launch.sh", real);
    char **args = calloc((size_t)argc + 2, sizeof(char *));
    if (!args) return 1;
    args[0] = "/bin/zsh";
    args[1] = script;
    for (int i = 1; i < argc; ++i) args[i + 1] = argv[i];
    execv("/bin/zsh", args);
    perror("CTR-Online: cannot start launch.sh");
    return 1;
}
