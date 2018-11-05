# -*- coding: utf-8 -*-
"""
Created on Mon Oct 22 16:24:01 2018

@author: keen_liu
"""

'''
URL handlers
'''


"""
后端API包括：
获取日志：GET /api/blogs
创建日志：POST /api/blogs
修改日志：POST /api/blogs/:blog_id
删除日志：POST /api/blogs/:blog_id/delete
获取评论：GET /api/comments
创建评论：POST /api/blogs/:blog_id/comments
删除评论：POST /api/comments/:comment_id/delete
创建新用户：POST /api/users
获取用户：GET /api/users

管理页面包括：
评论列表页：GET /manage/comments
日志列表页：GET /manage/blogs
创建日志页：GET /manage/blogs/create
修改日志页：GET /manage/blogs/
用户列表页：GET /manage/users

用户浏览页面包括：
注册页：GET /register
登录页：GET /signin
注销页：GET /signout
首页：GET /
日志详情页：GET /blog/:blog_id
"""

import re, time, json, logging, hashlib, base64, asyncio

from aiohttp import web

import markdown2

from coroweb import get, post
from models import User, Blog, Comment, next_id
from apis import APIValueError, APIError, Page, APIResourceNotFoundError, APIPermissionError
from config import configs


# test for day10
COOKIE_NAME = 'awesession'   #用来在set_cookie中命名
# 数据库保存的session
_COOKIE_KEY = configs.session.secret  #导入默认设置

# 正则表达式我是参考这里的(http://www.cnblogs.com/vs-bug/archive/2010/03/26/1696752.html)
# 匹配邮箱
_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
# 匹配哈希
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')


# 制作cookie的数值，即set_cookie的value
def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    # build cookie string by: id-expires-sha1
    # build cookie string by: id-expires-sha1（id-到期时间-摘要算法）
    # 存储cookie的截止时间
    expires = str(int(time.time() + max_age))
    # 用户cookie = ID + 密码 + 截止时间 + 数据库的session
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY) #s的组成：id, passwd, expires, _COOKIE_KEY
    # 加密，进一步包装
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]  #再把s进行摘要算法
    return '-'.join(L)


# 定义从cookie中找到user的信息的函数
# 从request cookie中拿到的cookie_str是这种类似格式的，这个格式其实是我们通过user2cookie()函数生成以后传给浏览器客户端的
# 001540366298304cc1f45e7f9634d0fb3a0d81d78945882000-1540452698-d42395f5ea4bd626a80ab56dfd96c98834774eec
async def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid.
    '''
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')  # 拆分字符串(D)
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if float(expires) < time.time():  # 查看是否过期,这里廖大用的是int，但是字符串用int的时候，只能全是数字，不能含小数点
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


# text文本到html格式的转换（防止一些特殊符号的时候不会是乱码）
def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)


# 定义检查请求是否有用户以及该用户是否有权限的函数
# 检测有否登录且是否为管理员
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


'''-----思路： 前端页面带有模板，具体操作响应用后端API处理，然后返回响应的页面'''
'''用户浏览页面包括：
注册页：GET /register
登录页：GET /signin
注销页：GET /signout
首页：GET /
日志详情页：GET /blog/:blog_id'''

# 主页(根url)
@get('/')
async def index(*, page='1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    page = Page(num)
    if num == 0:
        blogs = []
    else:
        blogs = await Blog.findAll(orderBy='created_at desc', limit=(page.offset, page.limit))
    return {
        '__template__': 'blogs.html',
        'page': page,
        'blogs': blogs
    }


# 日志详情页：GET /blog/:blog_id'''
# 获取某篇博客具体内容页面（包括评论等）
# 类似这种http://localhost:9000/blog/0015403778437085c5a48e658554c0fa42d7b4afeb66a60000
@get('/blog/{blog_id}')
async def get_blog(blog_id):
    logging.info('blog_id: %s' % blog_id)
    blog = await Blog.find(blog_id)
    comments = await Comment.findAll('blog_id=?', [blog_id], orderBy='created_at desc')
    for c in comments:
        c.html_content = text2html(c.content)
    # markdown将txt转化成为html格式
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }


# 注册页：GET /register
@get('/register')
async def register():
    return {
        '__template__': 'register.html'
    }


# 登录页：GET /signin
@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }


# 注销页：GET /signout
# signout回到index页面
@get('/signout')
def signout(request):
    referer = request.headers.get('Referer', None)
    r = web.HTTPFound(referer or '/')   # request消息中没有携带reference信息的话就回到 主页‘/’
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out')
    return r






'''----------------管理员页面------------------------------------------------'''
'''
管理页面包括：
评论列表页：GET /manage/comments
日志列表页：GET /manage/blogs
创建日志页：GET /manage/blogs/create
修改日志页：GET /manage/blogs/edit
用户列表页：GET /manage/users
'''


# 返回重定向url ===> manage/comments
@get('/manage/')
def manage():
    return 'redirect:/manage/comments'


# 评论列表页：GET /manage/comments
@get('/manage/comments')
def manage_comments(*, page='1'):
    return {
        '__template__': 'manage_comments.html',
        'page_index': get_page_index(page)
    }


# 日志列表页：GET /manage/blogs
@get('/manage/blogs')
def manage_blogs(*, page='1'):
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page)
    }


# 创建日志页：GET /manage/blogs/create
# 创建博客页，action ===> /api/blogs
# 显示创建blog页面，点击保存提交按钮以后会post到'/api/blogs'，就调用后端api_create_blog()函数处理URL
@get('/manage/blogs/create')
def manage_create_blog():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs'
    }


# 修改日志页：GET /manage/blogs/edit
# 修改某篇博客页，action ===> /api/blogs/{id} post到'/api/blogs/{blog_id}' URL调用后端api_update_blog()进行处理
# manage_blogs.html里面edit_blog()函数 是get URL '/manage/blogs/edit?id=' + blog.id
# 所有处理GET URL时候在'/manage/blogs/edit'后面有命名关键字参数id=''
@get('/manage/blogs/edit')
def manage_edit_blog(*, id):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': id,
        'action': '/api/blogs/%s' % id
    }


# 用户列表页：GET /manage/users
@get('/manage/users')
def manage_users(*, page='1'):
    return {
        '__template__': 'manage_users.html',
        'page_index': get_page_index(page)
    }






#-------------------------------------后端api----------------------------------------
'''
后端API包括：
获取日志：GET /api/blogs
创建日志：POST /api/blogs
修改日志：POST /api/blogs/:blog_id
删除日志：POST /api/blogs/:blog_id/delete
获取评论：GET /api/comments
创建评论：POST /api/blogs/:blog_id/comments
删除评论：POST /api/comments/:comment_id/delete
创建新用户：POST /api/users
获取用户：GET /api/users
'''


# 获取评论：GET /api/comments
# 但是这个应是获取的是所有的comments啊，并不是摸个blog对应的所有comments的
@get('/api/comments')
async def api_comments(*, page='1'):
    page_index = get_page_index(page)
    num = await Comment.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, comments=())
    comments = await Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)


# 创建评论：POST /api/blogs/:blog_id/comments
@post('/api/blogs/{blog_id}/comments')
async def api_create_comment(blog_id, request, *, content):
    user = request.__user__
    if user is None:
        raise APIPermissionError('Please signin first')
    if not content or not content.strip():
        raise APIValueError('content')
    blog = await Blog.find(blog_id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    print('user image:', user.image)
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image,
                      content=content.strip())
    await comment.save()
    return comment


# 删除评论：POST /api/comments/:comment_id/delete
# 删除评论，需要检查是否有权限
@post('/api/comments/{comment_id}/delete')
async def api_delete_comments(comment_id, request):
    check_admin(request)
    c = await Comment.find(comment_id)
    if c is None:
        raise APIResourceNotFoundError('Comment')
    await c.remove()
    return dict(id=comment_id)


# 获取用户：GET /api/users
@get('/api/users')
async def api_get_users(*, page='1'):
    page_index = get_page_index(page)
    num = await User.findNumber('count(id)')
    p = Page(num, page_index)
    if p == 0:
        return dict(page=p, users=())
    users = await User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    for u in users:
        u.passwd = '******'
    return dict(page=p, users=users)


# 创建新用户：POST /api/users
# 注意这里路径是'/api/users'，而不是`/register`
# 其实当用户填写完注册信息，点击提交按钮的时候，就会转到这个path的，URL'POST /api/users'是在register.html文件里面配置的
@post('/api/users')
async def api_register_user(*, email, name, passwd):    # 注册页面时需要填写的信息：邮箱，用户名，密码
    if not name or not name.strip():   # str.strip([chars])移除字符串头尾指定的字符(默认空格)
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = await User.findAll(where='email=?', args=[email])  # 查询邮箱是否已注册，查看ORM框架源码
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    # 接下来就是注册到数据库上,具体看会ORM框架中的models源码
    # 这里用来注册数据库表id不是使用Use类中的默认id生成，而是调到外部来，原因是后面的密码存储摘要算法时，会把id使用上。
    uid = next_id()
    # 加密形式:next_id():passwd，数据库中保存其摘要hexdigest()。与上面验证的时候要保持一致
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    # make session cookie:
    # 制作cookie返回浏览器客户端
    r = web.Response()
    # set_cookie(name,value,*,path='/',expires=None,domain=None,max_age=None,secure=None,httponly=None,version=None)
    # name:cookie名称(str),value:cookie值(str),expires在http1.1被遗弃，使用max_age代替
    # path(str):指定Cookie应用于的url的子集，默认'/'
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)  # max_age是cookie信息有效的时间86400s就是24hours
    user.passwd = '******'  # 掩盖passwd
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


# 获取日志：GET /api/blogs
# 从数据库中读取blogs内容发送给manage_blogs.html的VUE MVVM框架
@get('/api/blogs')
async def api_blogs(*, page='1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=())
    blogs = await Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)


# GET /api/blogs/{blog_id}
# 获取某篇博客
# 在修改日志页：GET /manage/blogs/edit修改某篇博客页以后，action ===> /api/blogs/{id}
@get('/api/blogs/{blog_id}')
async def api_get_blog(*, blog_id):
    blog = await Blog.find(blog_id)
    return blog


# 创建日志：POST /api/blogs
# 在创建blog页面（manage_blog_edit.html），点击保存提交按钮以后会post到'/api/blogs'，就调用api_create_blog()函数处理URL
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


# 修改日志：POST /api/blogs/:blog_id
# 对应的管理页面： 修改日志页：GET /manage/blogs/edit， manage_blog_edit.html
@post('/api/blogs/{blog_id}')
async def api_update_blog(blog_id, request, *, name, summary, content):
    check_admin(request)
    blog = await Blog.find(blog_id)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    blog.name = name.strip()
    blog.summary = summary.strip()
    blog.content = content.strip()
    await blog.update()
    return blog


@post('/api/blogs/{blog_id}/delete')
async def api_delete_blog(request, *, blog_id):
    check_admin(request)
    blog = await Blog.find(blog_id)
    if blog is None:
        pass
    await blog.remove()
    return dict(id=blog_id)


# 登录页：GET /signin 对应的模板是signin.html，填写email passwd信息点击提交以后，会post '/api/authenticate' 调用后端api_authenticate()进行处理
# 验证登录信息
@post('/api/authenticate')
async def api_authenticate(*, email, passwd):
    if not email:
        raise APIValueError('email')
    if not passwd:
        raise APIValueError('passwd')
    users = await User.findAll(where='email=?', args=[email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]  # 此时finall得出来的数值是一个仅含一个dict的list,就是sql语句返回什么类型的数据自己忘了
    # 把登录密码转化格式并进行摘要算法
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if sha1.hexdigest() != user.passwd:   # 与数据库密码比较
        raise APIValueError('password', 'Invaild password')
    # 制作cookie发送给浏览器，这步骤与注册用户一样
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = "******"
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


























