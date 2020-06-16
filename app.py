# File name: flask.py
import sys
sys.path.append('.')


from flask_pagedown import PageDown
from flask import Flask
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_migrate import Migrate # git for db
from flask_login import LoginManager

from handlers import blueprint_list
from configs import configs
from models import db, Role, User


def register_blueprints(app):
    for bp in blueprint_list:
        app.register_blueprint(bp)

def register_extensions(app):
    Bootstrap(app)
    db.init_app(app)
    Moment(app)
    Migrate(app, db)
    login_manager = LoginManager()    # 从这一行开始为新增代码
    login_manager.init_app(app)
    PageDown().init_app(app)

    # 该方法会被动执行，查找用户将其设为已登录状态
    @login_manager.user_loader
    def user_loader(id):
        # 只有主键才可以使用 query.get 方法查询
        return User.query.get(id)

    # 未登录状态下访问需要登录后才能访问的页面时，自动跳转到此路由
    login_manager.login_view = 'front.login'
    # 提示信息的内容和类型
    login_manager.login_message = '你需要登录之后才能访问该页面'
    login_manager.login_message_category = 'warning'

def create_app(config):
    app = Flask(__name__)
    app.config.from_object(configs.get(config)) # add configs from the 'configs' file
    register_extensions(app)
    register_blueprints(app)

    return app
