'''
完成注册和验证后，用户相关的视图函数
'''
# 若产生报错 'Permission' is undefined，则可能是导入顺序问题，请将下列覆盖到之前导入函数
from datetime import datetime
from flask import Blueprint, abort, redirect, url_for, flash, render_template
from flask import request, current_app
from flask_login import login_required, login_user, current_user

import sys

sys.path.append('..')

from models import db, User, Role, Blog
from forms import ProfileForm, AdminProfileForm, ChangePasswordForm, BlogForm
from forms import BeforeResetPasswordForm, ResetPasswordForm, ChangeEmailForm
from decorators import admin_required
from email_app import send_email

user = Blueprint('user', __name__, url_prefix='/user')



@user.route('/<name>/index')
def index(name):

    class Permission:
        FOLLOW = 1
        WRITE = 2
        COMMENT = 4
        MODERATE = 8
        ADMINISTER = 2 ** 7

    user = User.query.filter_by(name=name).first()
    if not user:
        abort(404)
    blogs = user.blogs.order_by(Blog.time_stamp.desc())

    return render_template('user/index.html', user=user, blogs=blogs, permission=Permission)


@user.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    # obj allows all user-info get into the form
    form = ProfileForm(current_user, obj=current_user)
    if form.validate_on_submit():
        form.populate_obj(current_user)
        db.session.add(current_user)
        db.session.commit()
        flash('Personal Information has been updated', 'success')
        return redirect(url_for('.index', name=current_user.name))
    return render_template('user/edit_profile.html', form=form)


@user.route('admin-edit-profile/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_profile(id):
    user = User.query.get(id)
    form = AdminProfileForm(user, obj=user)
    if form.validate_on_submit():
        form.populate_obj(user)  # 这个不是很懂
        db.session.add(user)
        db.session.commit()
        flash('info has been changed', 'success')
        return redirect(url_for('.index', name=user.name))
    return render_template('user/edit_profile.html', form=form)


@user.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        current_user.password = form.password.data
        db.session.add(current_user)
        db.session.commit()
        flash('Password changed successfully', 'success')
        return redirect(url_for('.index', name=current_user.name))
    return render_template('user/change_password.html', form=form)


@user.route('/before-reset-password', methods=['GET', 'POST'])
def before_reset_password():
    form = BeforeResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        token = user.generate_confirm_user_token()
        send_email(user, user.email, 'reset_password', token)
        flash('An email attached with token has been sent to your email', 'info')
    return render_template('user/reset_password.html', form=form)


@user.route('/reset-password/<name>/<token>', methods=["GET", "POST"])
def reset_password(name, token):
    user = User.query.filter_by(name=name).first()
    if user and user.confirm_user(token):
        form = ResetPasswordForm()
        if request.method == 'GET':
            flash('Please reset your password', 'success')
            return render_template('user/reset_password.html', form=form)
        if form.validate_on_submit():
            user.password = form.password.data
            db.session.add(user)
            db.session.add(user)
            db.session.commit()
            flash('Password has been reset', 'success')
            return redirect(url_for('.index', name=user.name))
    else:
        flash('Wait...Wrong token!', 'danger')
    return redirect(url_for('front.index'))


@user.route('/change-email', methods=['POST', 'GET'])
@login_required
def change_email():
    flash('错误的邮箱地址可能导致账号丢失！请小心哦~', 'warning')
    form = ChangeEmailForm()
    if form.validate_on_submit():
        current_user.email = form.email.data
        current_user.confirm = 0
        db.session.add(current_user)
        db.session.commit()
        token = current_user.generate_confirm_user_token()
        send_email(current_user, current_user.email, 'change_email', token)
        flash('A email with token has been sent to your email, please check the junk box :P', 'success')
    return render_template('user/change_email.html', form=form)


#  这里的token generate 相关需要clarify一下
@user.route('/change-email/<token>')
@login_required
def confirm_change_email(token):
    if current_user.confirm_user(token):
        current_user.confirmed = 1  # 可以省略此句
        db.session.add(current_user)
        db.session.commit()
        flash('Changed the email successfully!', 'success')
    flash('Seems not a right link!', 'danger')
    return redirect(url_for('front.index'))


@user.route('/follow/<name>')
@login_required
def follow(name):
    '''关注用户'''
    user = User.query.filter_by(name=name).first()
    if not user:
        flash('该用户不存在。', 'warning')
        return redirect(url_for('front.index'))
    if current_user.is_following(user):
        flash('在此操作之前，你已经关注了该用户。', 'info')
    else:
        current_user.follow(user)
        flash('成功关注此用户。', 'success')
    return redirect(url_for('.index', name=name))


@user.route('/unfollow/<name>')
@login_required
def unfollow(name):
    '''取关用户'''
    user = User.query.filter_by(name=name).first()
    if not user:
        flash('该用户不存在。', 'warning')
        return redirect(url_for('front.index'))
    if not current_user.is_following(user):
        flash('你并未关注此用户。', 'info')
    else:
        current_user.unfollow(user)
        flash('成功取关此用户。', 'success')
    return redirect(url_for('.index', name=name))

@user.route('/<name>/followed')
def followed(name):
    '''【user 关注了哪些用户】的页面'''
    user = User.query.filter_by(name=name).first()
    if not user:
        flash('用户不存在。', 'warning')
        return redirect(url_for('front.index'))
    page = request.args.get('page', default=1, type=int)
    pagination = user.followed.paginate(
            page,
            per_page = current_app.config['USERS_PER_PAGE'],
            error_out = False
    )
    follows = [{'user': f.followed, 'time_stamp': f.time_stamp}
            for f in pagination.items]
    # 这个模板是「关注了哪些用户」和「被哪些用户关注了」共用的模板
    return render_template('user/follow.html', user=user, title='我关注的人',
            endpoint='user.followed', pagination=pagination, follows=follows)


@user.route('/<name>/followers')
def followers(name):
    '''【user 被哪些用户关注了】的页面'''
    user = User.query.filter_by(name=name).first()
    if not user:
        flash('用户不存在。', 'warning')
        return redirect(url_for('front.index'))
    page = request.args.get('page', default=1, type=int)
    pagination = user.followers.paginate(
            page,
            per_page = current_app.config['USERS_PER_PAGE'],
            error_out = False
    )
    follows = [{'user': f.follower, 'time_stamp': f.time_stamp}
            for f in pagination.items]
    return render_template('user/follow.html', user=user, title='关注我的人',
            endpoint='user.followers', pagination=pagination, follows=follows)

@user.route('/edit-blog/<int:id>', methods=['GET','POST'])
@login_required
def edit_blog(id):
    blog = Blog.query.get_or_404(id)
    if current_user != blog.author and not current_user.is_administrator:
        abort(403)
    form = BlogForm(obj=blog)
    if form.validate_on_submit():
        form.populate_obj(blog)
        db.session.add(blog)
        db.session.commit()
        flash('博客已经更新', 'success')
        return redirect(url_for('front.blog', id=blog.id))
    return render_template('user/edit_blog.html', form=form)