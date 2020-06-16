import os


class BaseConfig:
    '''
    基础配置类，存储公共配置项
    '''

    SECRET_KEY = os.getenv('SECRET_KEY')
    FLASK_ENV = os.getenv('FLASK_ENV')
    FLASK_APP = 'manage.py'
    SQLALCHEMY_TRACK_MODIFICATIOS = False
    BLOGS_PER_PAGE = 10
    USERS_PER_PAGE = 10
    COMMENTS_PER_PAGE = 10
    #SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevConfig(BaseConfig):

    # 开发阶段使用的配置类
    # 这是设置连接数据库的配置项

    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = os.getenv('MAIL_PORT')
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')


class TestConfig(BaseConfig):
    '''
    测试阶段使用的配置类
    '''

    pass


# 配置类字典，便于 app.py 文件中的应用调用
configs = {
    'dev': DevConfig,
    'test': TestConfig
}