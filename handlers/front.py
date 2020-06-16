import sys

sys.path.append('..')

from datetime import datetime
from flask import Blueprint, url_for, redirect, flash, abort, request, session
from flask import render_template, current_app, make_response
from flask_login import login_required, login_user, logout_user, current_user

from forms import RegisterForm, LoginForm, BlogForm, CommentForm
from models import db, User, Blog, Comment, Permission
from email_app import send_email
from decorators import moderate_required

# build the blueprint
front = Blueprint('front', __name__)


# 由 before_app_request 所装饰的视图函数
# 会在所有请求（包括视图函数不在这个蓝图下的请求）被处理之前执行
# 相当于服务器收到任何请求后，先经过此函数进行预处理
@front.before_app_request
def before_request():
    '''页面请求预处理'''
    # current_user 默认为匿名用户，其 is_authenticated 属性值为 False
    # 用户登录后，current_user 为登录用户，is_authenticated 属性值为 True
    if current_user.is_authenticated:
        current_user.ping()  # fresh the last_seen
        # 未验证的用户登录后要发出 POST 请求的话，让用户先通过验证
        # 如果用户未通过邮箱确认身份，且为 POST 请求
        if (not current_user.confirmed) and (request.method == 'POST'):
            # 那么把请求交给 front.unconfirmed_user 函数处理
            return redirect(url_for('front.unconfirmed_user'))


@front.route('/', methods=['GET', 'POST'])
def index():
    '''网站首页'''
    form = BlogForm()
    # 凡是登录成功的用户，就有写博客的权限
    if current_user.is_authenticated:
        if form.validate_on_submit():
            blog = Blog()
            form.populate_obj(blog)
            blog.author = current_user
            db.session.add(blog)
            db.session.commit()
            flash('成功发布博客', 'success')
            return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = Blog.query.order_by(Blog.time_stamp.desc()).paginate(
        page,
        per_page=current_app.config['BLOGS_PER_PAGE'],
        error_out=False
    )
    blogs = pagination.items
    return render_template('index.html', form=form, blogs=blogs,
                           pagination=pagination)


@front.route('/unconfirmed_user')
@login_required
def unconfirmed_user():
    if current_user.is_anonymous or current_user.confirmed:
        return redirect(url_for('.index'))
    return render_template('user/confirm.html')


@front.route('/repeat_confirm')
@login_required
def resend_confirm_email():
    token = current_user.generate_confirm_user_token()
    # 这里的confirm_user 就是寄出的模板
    send_email(current_user, current_user.email, 'confirm_user', token)
    flash('A new confirmation email has been sent to your email.', 'info')
    return redirect(url_for('.index'))


@front.route('/register', methods=['POST', 'GET'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():  # pressed the submit button
        form.create_user()
        flash('You have registered successfully, please login in! ', 'success')
        return redirect(url_for('.login'))
    return render_template('register.html', form=form)


@front.route('/login', methods=['POST', 'GET'])
def login():
    if current_user.is_authenticated:
        flash('You have logged in.', 'info')
        return redirect(url_for('.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            flash('We cannot recognize the email provided. :<', 'info')
            # return redirect(url_for('.register'))
        elif user and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            flash('You have logged in successfully, {}'.format(user.name), 'success')
            if not user.confirmed:
                return redirect(url_for('.unconfirmed_user'))
            return redirect(url_for('.index'))
        flash('Wrong user name or password! :(', 'warning')
    return render_template('login.html', form=form)


# 用户注册之后，先在浏览器上登录，然后使用邮件确认账户的邮箱是否准确
# 新注册用户收到验证邮件后，通过点击邮件中提供的地址请求验证
@front.route('/confirm-user/<token>')
@login_required
def confirm_user(token):
    if current_user.confirmed:
        flash('You have confirmed already :>', 'info')
    elif current_user.confirm_user(token):
        flash('You confirm your email successfully! :)', 'success')
    else:
        flash('This is a unauthorized link', 'danger')
    return redirect(url_for('.index'))


@front.route('/logout')
def logout():
    logout_user()
    flash('You have logged out :)', 'info')
    return redirect(url_for('.index'))


@front.app_errorhandler(404)
def page_not_found(e):
    # Route error
    return render_template('404.html'), 404


@front.app_errorhandler(500)
def inter_server_error(e):
    return render_template('500.html'), 500

@front.route('/blog/<int:id>', methods=['GET', 'POST'])
def blog(id):
    '''每篇博客的单独页面，便于分享'''
    blog = Blog.query.get_or_404(id)
    # 页面提供评论输入框
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data, blog=blog, author=current_user)
        db.session.add(comment)
        db.session.commit()
        flash('评论成功。', 'success')
        return redirect(url_for('.blog', id=id))
    page = request.args.get('page', default=1, type=int)
    pagination = blog.comments.order_by(Comment.time_stamp.desc()).paginate(
            page,
            per_page = current_app.config['COMMENTS_PER_PAGE'],
            error_out = False
    )
    comments = pagination.items
    # hidebloglink 在博客页面中隐藏博客单独页面的链接
    # noblank 在博客页面中点击编辑按钮不在新标签页中打开
    return render_template('blog.html', blogs=[blog], hidebloglink=True,
            noblank=True, form=form, pagination=pagination,
            comments=comments, Permission=Permission)

@front.route('/comment/disable/<int:id>')
@moderate_required
def disable_comment(id):
    '''管理员封禁评论'''
    comment = Comment.query.get_or_404(id)
    comment.disable = 1
    db.session.add(comment)
    db.session.commit()
    return redirect(request.headers.get('Referer'))


@front.route('/comment/enable/<int:id>')
@moderate_required
def enable_comment(id):
    '''管理员解封评论'''
    comment = Comment.query.get_or_404(id)
    comment.disable = 0
    db.session.add(comment)
    db.session.commit()
    return redirect(request.headers.get('Referer'))