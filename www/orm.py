# -*- coding: utf-8 -*-
"""
Created on Mon Oct 15 15:21:46 2018

@author: keen_liu
"""


import asyncio, logging
import aiomysql


logging.basicConfig(level=logging.INFO)

def log(sql, args):
    if args==None:
        logging.info('SQL: %s' % sql)
    else:
        true_sql = sql.replace('?', '%s') % tuple(args)
        logging.info('SQL: %s' % true_sql)


#create connection pool for aiomysql
async def create_pool(loop, **kw): #这里的**kw是一个dict
    logging.info('Create database connection pool ...')
    global __pool
    #dict有一个get方法，如果dict中有对应的value值，则返回对应于key的value值，否则返回默认值，例如下面的host，如果dict里面没有
    #'host',则返回后面的默认值，也就是'localhost'
    #这里有一个关于Pool的连接，讲了一些Pool的知识点，挺不错的，点击打开链接，下面这些参数都会讲到，以及destroy__pool里面的
    #https://aiomysql.readthedocs.io/en/latest/pool.html
    #wait_closed()  
    __pool = await aiomysql.create_pool(
            host = kw.get('host', 'localhost'),
            port = kw.get('port', 3306),
            user = kw['user'],
            password = kw['password'],
            db = kw['db'],
            charset = kw.get('charset', 'utf8'),
            autocommit = kw.get('autocommit', True),  #默认自动提交事务，不用手动去提交事务
            maxsize = kw.get('maxsize', 10),
            minsize = kw.get('minsize', 1),
            loop = loop  #loop – is an optional event loop instance, asyncio.get_event_loop() is used if loop is not specified.
        )
async def destroy_pool():
    global __pool
    if __pool is not None :
        __pool.close()  #关闭进程池,The method is not a coroutine,就是说close()不是一个协程，所有不用yield from
        await __pool.wait_closed() #但是wait_close()是一个协程，所以要用yield from,到底哪些函数是协程，上面Pool的链接中都有
    
#select操作
async def select(sql, args, size=None):
    log(sql, args)
    global __pool
    async with __pool.get() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql.replace('?', '%s'), args or ())
            if size:
                rs = await cur.fetchmany(size)
            else:
                rs = await cur.fetchall()
        logging.info('rows returned: %s' % len(rs))
        return rs

# 封装INSERT, UPDATE, DELETE操作
# 语句操作参数一样，所以定义一个通用的执行函数，只是操作参数一样，但是语句的格式不一样
# 返回操作影响的行号
async def execute(sql, args, autocommit=True):
    log(sql, args)
    global __pool
    async with __pool.get() as conn:
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                affected = cur.rowcount
            if not autocommit:
                await conn.commit()
        except BaseException as e:
            if not autocommit:
                await conn.rollback()
            raise
        return affected

# 这个函数主要是把查询字段计数 替换成sql识别的?
# 比如说：insert into  `User` (`password`, `email`, `name`, `id`) values (?,?,?,?)  看到了么 后面这四个问号   
def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ','.join(L)



# 定义Field类，负责保存(数据库)表的字段名和字段类型
class Field(object):
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default
    
    def __str__(self):
        # 返回 表名字 字段名 和字段类型
        return '<%s %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

# 定义数据库中五个存储类型
class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super(StringField, self).__init__(name, ddl, primary_key, default)

# 布尔类型不可以作为主键
class BooleanField(Field):
    def __init__(self,name=None, default=False, ddl='boolean'):
        super(BooleanField, self).__init__(name, ddl, False, default)

class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super(IntegerField, self).__init__(name, 'bigint', primary_key, default)

class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0, ddl='real'):
        super(FloatField, self).__init__(name, ddl, primary_key, default)

class TextField(Field):
    def __init__(self, name=None, default=None):
        super(TextField, self).__init__(name, 'text', False, default)



#metaclass
        # -*-定义Model的元类
 
# 所有的元类都继承自type
# ModelMetaclass元类定义了所有Model基类(继承ModelMetaclass)的子类实现的操作
 
# -*-ModelMetaclass的工作主要是为一个数据库表映射成一个封装的类做准备：
# ***读取具体子类(user)的映射信息
# 创造类的时候，排除对Model类的修改
# 在当前类中查找所有的类属性(attrs)，如果找到Field属性，就将其保存到__mappings__的dict中，同时从类属性中删除Field(防止实例属性遮住类的同名属性)
# 将数据库表名保存到__table__中
 
# 完成这些工作就可以在Model中定义各种数据库的操作方法
# metaclass是类的模板，所以必须从`type`类型派生：
class ModelMetaclass(type):
    # __new__控制__init__的执行，所以在其执行之前
    # cls:代表要__init__的类，此参数在实例化时由Python解释器自动提供(例如下文的User和Model)
    # bases：代表继承父类的集合
    # attrs：类的方法集合
    def __new__(mcls, name, bases, attrs):
        #  排除model 是因为要排除对model类的修改
        if name=='Model':
            return type.__new__(mcls, name, bases, attrs)
        # 获取table名称:
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))
        # 获取所有的Field和主键名, 放到mappings中:
        mappings = dict()  # 保存属性和列的映射关系
        fields = []   ##field保存的是除主键外的属性名
        primaryKey = None
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('  found mapping: %s ==> %s' % (k, v))
                mappings[k] = v
                if v.primary_key:
                    # 找到主键:
                    # 这里很有意思 当第一次主键存在primaryKey被赋值 后来如果再出现主键的话就会引发错误
                    if primaryKey:  #一个表只能有一个主键，当再出现一个主键的时候就报错
                        raise RuntimeError('Duplicate primary key for field: %s' % k)
                    primaryKey = k  # 也就是说主键只能被设置一次
                else:
                    fields.append(k)
        if not primaryKey:  #如果主键不存在也将会报错，在这个表中没有找到主键，一个表只能有一个主键，而且必须有一个主键
            raise RuntimeError('Primary key not found.')
         # w下面位字段从类属性中删除Field 属性
        for k in mappings.keys():
            attrs.pop(k)
        
        # 保存除主键外的属性为''列表形式
        # 将除主键外的其他属性变成`id`, `name`这种形式，关于反引号``的用法，可以参考点击打开链接
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        attrs['__mappings__'] = mappings # 保存属性和列的映射关系
        attrs['__table__'] = tableName    # 保存表名
        attrs['__primary_key__'] = primaryKey # 主键属性名
        attrs['__fields__'] = fields # 除主键外的属性名
        # 构造默认的增删改查 语句
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(mcls, name, bases, attrs)        


# 定义ORM所有映射的基类：Model
# Model类的任意子类可以映射一个数据库表
# Model类可以看作是对所有数据库表操作的基本定义的映射
 
 
# 基于字典查询形式
# Model从dict继承，拥有字典的所有功能，同时实现特殊方法__getattr__和__setattr__，能够实现属性操作
# 实现数据库操作的所有方法，定义为class方法，所有继承自Model都具有数据库操作方法
class Model(dict, metaclass=ModelMetaclass):
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)
    

    #__get__attr()和__setattr__()其实是为了实现如下功能的：
    #加入存在user['passwd'] = passwd123, 正常的dict只能通过user['passwd'] = passwd456的方式来修改value值，
    #但是重新定义这两个方法以后，就可以通过user.passwd = 'xxxx'来修改访问key对应的value值
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'"% key)

    def __setattr__(self, key, value):
        self[key] = value
        
    def getValue(self, key):
        return getattr(self, key, None)
    
    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field_value = self.__mappings__[key]
            if field_value.default is not None:
                value = field_value.default() if callable(field_value.default) else field_value.default
                logging.debug('using default value for %s:%s' % (key, str(value)))
                setattr(self, key, value)
        return value
    
    # 类方法有类变量cls传入，从而可以用cls做一些相关的处理。并且有子类继承时，调用该类方法时，传入的类变量cls是子类，而非父类。
    @classmethod
    async def findAll(cls, where=None, args=None, **kw):
        'find objects by where clause'
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
            limit = kw.get('limit', None)
            if limit is not None:
                sql.append('limit')
                if isinstance(limit, int):
                    sql.append('?')
                    args.append(limit)
                elif isinstance(limit, tuple) and len(limit)==2:
                    #两个参数的话，就代表这第一个参数是offset(如果没有默认是0)18代表是从19开始算起， 第二个参数10代表返回的最大行数
                    #举例： sql语句是这样的： select * from table1 limit 18, 10；
                    sql.append('?, ?')
                    args.extend(limit)
                else:
                    raise ValueError('Invalid limit value: %s' % str(limit))
        rs = await select(' '.join(sql), args)
        # **r 是关键字参数，构成了一个cls类的列表，其实就是每一条记录对应的类实例
        return [cls(**r) for r in rs]

    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        ' find number by select and where. '
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        print('KEEN  SQL', str(sql))
        print('keen  args', args)
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @classmethod
    async def find(cls, pk):
        'find object by primary key.'
        rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs)==0:
            return None
        return cls(**rs[0])
    
    async def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warn('failed to insert record: affected rows: %s' % rows)
        
    async def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows!=1:
            logging.warn('failed to update by primary key: affected rows: %s' % rows)

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows!=1:
            logging.warn('failed to remove by primarykey: affected rows: %s' % rows)


if __name__ == '__main__':
    class User(Model): #一个类自带前后都有双下划线的方法，在子类继承该类的时候，这些方法会自动调用，比如__init__
        id = IntegerField('id', primary_key=True)
        name = StringField('name')
        email = StringField('email')
        password = StringField('password')
        
    user = User(id=80, name='Tom', email='slysly759@gmail.com', password='54321')
    
    #创建异步事件的句柄
    loop = asyncio.get_event_loop()
    
    async def test():
        await create_pool(loop=loop, host='127.0.0.1', port=3306, user='root', password='keen123456', db='test')
        await user.remove()
        #rs = await User.findAll()
        #print(rs)
        logging.info('asyncio sleep(20)')
        await asyncio.sleep(20)
        await destroy_pool()  #关闭pool
    
    loop.run_until_complete(test())
    loop.close()
    











































