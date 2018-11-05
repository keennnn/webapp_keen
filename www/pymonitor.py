# -*- coding: utf-8 -*-
"""
Created on Thu Nov  1 15:24:39 2018

@author: keen_liu
"""


"""
在继续工作前，注意到每次修改Python代码，都必须在命令行先Ctrl-C停止服务器，再重启，改动才能生效。
在开发阶段，每天都要修改、保存几十次代码，每次保存都手动来这么一下非常麻烦，严重地降低了我们的开发效率。有没有办法让服务器检测到代码修改后自动重新加载呢？
Django的开发环境在Debug模式下就可以做到自动重新加载，如果我们编写的服务器也能实现这个功能，就能大大提升开发效率。
可惜的是，Django没把这个功能独立出来，不用Django就享受不到，怎么办？
其实Python本身提供了重新载入模块的功能，但不是所有模块都能被重新载入。另一种思路是检测www目录下的代码改动，一旦有改动，就自动重启服务器。
按照这个思路，我们可以编写一个辅助程序pymonitor.py，让它启动wsgiapp.py，并时刻监控www目录下的代码改动，有改动时，先把当前wsgiapp.py进程杀掉，再重启，就完成了服务器进程的自动重启。
要监控目录文件的变化，我们也无需自己手动定时扫描，Python的第三方库watchdog可以利用操作系统的API来监控目录文件的变化，并发送通知。
"""


import os, sys, time, subprocess

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def log(s):
    print('[Monitor] %s' % s)

#编辑MyFileSystemEventHander
class MyFileSystemEventHander(FileSystemEventHandler):

    def __init__(self, fn):
        super(MyFileSystemEventHander, self).__init__()
        self.restart = fn   #导入重启函数restart_process，没括号

    def on_any_event(self, event):
        if event.src_path.endswith('.py'):   #监视`.py`后缀文件发生改变
            log('Python source file changed: %s' % event.src_path)
            self.restart()

command = ['echo', 'ok']   #重启操作文件的信息
process = None

#退出程序
def kill_process():
    global process
    if process:
        log('Kill process [%s]...' % process.pid)
        process.kill()
        process.wait()
        log('Process ended with code %s.' % process.returncode)
        process = None

#开始程序
def start_process():
    global process, command
    log('Start process %s...' % ' '.join(command))
    process = subprocess.Popen(command, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)

#重启程序
def restart_process():
    kill_process()
    start_process()

#监视
def start_watch(path, callback):
    observer = Observer()
    observer.schedule(MyFileSystemEventHander(restart_process), path, recursive=True)
    observer.start()
    log('Watching directory %s...' % path)
    start_process()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == '__main__':
    #sys.argv[]说白了就是一个从程序外部获取参数的桥梁
    #我们从外部取得的参数可以是多个，所以获得的是一个列表（list)，也就是说sys.argv其实可以看作是一个列表。其第一个元素是程序本身，随后才依次是外部给予的参数。
    #其实也是通过这个这个方式拿到输入的要执行的文件
    argv = sys.argv[1:]  #用于在命令行取程序外部输入参数-->http://www.cnblogs.com/aland-1415/p/6613449.html
    if not argv:
        print('Usage: ./pymonitor your-script.py')
        exit(0)
    if argv[0] != 'python':
        argv.insert(0, 'python')
    command = argv  #操作文件的名字及程序名 其实就是python xx/xx.py这样的执行py文件的指令
    #这个是为了获得要执行的文件的上级目录，以便后续通过watchdog监控这个目录下所有的.py的改动
    path = os.path.abspath(os.path.dirname(os.path.dirname(argv[1])))
    start_watch(path, None)

