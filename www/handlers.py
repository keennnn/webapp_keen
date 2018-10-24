# -*- coding: utf-8 -*-
"""
Created on Mon Oct 22 16:24:01 2018

@author: keen_liu
"""

'''
URL handlers
'''

import re, time, json, logging, hashlib, base64, asyncio

from aiohttp import web


from coroweb import get, post
from models import User, Blog, Comment, next_id
from apis import APIValueError, APIError
from config import configs



'''
#test for day7
@get('/')
async def index(request):
    users = await User.findAll()
    return {
            '__template__': 'test.html',
            'users': users            
    }
'''

#test for day8
@get('/')
async def index(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time()-3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time()-7200)
    ]
    return {
        '__template__': 'blogs.html',
        'blogs': blogs
    }


#test for day9
@get('/api/users')
async def api_get_users():
    users = await User.findAll(orderBy='created_at desc')
    for u in users:
        u.passwd = '******'
    return dict(users=users)



#test for day10
COOKIE_NAME = 'awesession'   #用来在set_cookie中命名
_COOKIE_KEY = configs.session.secret  #导入默认设置

#正则表达式我是参考这里的(http://www.cnblogs.com/vs-bug/archive/2010/03/26/1696752.html)
_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')    

#制作cookie的数值，即set_cookie的value
def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    # build cookie string by: id-expires-sha1
    # build cookie string by: id-expires-sha1（id-到期时间-摘要算法）
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY) #s的组成：id, passwd, expires, _COOKIE_KEY
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]  #再把s进行摘要算法
    return '-'.join(L)


#显示注册页面
@get('/register')
async def register():
    return {
        '__template__': 'register.html'
    }

#制作用户注册api
#注意这里路径是'/api/users'，而不是`/register`
#其实当用户填写完注册信息，点击提交按钮的时候，就会转到这个path的，这个是在register.html文件里面配置的
@post('/api/users')
async def api_register_user(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = await User.findAll(where='email=?', args=[email])  #查询邮箱是否已注册，查看ORM框架源码
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    #接下来就是注册到数据库上,具体看会ORM框架中的models源码
    #这里用来注册数据库表id不是使用Use类中的默认id生成，而是调到外部来，原因是后面的密码存储摘要算法时，会把id使用上。
    uid = next_id()
    print('uid:', uid)
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    # make session cookie:
    #制作cookie返回浏览器客户端
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)  #max_age是cookie信息有效的时间86400s就是24hours
    user.passwd = '******'  #掩盖passwd
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

"""
总结一下具体流程，当用户在主页页面（就是前一章那个）点击注册时，会跳转到后缀为/register的URL,这时负责后缀/register的URL处理函数返回注册页面，当用户填写好消息并提交时，会先通过javascript，这段javascript功能有几个： 
1、初步检验信息（如检验邮箱格式是否正确，信息是否有留白，密码长度，两次密码是否一致等等，但不懂为何有些信息这里检验了一遍去到python的注册API那里又检验一次）。 
2、初次对密码进行摘要算法（后面python存储信息时又对密码进行了一次摘要算法，在作为cookie返回客户端时又进行了一次摘要算法，主要是为了安全） 
3、进行摘要算法过后，转去后缀为/api/users的URL，即此时才转到注册用户的API。 
4、注册用户的API运行完过后，重回首页。

"""













