import sys

from flask_login import current_user

sys.path.append('.')

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, PasswordField, IntegerField, RadioField, TextAreaField, \
    SelectField
from wtforms import ValidationError
from wtforms.validators import DataRequired, Length, Email, EqualTo, Regexp, Optional
from email_app import send_email
from models import db, User, Role
from flask_pagedown.fields import PageDownField


gender_list = [('Male', '男'), ('Female', '女'),
               ('FUTA', '扶她「ふたなり」'), ('OTOKONOKO', '伪娘「おとこのこ」'),
               ('OTHER', 'Other gender not listed'),
               ('UNKNOWN', 'I am not sure')]


class RegisterForm(FlaskForm):
    '''注册表单类'''

    name = StringField('Name', validators=[DataRequired(), Length(3, 22),
                                           # Regexp 接收三个参数，分别为正则表达式、flags 、提示信息
                                           # flags 也叫作「旗标」，没有的话写为 0
                                           Regexp('^\w+$', 0, 'User name must have only letters.')])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(),
                                                     Length(3, 32)])
    repeat_password = PasswordField('Repeat Password', validators=[
        DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_name(self, field):
        if User.query.filter_by(name=field.data).first():
            raise ValidationError('Name already registered.')

    def create_user(self):
        user = User()
        self.populate_obj(user)
        user.avatar_hash = user.gravatar()
        user.small_avatar_hash = user.small_gravatar()
        db.session.add(user)
        db.session.commit()
        token = user.generate_confirm_user_token()
        send_email(user, user.email, 'confirm_user', token)
        return user


class LoginForm(FlaskForm):
    '''登录表单类'''

    email = StringField('Email', validators=[DataRequired(), Length(6, 64),
                                             Email()])
    password = PasswordField('Password', validators=[DataRequired(),
                                                     Length(3, 32)])
    remember_me = BooleanField('Remember me')
    submit = SubmitField('Login')


class ProfileForm(FlaskForm):
    '''information form'''

    # flaskform has __init__ method and we cannot interrupt it
    def __init__(self, user, *args, **kw):
        super().__init__(*args, **kw)
        self.user = user

    name = StringField('username', validators=[DataRequired(), Length(2, 22),
                                               Regexp('^\w+$', 0, '用户名只能使用字母和数字')])
    age = IntegerField('age', validators=[Optional()])
    gender = SelectField('prefered gender', choices=gender_list)
    phone_num = StringField('phone', validators=[Optional(), Length(6, 16)])
    location = StringField('location', validators=[Optional(), Length(2, 16)])
    about_me = TextAreaField('introduction')
    submit = SubmitField('Submit')

    def validate_name(self, field):
        if (field.data != self.user.name and
                User.query.filter_by(name=field.data).first()):
            raise ValidationError('This username has been used')

    def validate_phone_num(self, field):
        if (field.data != self.phone_num.data and
                User.query.filter_by(phone_num=field.data).first()):
            raise ValidationError('This phone number has been used')


class AdminProfileForm(ProfileForm):
    '''管理员编辑用户个人信息所用的表单类'''

    name = StringField('用户名', validators=[DataRequired(), Length(2, 22),
                                          Regexp('^\w+$', 0, '用户名只能使用单词字符')])
    age = IntegerField('年龄', validators=[Optional()])
    gender = SelectField('性别', choices=gender_list)
    phone_num = StringField('电话', validators=[Length(6, 16), Optional()])
    location = StringField('所在城市', validators=[Optional(), Length(2, 16)])
    about_me = TextAreaField('个人简介', validators=[Optional()])
    # 这个选择框，选择的结果就是 int 数值，也就是用户的 role_id 属性值
    # 参数 coerce 规定选择结果的数据类型
    # 该选择框须定义 choices 属性，也就是选项列表
    # 每个选项是一个元组，包括 int 数值（页面不可见）和选项名（页面可见）
    # 选择某个选项，等号前面的变量 role_id 就等于对应的 int 数值
    role_id = SelectField('角色', coerce=int)
    confirmed = BooleanField('已通过邮箱验证')
    submit = SubmitField('提交')

    def __init__(self, user, *args, **kw):
        super().__init__(user, *args, **kw)
        # 初始化表单类实例时，需要定义好 SelectField 所需的选项列表
        self.role_id.choices = [(role.id, role.name)
                                for role in Role.query.order_by(Role.permissions)]


class ChangePasswordForm(FlaskForm):
    '''用户登录后修改密码所使用的表单类'''

    old_password = PasswordField('Old password', validators=[DataRequired()])
    password = PasswordField('New password',
                             validators=[DataRequired(), Length(3, 22)])
    repeat_password = PasswordField('Repeat new password',
                                    validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Submit')

    def validate_old_password(self, field):
        if not current_user.verify_password(field.data):
            raise ValidationError('The old password does not match')


class BeforeResetPasswordForm(FlaskForm):
    '''忘记密码时利用邮箱重置密码前所使用的【邮箱】表单类'''

    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Submit')

    def validate_email(self, field):
        if not User.query.filter_by(email=field.data).first():
            raise ValidationError('This email has not been registered')


class ResetPasswordForm(FlaskForm):
    '''忘记密码时利用邮箱重置密码时所使用的【密码】表单类'''

    password = PasswordField('New Password',
                             validators=[DataRequired(), Length(3, 22)])
    repeat_password = PasswordField('Repeat password',
                                    validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('提交')


class ChangeEmailForm(FlaskForm):
    '''change email'''
    email = StringField('New email',
                        validators=[DataRequired(), Email()])
    repeat_email = StringField('Repeat the email',
                               validators=[DataRequired(), EqualTo('email')])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField()

    def validate_email(self, field):  # validate自动寻找email field
        if not User.query.filter_by(email=field.data).first():
            return ValidationError('Cannot find the email address')

    def validate_password(self, field):
        if not current_user.verify_password(field.data):
            return ValidationError('Wrong password')

class BlogForm(FlaskForm):
    '''Blog form'''
    '''Flask pagedown supports markdown writing'''
    body = PageDownField('How are you today? :)', validators=[DataRequired()])
    submit = SubmitField('Publish')

class CommentForm(FlaskForm):
    body = TextAreaField('', validators=[DataRequired()])
    submit = SubmitField('Submit')
