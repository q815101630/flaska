from flask import current_app, render_template, flash
from flask_mail import Mail, Message
from threading import Thread


def send_async_email(app, msg):
    '''该函数作为线程类实例化时 target 参数的值，在线程中执行'''

    with app.app_context():
        Mail(app).send(msg)


def send_email(user, email, tmp, token):
    '''
    发送邮件的主函数，参数分别是：
    当前登录用户，收件人的邮箱，前端文件名片段，token
    '''

    # 如果使用多线程，就不能用 current_app 了，它被看作是一个代理
    # 类似 socket 服务器中的主套接字，每次接收请求后都要创建一个临时套接字去处理
    # 此处使用 current_app 对象的 _get_curent_object 方法
    # 新创建的临时应用对象 app 包含独立的上下文信息，交给子线程处理
    app = current_app._get_current_object()
    # Message 是一个类，它接收以下参数：
    # 1、默认参数 subject 字符串（邮件主题
    # 2、sender 字符串（发件人邮箱
    # 3、recipients 列表（收件人邮箱列表
    msg = Message(
            'To: ' + user.name,
            sender = app.config.get('MAIL_USERNAME'),
            recipients = [email]
    )
    msg.body = render_template('email/{}.txt'.format(tmp), user=user,
            token=token)    # 纯文本文件
    msg.html = render_template('email/{}.html'.format(tmp), user=user,
            token=token)    # HTML 文件
    thread = Thread(target=send_async_email, args=(app, msg))
    thread.start()          # 创建一个子线程并启动
    return thread