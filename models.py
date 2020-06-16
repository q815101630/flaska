from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import BadSignature
from datetime import datetime
import enum

import hashlib
from flask_login import UserMixin
from flask import current_app

import bleach
from markdown import markdown

# UserMixin 是在 flask_login.mixins 模块中定义的类
# 该类为 User 类的实例增加了 is_authenticated、is_active、is_anonymous 等属性
# 以及 get_id 等方法
#
# is_authenticated 为 True
# is_anonymous 与之正相反
# is_active 属性默认值为 True ，可以用来封禁用户
#
# User 类的实例的 get_id 的返回值为 str(self.id) ，即 id 属性值的字符串

db = SQLAlchemy()


class Permission:
    FOLLOW = 1
    WRITE = 2
    COMMENT = 4
    MODERATE = 8
    ADMINISTER = 2 ** 7


class Gender(enum.Enum):
    '''gender enumeration'''
    MALE = '男性'
    FEMALE = '女性'
    FUTA = '扶她「ふたなり」'
    OTOKONOKO = '伪娘「おとこのこ」'
    OTHER = 'Other gender not listed'
    UNKNOWN = 'I am not sure'


class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)

    def __repr__(self):
        return '<Role: {}>'.format(self.name)

    @staticmethod
    def insert_roles():
        roles = {
            'User': Permission.FOLLOW | Permission.COMMENT | Permission.WRITE,
            'Moderator': Permission.FOLLOW | Permission.COMMENT |
                         Permission.WRITE | Permission.MODERATE,
            'Administrator': Permission.FOLLOW | Permission.COMMENT |
                             Permission.WRITE | Permission.MODERATE | Permission.ADMINISTER
        }
        # 用户的默认角色的 name 属性值
        default_role_name = 'User'
        for r, v in roles.items():
            # 查询角色数据表中是否有此数据，如果没有就新建一个实例
            # 如果有的话，or 后面的代码不会执行
            role = Role.query.filter_by(name=r).first() or Role(name=r)
            role.permissions = v
            # 如果用户的 name 属性值为 'User' ，则其 default 属性值为 True
            # 否则 default 属性值为 False
            role.default = True if role.name == default_role_name else False
            db.session.add(role)
        db.session.commit()
        print('角色已创建')


class Follow(db.Model):
    '''存储用户关注信息的双主键映射类'''

    __tablename__ = 'follows'

    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'),
                            primary_key=True)  # 关注者 ID
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'),
                            primary_key=True)  # 被关注者 ID
    time_stamp = db.Column(db.DateTime, default=datetime.now)


class User(db.Model, UserMixin):

    def __init__(self, **kw):
        '''default role'''
        # inherit the core of ORM
        super().__init__(**kw)
        self.role = Role.query.filter_by(default=True).first()

    # necessary
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(64), unique=True, index=True)  # index helps to do query in front

    # info related
    _password = db.Column('password', db.String(128))
    confirmed = db.Column(db.Boolean, default=False)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'))
    role = db.relationship('Role', backref=db.backref('users', lazy='dynamic'))

    # personalize
    age = db.Column(db.Integer)
    gender = db.Column(db.Enum(Gender))
    phone_num = db.Column(db.String(32), unique=True)
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    avatar_hash = db.Column(db.String(128))
    small_avatar_hash = db.Column(db.String(128))

    # other
    create_at = db.Column(db.DateTime, default=datetime.utcnow())
    last_seen = db.Column(db.DateTime, default=datetime.utcnow())

    # getter
    @property
    def password(self):
        return self._password

    # token generator
    @property
    def serializer(self, expires_in=3600):
        # 创建令牌生成器，Serializer 类的实例即为令牌生成器
        # 创建该类实例，须提供一个字符串和一个过期时间
        # 过期时间指的是令牌生成器生成的令牌的有效期
        # 令牌生成器的 dumps 方法的参数是字典，返回值是令牌
        # 令牌也叫加密签名，是一串复杂的字符串
        # 将令牌作为令牌生成器的 loads 方法的参数可以获得字典
        return Serializer(current_app.config['SECRET_KEY'], expires_in)

    # func to generate token
    def generate_confirm_user_token(self):
        return self.serializer.dumps({'confirm_user': self.id})  # arg is a dict
        # self.id is primary key

    # check if the user has good token
    def confirm_user(self, token):
        try:
            data = self.serializer.loads(token)  # loads decrypts the token, return the dict
        except BadSignature:
            return False
        if data.get('confirm_user') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)  # update the user info
        db.session.commit()  # complete update
        return True

    @property
    def is_administrator(self):
        return self.role.permissions & Permission.ADMINISTER

    @property
    def is_moderator(self):
        return self.role.permissions & Permission.MODERATE

    @property
    def can_follow(self):
        return self.role.permissions & Permission.FOLLOW

    def has_permission(self, permission):
        return self.role.permissions & permission

    # 为了修复 user\index permission问题做的一个替换has-permission的方法
    def has_permission_replace(self, permission):
        replace_table = {1: 7, 2: 15, 3: 143}
        return replace_table.get(self.role_id) & permission

    @password.setter
    def password(self, pwd):  # 创建实例时自动运行并赋值给_password
        self._password = generate_password_hash(pwd)

    def verify_password(self, pwd):
        return check_password_hash(self._password, pwd)

    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.add(self)
        db.session.commit()

    def gravatar(self, size=256, default='identicon', rating='g'):
        # arg: size, default, rating=[G, PG, R]
        url = 'https://cn.gravatar.com/avatar'
        hash = self.avatar_hash or hashlib.md5(self.email.encode()).hexdigest()
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(
            url=url, hash=hash, size=size, default=default, rating=rating)

    def small_gravatar(self, size=44, default='identicon', rating='g'):
        # arg: size, default, rating=[G, PG, R]
        url = 'https://cn.gravatar.com/avatar'
        hash = self.small_avatar_hash or hashlib.md5(self.email.encode()).hexdigest()
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(
            url=url, hash=hash, size=size, default=default, rating=rating)

    '''
    # relation 到 Follow类，查询所有foreignkey = follow.follower_id的，
    # follower_id 正好是与user.id 联系，即这位用户的id

    #返回一个所有followed的Follow实例表
    followed = db.relationship('Follow', foreign_keys=[Follow.follower_id],
            # 顺便在 Follow类里创建一个 follower属性，链接到这个user.followed 这个用户
            # joined 实现立即从链接查询中加载相关对象
            # 即依从性查询所有的关系
            backref=db.backref('follower', lazy='joined'),
            # cascade：如果User对象被删除，即删除全部相关的follow对象
            #dynamic: 仅获得查询结果，不把数据库加载到内存
            cascade='all, delete-orphan', lazy='dynamic')

    # 此属性可获得数据库中「谁关注了我」的查询结果，它是 Follow 实例的列表
    followers = db.relationship('Follow', foreign_keys=[Follow.followed_id],
            backref=db.backref('followed', lazy='joined'),
            cascade='all, delete-orphan', lazy='dynamic')
            

    def is_following(self, user):
        return self.followed.filter_by(followed_id=user.id).first()

    def is_followed(self, user):
        return self.followers.filter_by(follower_id=user.id).first()

    def follow(self, user):
        if not self.is_following(user):
            # 这里的等于是数值的等于，在Follow 里关于follower-id 让他俩连接关系，即等价
            f = Follow(follower_id=self.id, followed_id=user.id)
            db.session.add(f)
            db.session.commit()

    def unfollow(self, user):
        f = self.followed.filter_by(followed_id=self.id)
        if f:
            db.session.delete(f)
            db.session.commit()
    '''
    followed = db.relationship('Follow', foreign_keys=[Follow.follower_id],
                               backref=db.backref('follower', lazy='joined'),
                               cascade='all, delete-orphan', lazy='dynamic')
    followers = db.relationship('Follow', foreign_keys=[Follow.followed_id],
                                backref=db.backref('followed', lazy='joined'),
                                cascade='all, delete-orphan', lazy='dynamic')

    def is_following(self, user):
        '''判断 self 用户是否关注了 user 用户'''
        return self.followed.filter_by(followed_id=user.id).first() is not None

    def is_followed_by(self, user):
        '''判断 self 用户是否被 user 用户关注'''
        return self.followers.filter_by(follower_id=user.id).first() is not None

    def follow(self, user):
        '''关注 user 用户，即向 follows 数据表中添加一条数据'''
        if not self.is_following(user):
            f = Follow(follower_id=self.id, followed_id=user.id)
            db.session.add(f)
            db.session.commit()

    def unfollow(self, user):
        '''取关 user 用户，即移除 follows 数据表中的一条数据'''
        f = self.followed.filter_by(followed_id=user.id).first()
        if f:
            db.session.delete(f)
            db.session.commit()

    # all blogs the user followed
    @property
    def followed_posts(self):
        return Blog.query.join(Follow, Follow.followed_id == Blog.author_id).filter(Follow.follower_id == self.id)

    # join是连表查询， 查询 Follow， 条件是 followed-id，筛选条件是follower—id

    # 需要新建一个column管理小图片，自动调整没有反应 (解决）

    def __repr__(self):
        return '<User: {}>'.format(self.name)

    def change_admin(self):
        f = Role.query.filter_by(id=3).first()
        self.role=f
        db.session.add(self)
        db.session.commit()

class Comment(db.Model):
    '''评论映射类'''

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    time_stamp = db.Column(db.DateTime, index=True, default=datetime.now)
    disable = db.Column(db.Boolean)
    author_id = db.Column(db.Integer,
                          db.ForeignKey('user.id', ondelete='CASCADE'))
    author = db.relationship('User', backref=db.backref('comments',
                                                        lazy='dynamic', cascade='all, delete-orphan'))
    blog_id = db.Column(db.Integer,
                        db.ForeignKey('blog.id', ondelete='CASCADE'))
    blog = db.relationship('Blog', backref=db.backref('comments',
                                                      lazy='dynamic', cascade='all, delete-orphan'))


class Blog(db.Model):
    '''Blog ORM'''
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    time_stamp = db.Column(db.DateTime, default=datetime.now)
    author_id = db.Column(db.Integer,
                          db.ForeignKey('user.id', ondelete='CASCADE'))
    author = db.relationship('User', backref=db.backref('blogs', lazy='dynamic',
                                                        cascade='all, delete-orphan'))
    '''author(relationship) 是基于 foreignkey而存在的!,没有 foreignkey 就不可能relationship
    author 可以直接在front 内被赋值 current user
    再id, time, author_id自动生成，body_html通过静态方法监听更改，body 通过form 更改
    '''

    # 该方法为静态方法，可以写在类外部，Blog().body 有变化时自动运行
    # target 为 Blog 类的实例，value 为实例的 body 属性值
    # old_value 为数据库中 Blog.body_html 的值，initiator 是一个事件对象
    # 后两个参数为事件监听程序调用此函数时固定要传入的值，在函数内部用不到
    @staticmethod
    def on_changed_body(target, value, old_value, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
                        'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                        'h1', 'h2', 'h3', 'p']
        # bleach.linkify 方法将 <a> 标签转换为链接
        # bleach.clean 方法清洗 HTML 数据
        # markdown 方法将 Markdown 文本转换为 HTML
        target.body_html = bleach.linkify(bleach.clean(markdown(value, output_format='html'),
                                                       tags=allowed_tags, strip=True))





# db.event.listen 设置 SQLAlchemy 的 'set' 事件监听程序
# 当 Blog.body 的值发生变化，该事件监听程序会自动运行
# 高效地修改 Blog.body_html 字段的值并存入数据表
db.event.listen(Blog.body, 'set', Blog.on_changed_body)

