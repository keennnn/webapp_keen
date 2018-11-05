# -*- coding: utf-8 -*-
"""
Created on Fri Oct 19 10:14:45 2018

@author: keen_liu
"""


'''
create a webframe

based on :
https://github.com/justoneliu/web_app/blob/d5/www/webframe.py
'''

import asyncio, os, inspect, logging, functools

from urllib import parse
from aiohttp import web
from apis import APIError


'''将aiohttp框架进一步封装成更简明使用的web框架
建立视图函数装饰器，用来存储、附带URL信息，这样子便可以直接通过装饰器，将函数映射成视图函数
例：@get
	def View(request):
		return response
	但此时函数View仍未能从request请求中提取相关的参数，
	需自行定义一个处理request请求的类来封装，并把视图函数变为协程'''


#通过装饰器函数把一个函数映射为一个URL处理函数
#Define decorator @get('/path')
def get(path):
     ' @get装饰器，Define decorator @get("/path") '
     def decorator(func):
         @functools.wraps(func)
         def wrapper(*args, **kw):
             return func(*args, **kw)
         wrapper.__method__ = 'GET'  #给处理函数绑定URL和HTTP method-GET的属性
         wrapper.__route__ = path  #给处理函数绑定URL和HTTP
         return wrapper
     return decorator
             
#Define decorator @post("/path")
def post(path):
    ' @post装饰器，Define decorator @post("/path") '
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'  #给处理函数绑定URL和HTTP method-GET的属性
        wrapper.__route__ = path     #给处理函数绑定URL和HTTP
        return wrapper
    return decorator


def get_required_kw_args(fn):
    ' 将函数所有 没默认值的 命名关键字参数名 作为一个tuple返回 '
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind==inspect.Parameter.KEYWORD_ONLY and param.default==inspect.Parameter.empty:
            # param.kind : describes how argument values are bound to the parameter.
            # KEYWORD_ONLY : value must be supplied as keyword argument, which appear after a * or *args
            # param.default : the default value for the parameter,if has no default value,this is set to Parameter.empty
            # Parameter.empty : a special class-level marker to specify absence of default values and annotations
            args.append(name)
    return tuple(args)


def get_named_kw_args(fn):
    ' 将函数所有的 命名关键字参数名 作为一个tuple返回 '
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind==inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)


'''
补充关于命名关键字参数：
要限制关键字参数的名字，就可以用命名关键字参数  
例如，只接收city和job作为关键字参数。这种方式定义的函数如下：
def person(name, age, *, city, job):
和关键字参数**kw不同，命名关键字参数需要一个特殊分隔符*，*后面的参数被视为命名关键字参数。

'''

def has_named_kw_args(fn): 
    ' 检查函数是否有命名关键字参数，返回布尔值 '
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True
        

def has_var_kw_arg(fn):
    ' 检查函数是否有关键字参数集，返回布尔值, 可变关键字参数'
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True



def has_request_arg(fn):
    '检查函数是否有request函数，返回布尔值。若有request参数，检查该函数是否为该函数的最后一个函数，否则抛出异常'
    sig =  inspect.signature(fn)
    params = sig.parameters  #inspect.Parameter类型的对象， 含有参数名，参数的信息
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue   #退出本次循环
        #如果找到‘request’参数后，还出现位置参数，就会抛出异常
        if found and (param.kind!=inspect.Parameter.VAR_POSITIONAL and param.kind!=inspect.Parameter.KEYWORD_ONLY and param.kind!=inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found

#定义RequestHandler,正式向request参数获取URL处理函数所需的参数
class RequestHandler(object):
    ' 请求处理器，用来封装处理函数 '
    def __init__(self, app, fn):
        # app : an application instance for registering the fn
        # fn : a request handler with a particular HTTP method and path
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)  # 检查函数是否有request参数
        self._has_var_kw_arg = has_var_kw_arg(fn)     # 检查函数是否有关键字参数集
        self._has_named_kw_args = has_named_kw_args(fn)   # 检查函数是否有命名关键字参数
        self._named_kw_args = get_named_kw_args(fn)   # 将函数所有的 命名关键字参数名 作为一个tuple返回
        self._required_kw_args = get_required_kw_args(fn)  # 将函数所有 没默认值的 命名关键字参数名 作为一个tuple返回

    async def __call__(self, request):
        ' 分析请求，request handler,must be a coroutine that accepts a request instance as its only argument and returns a streamresponse derived instance '
        kw = None
        # 当传入的处理函数具有 关键字参数集 或 命名关键字参数 或 request参数
        if self._has_var_kw_arg or self._has_named_kw_args  or self._required_kw_args:
            # POST请求预处理
            if request.method == 'POST':
                # 无正文类型信息时返回
                if not request.content_type:
                    return web.HTTPBadRequest(text='Missing Content-Type.') #这里被廖大坑了，要有text
                ct = request.content_type.lower()
                # 处理JSON类型的数据，传入参数字典中
                if ct.startswith('application/json'):
                    params = await request.json()   #Read request body decoded as json.
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest(text='JSON body must be object.')
                    kw = params
                # 处理表单类型的数据，传入参数字典中
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                # 暂不支持处理其他正文类型的数据
                else:
                    return web.HTTPBadRequest(text='Unsupported Content-Type: %s' % request.content_type)
            # GET请求预处理
            if request.method == 'GET':
                #在World Wide Web上, query string是Uniform Resource Locator (URL)的一部分, 其中包含着需要传给web application的数据.
                #当通过HTTP请求一个页面的时候, 服务器根据请求的URL来在文件系统中定位到请求的文件. 这个文件可能是一个普通的文件, 也可能是一个程序. 
                #如果是第二种情况的话, 服务器需要运行这个程序, 之后把运行的结果作为一个页面返回. query string是传递给这个程序的URL的一部分, 通过对它的使用, 可以允许我们从HTTP的client端发送数据给生成web page的应用程序.
                #Query String Parameters是类似这种格式的
                #site: qq
                #state: CODE-gz-1GeqpT-1RHINN-XHbQexRheevNP7U759169
                #bentry: homepage
                #wl: 1
                #callback: https%3A%2F%2Fwww.sina.com.cn%2F
                #code: 0DCF7C2E544C63529D82C588B403A28C
                qs = request.query_string
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        #Parse a query string given as a string argument.Data are returned as a dictionary. The dictionary keys are the unique query variable names and the values are lists of values for each name.
                        # parse a query string, data are returned as a dict. the dict keys are the unique query variable names and the values are lists of values for each name
                        # a True value indicates that blanks should be retained as blank strings
                        kw[k] = v[0]
        if kw is None:
            kw = dict(**request.match_info)
            # Read-only property with AbstractMatchInfo instance for result of route resolving
        else:
            # 参数字典收集请求参数
            # #当函数参数没有关键字参数时，移去request除命名关键字参数所有的参数信息
            if not self._has_var_kw_arg and self._named_kw_args:
                #remove all unamed kw:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            #check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named args and kw args: %s' % k)
                kw[k] = v                                
                
        if self._has_request_arg:
            kw['request'] = request
        #check required kw # 收集无默认值的关键字参数
        ##假如命名关键字参数(没有附加默认值)，request没有提供相应的数值，报错
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    # 当存在关键字参数未被赋值时返回，例如 一般的账号注册时，没填入密码就提交注册申请时，提示密码未输入
                    return web.HTTPBadRequest(text='Missing argument: %s' % name)
        logging.info('Call with args: %s' % str(kw))
        try:
            # 最后调用URL处理函数，并传入请求参数，进行请求处理
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)
    

def add_static(app):
    ' 添加静态资源路径 '
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static') #获得包含'static'的绝对路径
    # os.path.dirname(os.path.abspath(__file__)) 返回脚本所在目录的绝对路径
    app.router.add_static('/static/', path)  # 添加静态资源路径
    logging.info('add static %s => %s' % ('/static/', path))





#add_route函数用来注册一个URL处理函数（这些URL处理函数后续都是放在handlers.py文件中的）
#其实就是将URL处理函数注册到web服务的路由中
def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @ post not defined in %s.' % str(fn))
    #就是判断如果URL处理函数如果不是coroutine的话就先将其转化为coroutine，满足异步处理的
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ','.join(inspect.signature(fn).parameters.keys())))
    #这句话就是这个函数的重点，app其实是调用aiohttp生成的，这句话就是将URL处理函数注册到app.router.add_route()
    #我的理解其实是将URL函数与具体的app关联起来的
    app.router.add_route(method, path, RequestHandler(app, fn))  #别忘了RequestHandler的参数有两个


#如果多次调用add_route()函数将handlers中的URL处理函数都注册到app.router.add_route()， 会显得很麻烦
# 自动把handlers模块(存放URL处理函数的模块)的所有符合条件的函数注册了:
#把原来的add_route(app, fn)改写成add_route(app, module_name)
def add_routes(app, module_name):
    n = module_name.rfind('.')  #先查看module_name中是否有'.', 例如module_name = test.test1
    if n == (-1):   #n=-1代表着没有在module_name中找到'.'， 说明这个module与该add_routes函数所在的py文件属于同一个目录下
        #__import__(name, globals=None, locals=None, fromlist=(), level=0)
        mod = __import__(module_name, globals(), locals())
    else:
        # __import__(package.module)相当于from package import name，如果fromlist不传入值，则返回package对应的模块，如果fromlist传入值，则返回package.module对应的模块。
        name = module_name[n+1:]  #在module_name中找到'.'， 那么name就是类似例子中的test1
        #getattr(object, name[, default])
        #getattr() 函数用于返回一个对象属性值。
        mod = getattr(__import__(module_name[:n], globals(), locals(),[name]), name)
    for attr in dir(mod):
        if attr.startswith('_'):  #'_'开头代表是module私有的属性，一般情况下是不允许外部使用的
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)  #查看fn函数是否有__method__属性，如果没有的话就返回None
            path = getattr(fn, '__route__', None)
            if method and path:
                #这里要查询path以及method是否存在而不是等待add_route函数查询，因为那里错误就要报错了
                # 对已经修饰过的URL处理函数注册到web服务的路由中
                add_route(app, fn)
            
























