#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/reboot.h>
#include <sys/wait.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
int main(void) {
    mount("proc","/proc","proc",0,0);
    mount("sysfs","/sys","sysfs",0,0);
    mount("devtmpfs","/dev","devtmpfs",0,0);
    mkdir("/dev/shm",0777);
    mount("tmpfs","/dev/shm","tmpfs",0,0);
    setenv("HOME","/tmp",1);
    setenv("PATH","/usr/bin:/bin",1);
    if (!fork()) {
        char *argv[]={"/usr/bin/blender","-b","--factory-startup","--disable-autoexec",
          "/scene.blend","-t","2","--python-exit-code","1","--python","/settings.py",
          "-o","/tmp/frame-####","-F","PNG","-f","65",0};
        execv(argv[0],argv);
        perror("Blender exec"); _exit(127);
    }
    int result; wait(&result);
    struct stat image;
    long size = stat("/tmp/frame-0065.png",&image) ? 0 : image.st_size;
    printf("MERLIN_GUEST_RESULT status=%d frame_bytes=%ld\n",result,size); fflush(stdout);
    if (result==0 && size>0 && !fork()) {
        execl("/usr/bin/sha256sum","sha256sum","/tmp/frame-0065.png",(char *)0);
        _exit(127);
    }
    if(result==0 && size>0) wait(0);
    sync(); reboot(RB_POWER_OFF);
    for (;;) pause();
}
