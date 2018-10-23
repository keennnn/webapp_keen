# -*- coding: utf-8 -*-
"""
Created on Wed Oct 17 11:28:17 2018

@author: keen_liu
"""


'''
Models for user, blog, comment

'''

import time, uuid

from orm import Model, StringField, BooleanField, FloatField, TextField

def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)

class User(Model):
    __table__ = 'users'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    email = StringField(ddl='varchar(50)')
    passwd = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(500)')
    created_at = FloatField(default=time.time)

class Blog(Model):
    __table__ = 'blogs'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    name = StringField(ddl='varchar(50)')
    summary = StringField(ddl='varchar(200)')
    content = TextField()
    created_at = FloatField(default=time.time)

class Comment(Model):
    __table__ = 'comments'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    blog_id = StringField(ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(default=time.time)

"""
SQL生成Models脚本
在MySQL command line client命令行输入命令输入类似命令就可以运行sql脚本
mysql> source D:\keen\python\python3\projects\awesome-python3-webapp\www\Models_
init_schema.sql


-- schema.sql
DROP DATABASE if EXISTS awesome;

CREATE DATABASE awesome;
USE awesome;

-- grant 数据用户，查询、插入、更新、删除 数据库中相应database的表数据的权利。
-- 新建一个user（account）：DATABASE：awesome, user: www-data, host: localhost, password: www-data
grant select, insert, update, delete on awesome.* to 'www-data'@'localhost' identified by 'www-data';

create table users (
    `id` varchar(50) not null,
    `email` varchar(50) not null,
    `passwd` varchar(50) not null,
    `admin` bool not null,
    `name` varchar(50) not null,
    `image` varchar(500) not null,
    `created_at` real not null,
    unique key `idx_email` (`email`),
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=innodb default charset=utf8;

create table blogs (
    `id` varchar(50) not null,
    `user_id` varchar(50) not null,
    `user_name` varchar(50) not null,
    `user_image` varchar(500) not null,
    `name` varchar(50) not null,
    `summary` varchar(200) not null,
    `content` mediumtext not null,
    `created_at` real not null,
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=innodb default charset=utf8;

create table comments (
    `id` varchar(50) not null,
    `blog_id` varchar(50) not null,
    `user_id` varchar(50) not null,
    `user_name` varchar(50) not null,
    `user_image` varchar(500) not null,
    `content` mediumtext not null,
    `created_at` real not null,
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=innodb default charset=utf8;

"""


"""
example to test :编写数据访问代码
测试通过ORM框架操作数据库

import asyncio, logging

logging.basicConfig(level=logging.INFO)

import orm
from models import User, Blog, Comment




if __name__ == '__main__':
    
    #创建异步事件的句柄
    loop = asyncio.get_event_loop()
    
    async def test(loop):
        await orm.create_pool(loop=loop, user='www-data', password='www-data', db='awesome')
        user = User(name='Test2', email='test@example2.com', passwd='1234567890', image='about:blank')
        await user.save()
        logging.info('pass to insert user info to database')
        #rs = await User.findAll()
        #print(rs)
        await asyncio.sleep(20)
        await orm.destroy_pool()  #关闭pool
    
    loop.run_until_complete(test(loop))
    loop.close()
    
"""





















