# coding: utf-8


import six,imp,os,sys,signal,socket, time,datetime, pickle,zipfile, mmap,multiprocessing, threading, traceback
from six.moves import builtins,reload_module
if six.PY2 and sys.getdefaultencoding() != 'utf8':
    reload(sys)
    sys.setdefaultencoding('utf8')

if six.PY3:
    import asyncio
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


sys.path.insert(0, '.')
from tornado import web, process, gen, log, netutil
from tornado.log import gen_log
from tornado.process import cpu_count,errno_from_exception, errno, _reseed_random
from concurrent.futures import ProcessPoolExecutor

DEBUG = 0
DEBUG_IO = six.StringIO()
CPU_COUNT = cpu_count()


THIS_DIRNAME = os.path.abspath(os.getcwd())
EXIT_PENDING = False

listen_port = None
def fork_processes(ports=None, max_restarts=100):
    global listen_port
    assert listen_port is None
    assert isinstance(ports, (list, tuple)) and len(ports) > 0, '端口列表不正确.'
    gen_log.info("Starting service on ports: %s", ports)
    children = {}

    def start_child(port):
        pid = os.fork()
        if pid == 0:
            # child process
            _reseed_random()
            global listen_port
            listen_port = port
            print('FORKED: %s' % port)
            return port
        else:
            children[pid] = port
            return None

    for port in ports:
        l_port = start_child(port)
        if l_port is not None:
            return l_port

    num_restarts = 0
    exit_pending = 0
    while 1:
        try:
            pid, status = os.wait()
        except KeyboardInterrupt:
            print('Ctrl+C, Exit.')
            sys.exit(0)
        except OSError as e:
            if errno_from_exception(e) == errno.EINTR:
                continue
            if errno_from_exception(e) == errno.ECHILD:
                break
            raise

        if pid not in children:
            continue

        port = children.pop(pid)

        if exit_pending:
            continue

        if os.WIFSIGNALED(status):
            gen_log.warning("child [port:%s] [pid:%d] killed by [signal:%d], restarting", port, pid, os.WTERMSIG(status))
        elif os.WEXITSTATUS(status) != 0:
            gen_log.warning("child [port:%s] [pid:%d] exited with status %d, restarting", port, pid, os.WEXITSTATUS(status))
        else:
            gen_log.info(   "child [port:%s] [pid:%d] exited normally", port, pid)
            continue

        num_restarts += 1
        if num_restarts > max_restarts:
            raise RuntimeError("child [port:%s] too many restarts, giving up", port)
        l_port = start_child(port)
        if l_port is not None:
            return l_port
    # All child processes exited cleanly, so exit the master process
    # instead of just returning to right after the call to
    # fork_processes (which will probably just start up another IOLoop
    # unless the caller checks the return value).

    print('Children: %s' % sorted(children.items(), key=lambda x:x[1]))
    print('Main Process Exiting...')
    sys.exit(0)


class MainApplication(web.Application):
    @classmethod
    def ready(MainApp, port, addr=None, family=None, backlog=1048576, reuse_port=True, debug=False, mmfile=None, **kwargs):
        #import pymysql
        #pymysql.install_as_MySQLdb()
        global DEBUG

        import sys
        sys.argv.extend(['--%s=%s' % (k, v) for k, v in {
            'logging': 'debug' if DEBUG else 'error',
            'log_rotate_mode': 'time',
            'log_file_prefix': 'logs/server.%s.log' % port,
            'log_file_num_backups': 30,
            'log_rotate_interval': 1,
            'log_file_max_size': 100 * 1000 * 1000,
            'log_to_stderr': False
        }.items()])

        from tornado import options, locale, log
        import finup_model,handlers
#        options.parse_config_file("server.conf")
        options.define("port", default=finup_model.PORT, help="port to listen on")
        remain_args = options.parse_command_line()
        locale.get()

        settings = {
            'gzip': True,
            'static_url_prefix': "/yihao01-face-recognize/static/",
            'template_path': os.path.join((os.path.dirname(__file__)),'template'),
            'static_path': os.path.join((os.path.dirname(__file__)),'static'),
            'websocket_ping_interval':1,
            'websocket_ping_timeout':5,
            'max_message_size': 16 * 1024 * 1024,
            'cookie_secret': 'abaelhe.0easy.com',
            'cookie_domain': '.0easy.com',
            'token':True,
            'debug': debug,
            'autoreload': debug,
        }

        log.app_log.info( 'Listen:%s:%s\nConfigs:\n%s\nRunning.\n' % (addr, finup_model.PORTS,
            ''.join(['  %s = %s\n' % (k, v) for k, v in reversed(sorted(options.options.items(), key=lambda i: i[0]))  if k != 'help'])))

        web_handlers = [
            (r'/finup', handlers.FinupHandler),
            (r'/sys', handlers.SysHandler),

            #            (r'/sock', handlers.SockHandler),
#            (r'/yihao01-face-recognize/target', receiver.TargetHandler),
        ]

        sock_handlers = []
        app = MainApp(handlers=web_handlers + sock_handlers, **settings)
        port = int(port)
        app.listen(port, addr=finup_model.ADDR, debug=debug, reuse_port=reuse_port, **kwargs)


    def listen(self, port, addr=None, family=None, debug=False, reuse_port=True, **kwargs):
        from tornado import httpserver, log, ioloop
        import struct

        flags = 0
        if hasattr(socket, 'TCP_DEFER_ACCEPT'):
            flags |= socket.TCP_DEFER_ACCEPT
        if hasattr(socket, 'TCP_QUICKACK'):
            flags |= socket.TCP_QUICKACK

        sockets = netutil.bind_sockets(port, address=addr, backlog=1048576, reuse_port=reuse_port, flags=None if flags == 0 else flags)
        for sock in sockets:
            if not sock.family == socket.AF_INET:
                continue
            #if hasattr(socket, 'SO_LINGER'):
            #    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 0,0))

            #sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, struct.pack('i', 0))
            #sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, struct.pack('i', 0))
            for i in range(16,0,-1):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, struct.pack('i', i * 1024 * 1024))
                    print('server sock.SO_RCVBUF: %dM' %(i))
                    break
                except:
                    continue
            for i in range(16,0,-1):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, struct.pack('i', i * 1024 * 1024))
                    print('server sock.SO_SNDBUF: %dM' %(i))
                    break
                except:
                    continue

        self.server = httpserver.HTTPServer(self, no_keep_alive=False, **kwargs)
        self.server.add_sockets(sockets)
        self.server.start(1)

        try:
            ioloop.IOLoop.current().start()
        except (KeyboardInterrupt, SystemExit):
            log.app_log.info("\nSystem Exit.\n")
            sys.exit(0)
        except:
            log.app_log.error("System Exception:\n", exc_info=True)
            sys.exit(-1)
        finally:
            self.on_close()

    def on_close(self):
        pass

SERVICE_STR = """
请提供调试文件(程序运行目录里 "%s")与 凡普金科支持:
    何义军, 13522696712, <abaelh@icloud.com>
    凡普金科 | www.finupgroup.com | FF business
感谢你的信赖。我们会尽快解决。

"""

def model_initializer(procs=None, port=None, addr=None, reuse_port=True):

    global DEBUG
    global CPU_COUNT
    global THIS_DIRNAME
    global listen_port

    port = 8888
    argv = []
    reloader = False
    import finup_model
    for i in sys.argv:
        if i.startswith('--reload'):
            reloader = True
            continue
        if i.startswith('--debug'):
            DEBUG = True
            continue
        if i.startswith('--port'):
            port = int(i.partition('=')[-1])
            continue

    if reloader:
        mod = None
        path = os.sep.join([THIS_DIRNAME, 'reloader.so'])
        if os.path.exists(path):
            mod = imp.load_dynamic('reloader', path)
        else:
            path = os.sep.join([THIS_DIRNAME, 'reloader.py'])
            mod = imp.load_source('reloader', path)
        mod.reloader()
        return

    if not DEBUG:
        finup_model.OTP_init()

    process_num = 1 if DEBUG else (CPU_COUNT if procs is None else procs)
    ports = [(int(port)+i) for i in range(process_num)]
    print('\nDebug:%s, Cpus:%s, Listen: %s:%s\n' % (DEBUG, process_num, finup_model.ADDR, ports))

    if not DEBUG:
        port = fork_processes(ports)
    from tornado import ioloop
    iol = ioloop.IOLoop.current()
    #assert iol._running is False, 'Fork must before any IOLoop instance()'
    import socket
    reload_module(socket)
    from tornado import options, locale, log
    reload_module(options)
    reload_module(log)
    from handlers import finup_handler
    reload_module(finup_handler)

    import finup_model
    reload_module(finup_model)
    if addr is not None:
        finup_model.ADDR = addr
    finup_model.PORT = port
    finup_model.PORTS.extend([i for i in ports if i not in finup_model.PORTS])
    for i in sys.argv:
        if i.startswith('--redis='): ## --redis='redis://abc:123@10.10.210.83:6379/0'
            redis= i.rpartition('=')[-1]
            u = six.moves.urllib_parse.urlsplit(('redis://' +redis) if '://' not in redis else redis)
            finup_model.REDIS_SETTINGS.update({'host':u.hostname, 'port':int(u.port or 6379), 'password': u.password})
            print('REDIS: %s' % finup_model.REDIS_SETTINGS)
            continue

        if not i.startswith('--port=') and not i.startswith('--debug') and not i.startswith('--redis'):
            argv.append(i)
            continue
    sys.argv = argv

    finup_model.reload_modules(system=True)

    dumpfile = os.sep.join([THIS_DIRNAME, 'logs', 'support%s.dat' % ('' if DEBUG else ('.%s' %listen_port)  ) ])
    max_buffer = 4096*1024*1024
    max_chunk = 128*1024*1024
    try:
        MainApplication.ready(port, addr=finup_model.ADDR, debug=DEBUG,
		reuse_port=reuse_port,
		max_body_size=max_buffer,
		max_buffer_size=max_buffer,
		chunk_size=max_chunk,
		decompress_request=True,
		idle_connection_timeout=5000, body_timeout=1200000)
        ## decompress_request=True, 自动解压GZIP: curl -s -F 'files=@./fanpu_20180403_v2.txt;type=csv/gzip' 'http://127.0.0.1:8889/finup?model=1&stats=1' > ./data.8889.txt  &
    except KeyboardInterrupt:
        print("W: interrupt received, stopping…")
    except:
        try:
            with open(dumpfile, 'wb') as support_file:
                support_file.write('>>>> %s\n' % datetime.datetime.now().isoformat())
                finup_model.print_exc(file=support_file)
                support_file.write(SERVICE_STR % dumpfile)
                support_file.flush()
        except:
            pass







def gen_model_py(model_name, model_object_in_memory, *other_objects_in_memory):
    template = """#!/usr/bin/env python
# -*-coding:utf-8-*-
import six,os,sys,pickle,base64

%s

def predict_proba(items):
    '''if MODEL PREPROCESS / FEATURE ENGINEERING required, write below before the "return ..." line. '''
    return model.predict_proba(items)
"""
    import six, os, sys, pickle, base64
    to_bytes = lambda s: s.encode('utf-8') if isinstance(s, six.text_type) else s
    dump_object = lambda obj: base64.b64encode(pickle.dumps(obj, protocol=2))
    load_template = "%s = pickle.loads(base64.b64decode(%r.strip()))"

    loads = []
    load_model_str = load_template % ('PKL_MODEL', dump_object(model_object_in_memory))
    loads.append(to_bytes(load_model_str))

    for idx, obj in enumerate(other_objects_in_memory):
        obj_name = 'PKL_OBJ_%s' % idx
        obj_str = dump_object(obj)
        load_obj_str = load_template % (obj_name, obj_str)
        loads.append(to_bytes(load_obj_str))

    with open('./%s.py' % model_name, 'wb') as f:
        strs = to_bytes(template % '\n'.join(loads))
        f.write(strs)
        f.flush()
