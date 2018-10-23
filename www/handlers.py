# -*- coding: utf-8 -*-
"""
Created on Mon Oct 22 16:24:01 2018

@author: keen_liu
"""

'''
URL handlers
'''

import re, time, json, logging, hashlib, base64, asyncio

from coroweb import get, post
from models import User, Blog, Comment, next_id


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























