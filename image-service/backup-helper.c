#include <unistd.h>
#include <stdlib.h>

/* Intentionally vulnerable CTF helper.
 * Runs only inside the disposable image-service container.
 * Weakness: setuid-root helper executes `tar` via PATH rather than an absolute path.
 */
int main(void) {
    setuid(0);
    setgid(0);
    return system("tar -cf /tmp/lab-backup.tar /app/uploads >/dev/null 2>&1");
}
