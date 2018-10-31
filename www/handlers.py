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

import markdown2

from coroweb import get, post
from models import User, Blog, Comment, next_id
from apis import APIValueError, APIError, Page, APIResourceNotFoundError, APIPermissionError
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
        'blogs': blogs,
        '__user__': request.__user__
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


#day10   part2 signin
#显示登录页面
@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }

#从request cookie中拿到的cookie_str是这种类似格式的，这个格式其实是我们通过user2cookie()函数生成以后传给浏览器客户端的
#001540366298304cc1f45e7f9634d0fb3a0d81d78945882000-1540452698-d42395f5ea4bd626a80ab56dfd96c98834774eec
async def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid.
    '''
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')  #拆分字符串(D)
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if float(expires) < time.time():  #查看是否过期,这里廖大用的是int，但是字符串用int的时候，只能全是数字，不能含小数点
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('Invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None


#验证登录信息
@post('/api/authenticate')
async def authenticate(*,email,passwd):
    if not email:
        raise APIValueError('email')
    if not passwd:
        raise APIValueError('passwd')
    users = await User.findAll(where='email=?',args=[email])
    if len(users) == 0:
        raise APIValueError('email','Email not exist.')
    user = users[0]#此时finall得出来的数值是一个仅含一个dict的list,就是sql语句返回什么类型的数据自己忘了
    #把登录密码转化格式并进行摘要算法
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if sha1.hexdigest() != user.passwd:#与数据库密码比较
        raise APIValueError('password','Invaild password')
    #制作cookie发送给浏览器，这步骤与注册用户一样
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user,86400), max_age=86400, httponly=True)
    user.passwd = "******"
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii = False).encode('utf-8')
    return r


#signout回到index界面
@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out')
    return r


#day11
    
#检测有否登录且是否为管理员
def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()

def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p


def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)

#查看某个blog
#http://localhost:9000/blog/0015403778437085c5a48e658554c0fa42d7b4afeb66a60000
@get('/blog/{id}')
async def get_blog(id):
    blog = await Blog.find(id)
    comments = await Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }

#显示创建blog页面，点击保存提交按钮以后会post到'/api/blogs'，就调用api_create_blog()函数处理URL
@get('/manage/blogs/create')
def manage_create_blog(request):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs',
        '__user__': request.__user__
    }

@get('/api/blogs/{id}')
async def api_get_blog(*, id):
    blog = await Blog.find(id)
    return blog

#创建blog
@post('/api/blogs')
async def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
    await blog.save()
    return blog















