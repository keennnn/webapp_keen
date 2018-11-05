# -*- coding: utf-8 -*-
"""
Created on Tue Oct  9 16:34:21 2018

@author: keen_liu
"""


"""
编写Web App骨架

由于我们的Web App建立在asyncio的基础上，因此用aiohttp写一个基本的app.py：

import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web

def index(request):
    return web.Response(body=b'<h1>Awesome</h1>')

@asyncio.coroutine
def init(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/', index)
    srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
运行python app.py，Web App将在9000端口监听HTTP请求，并且对首页/进行响应：

$ python3 app.py
INFO:root:server started at http://127.0.0.1:9000...
这里我们简单地返回一个Awesome字符串，在浏览器中可以看到效果：

awesome-home

这说明我们的Web App骨架已经搭好了，可以进一步往里面添加更多的东西。

"""


import logging; logging.basicConfig(level=logging.INFO)
import asyncio, os, json, time

from datetime import datetime
from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import orm
from coroweb import add_routes, add_static
from handlers import cookie2user, COOKIE_NAME

'''
在app.py中加入middleware、jinja2模板和自注册的支持：

app = web.Application(loop=loop, middlewares=[
    logger_factory, response_factory
])
init_jinja2(app, filters=dict(datetime=datetime_filter))
add_routes(app, 'handlers')
add_static(app)
'''

# 日志文件简单配置basicConfig(filename/stream,filemode='a',format,datefmt,level)
logging.basicConfig(level=logging.INFO)

def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    options = dict(
        autoescape=kw.get('autoescape', True),   # 默认打开自动转义 转义字符
        block_start_string=kw.get('block_start_string', '{%'),   # 模板控制块的字符串 {% block %}
        block_end_string=kw.get('block_end_string', '%}'),
        variable_start_string=kw.get('variable_start_string', '{{'),   # 模板变量的字符串 {{ var/func }}
        variable_end_string=kw.get('variable_end_string', '}}'),
        auto_reload=kw.get('auto_reload', True)
    )
    path = kw.get('path', None)
    if path is None:
        # 获得模板路径
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja template path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)    # 用文件系统加载器加载模板
    filters = kw.get('filters', None)    # 尝试获取过滤器
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env   # 给Web实例程序绑定模板属性


"""
middleware
middleware是一种拦截器，一个URL在被某个函数处理前，可以经过一系列的middleware的处理。
一个middleware可以改变URL的输入、输出，甚至可以决定不继续处理而直接返回。middleware的用处就在于把通用的功能从每个URL处理函数中拿出来，集中放到一个地方。
"""


async def logger_factory(app, handler):
    async def logger(request):
        # 输出到控制台：收到请求信息的（方法，路径）
        logging.info('Request: %s  %s' % (request.method, request.path))
        # await asyncio.sleep(0.3)
        # 继续处理请求
        return await handler(request)
    return logger
"""
#aiohttp V2.3以后的新式写法，教程为旧式写法(也可以混用)，参数handler是视图函数
from aiohttp.web import middleware
@middleware
async def logger(request, handler):
    # 输出到控制台：收到请求信息的（方法，路径）
    logging.info('Request: %s %s' % (request.method, request.path))
    # 继续处理请求
    return await handler(request)
"""


async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request form: %s ' % str(request.__data__))
        return await handler(request)
    return parse_data


# 继续处理经过logger后的请求
# 提取并解析cookie并绑定在request对象上
async def auth_factory(app, handler):
    async def auth(request):
        # 输出到控制台：检查请求的信息（方法，路径）
        logging.info('check user: %s %s' % (request.method, request.path))
        request.__user__ = None # 初始化

        # -----新增一个查看cookies的输出----------------------
        logging.info(request.cookies)
        # 获取请求的cookie名为COOKIE_NAME的cookie
        cookie_str = request.cookies.get(COOKIE_NAME) # 读取cookie
        # 如果保存有该cookie，则验证该cookie，并返回cookie的user（即请求的账户id）
        if cookie_str:
            user = await cookie2user(cookie_str)
            if user:
                logging.info('set current user: %s' % user.email)
                request.__user__ = user
        # 此处判定/manage/的子url中的请求是否有权限，如果没有则返回signin登陆界面
        if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
            return web.HTTPFound('/signin')
        return await handler(request)
    return auth


# 最终处理请求，返回响应给客户端
async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler...')
        r = await handler(request)
        # 如果经过句柄函数（视图函数）handler处理后的请求是stream流响应的实例，则直接返回给客户端
        if isinstance(r, web.StreamResponse):
            logging.info('return StreamResponse.')
            return r
        # 如果处理后是字节的实例，则调用web.Response并添加头部返回给客户端
        if isinstance(r, bytes):
            logging.info('return bytes directly.')
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        # 如果处理后是字符串的实例，则需调用web.Response并(utf-8)编码成字节流，添加头部返回给客户端
        if isinstance(r, str):
            logging.info('return str.encode(`utf-8`)')
            # 如果开头的字符串是redirect:形式（重定向），则返回重定向后面字符串所指向的页面
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        # 如果处理后是字典的实例.......
        if isinstance(r, dict):
            logging.info('return json or html-models.')
            # day11 show login user，在blog页面显示login user信息
            r['__user__'] = request.__user__
            # 在后续构造视图函数返回值时，会加入__template__值，用以选择渲染的模板
            template = r.get('__template__', None)
            if template is None:
                '''不带模板信息，返回json对象
                ensure_ascii:默认True，仅能输出ascii格式数据。故设置为False
                default: r对象会先被传入default中的函数进行处理，然后才被序列化为json对象
                __dict__: 以dict形式返回对象属性和值的映射，一般的class实例都有一个__dict__属性'''
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                '''get_template()方法返回Template对象，调用其render()方法传入r渲染模板'''
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        # 返回响应码
        if isinstance(r, int) and (600 > r >= 100):
            logging.info('return http response code')
            return web.Response(status=r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and (600 > t >= 100):
                return web.Response(status=t, reason=str(m))
        # default:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response


'''
Blog的创建日期显示的是一个浮点数，因为它是由这段模板渲染出来的：
<p class="uk-article-meta">发表于{{ blog.created_at }}</p>
解决方法是通过jinja2的filter（过滤器），把一个浮点数转换成日期字符串。
filter需要在初始化jinja2时设置
'''


def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)


async def init(loop):

    """ 服务器运行程序：创建web实例程序，该实例程序绑定路由和处理函数，运行服务器，监听端口请求，送到路由处理 """

    '''Application,构造函数 def __init__(self,*,logger=web_logger,loop=None,
                                         router=None,handler_factory=RequestHandlerFactory,
                                         middlewares=(),debug=False)
       使用app时，先将urls注册进router，再用aiohttp.RequestHandlerFactory作为协议簇创建套接字；'''
    # middleware是一种拦截器，一个URL在被某个函数处理前，可以经过一系列的middleware处理
    await orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user='www-data', password='www-data', db='awesome')
    app = web.Application(loop=loop, middlewares=[logger_factory, auth_factory, response_factory])
    # 初始化jinja2模板信息
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    # 添加路径
    add_routes(app, 'handlers')    # 将’handlers‘模块中的URL处理函数注册到app路由中
    # 添加静态路径
    add_static(app)
    # 用make_handler()创建aiohttp.RequestHandlerFactory，用来处理HTTP协议
    '''用协程创建监听服务，其中LOOP为传入函数的协程，调用其类方法创建一个监听服务，声明如下
       coroutine BaseEventLoop.create_server(protocol_factory,host=None,port=None,*,
                                             family=socket.AF_UNSPEC,flags=socket.AI_PASSIVE
                                             ,sock=None,backlog=100,ssl=None,reuse_address=None
                                             ,reuse_port=None)
        await返回后使srv的行为模式和LOOP.create_server()一致'''
    # 在app.make_handler()以后会被废弃（deprecated）， 但是我不会改写成最新的用AppRunner()的方式
    srv = await loop.create_server(app.make_handler(), host='127.0.0.1', port=9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

if __name__ == '__main__':
    # 创建协程，LOOP = asyncio.get_event_loop()为asyncio.BaseEventLoop的对象，协程的基本单位
    LOOP = asyncio.get_event_loop()
    LOOP.run_until_complete(init(LOOP))
    LOOP.run_forever()





















