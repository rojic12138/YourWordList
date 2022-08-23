from http import server
from unicodedata import name
from flask import Flask, render_template, request, redirect, url_for, session,flash
import os
import json
from flask_login import UserMixin,LoginManager,login_user,logout_user,current_user, login_required
from time import sleep
import re
from word_information import add_words
from random import sample
from gevent import pywsgi

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = "123456"
app.secret_key = "123456"

#登陆界面
login_manager=LoginManager(app)
login_manager.login_view='login'
login_manager.login_message='Please login in to access this page'
login_manager.login_message_category="info"

#用户类
class User(UserMixin):
    def get_name(self):
        return self.name

#启动时运行，得到用户的信息
def get_users():
    users={}
    files=os.listdir('users')
    for file in files:
        users[file.strip('.json')]=json.load(open(os.path.join('users',file)))
    return users
users=get_users()

#通过name来获取用户信息
def query_user(name):
    if name in users.keys():
        return users[name]
    return None

#加载当前用户信息
@login_manager.user_loader
def load_user(name):
    if query_user(name) != None:
        curr_user=User()
        curr_user.name=name
        return curr_user

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'),404

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        username=request.form['username']
        user=query_user(username)
        if user is not None and request.form['password']==user['password']:
            # flash('Logged in as: %s. Click the logo to come back to frontpage.' % username)
            curr_user=User()
            curr_user.name=curr_user.id=username
            login_user(curr_user, remember=True)
            return redirect('/')
        else:
            flash('Wrong username or password!')
    return render_template('login.html')

@app.route('/logout',methods=['GET','POST'])
def logout():
    if request.method=='POST':
        if 'yes' in request.form:
            # flash('Successfully logout. Click the logo to come back to frontpage.')
            logout_user()
            return redirect('/')
    return render_template('logout.html')

#注册新用户时分配的id
def new_person_id():
    files=os.listdir('users')
    return len(files)

#注册用户
@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        email=request.form['email']
        if(bool(re.match("^[a-zA-Z0-9_]*$",username)==False)):
            flash('The name must only consist of a-z A-Z 0-9 and _')
        elif(len(password)<6):
            flash('The password must be no shorter than 6')
        else:
            user=query_user(username)
            if user is not None:
                flash('This name has already been used')
            else: #新建一个用户文件
                person_id=new_person_id()
                d={"name":username,"person_id":person_id,"password":password,"email":email,"word_list":[],"memoried_word_list":[],"mastered_word_list":[]}
                users[username]=d
                with open(f'users/{username}.json','w',encoding='utf-8') as f:
                    f.write(json.dumps(d,indent=4))
                return redirect('/login')
    return render_template('register.html')

#保存user的信息
def save_user(username):
    data=users[username]
    with open(f'users/{username}.json','w',encoding='utf-8') as f:
        f.write(json.dumps(data,indent=4))

#删除user的信息
def del_user(username):
    os.remove(f'users/{username}.json')
    del users[username]

#个人页面
@app.route('/profile',methods=['GET','POST'])
@login_required
def profile():
    name=current_user.get_name()
    global users
    user=get_users()
    data=users[name]
    if request.method=='POST':
        if('change' in request.form):
            change=True
        else:
            new_data=data
            username=new_data['name']=request.form['username']
            password=new_data['password']=request.form['password']
            if(bool(re.match("^[a-zA-Z0-9_]*$",username)==False)):
                flash('The name must only consist of  a-z A-Z 0-9 and _')
            elif(len(password)<6):
                flash('The password must be longer than 5 (6 is ok)')
            else:
                user=query_user(username)
                if (username!=name and user is not None):
                    flash('This name has already been used')
                new_data['email']=request.form['email']
                users[username]=new_data
                save_user(username)
                del_user(name)
            
                flash('You have successfully changed your profile! Please login again.')
                change=False
    else:
        change=False
    return render_template('profile.html',data=data,change=change)

@app.route('/',methods=['GET','POST'])
def frontpage():
    try:
        current_user.get_name()
        logined=True
    except:
        logined=False
    if(request.method=='POST'):
        if('login' in request.form):
            return render_template('login.html')
        elif('register' in request.form):
            return render_template('register.html')
    return render_template('frontpage.html',logined=logined)

#单词页面
@app.route('/word/<word>',methods=['GET','POST'])
@login_required
def display_word(word):
    username=current_user.get_name()
    if(request.method=='POST'):
        #修改单词注释
        if('change_annotation' in request.form):
            #之前遇到如有空格则只显示第一部分的问题，解决途径是value加引号，value='{{translation }}'
            annotation=request.form["annotation"]
            person_id=users[username]["person_id"]
            data=json.load(open(f"static/words/{word}.json"))
            data["personal_translations"][person_id]=annotation
            with open(f"static/words/{word}.json",'w') as f:
                f.write(json.dumps(data,indent=4))
        else:
            if('forget' in request.form):
                if(word not in users[username]["word_list"]):
                    users[username]["word_list"].append(word)
                try:
                    users[username]["memoried_word_list"].remove(word)
                except:
                    pass
                try:
                    users[username]["mastered_word_list"].remove(word)
                except:
                    pass
            elif('memoried' in request.form):
                if(word not in users[username]["memoried_word_list"]):
                    users[username]["memoried_word_list"].append(word)
                try:
                    users[username]["word_list"].remove(word)
                except:
                    pass
                try:
                    users[username]["mastered_word_list"].remove(word)
                except:
                    pass
            elif('mastered' in request.form):
                if(word not in users[username]["mastered_word_list"]):
                    users[username]["mastered_word_list"].append(word)
                try:
                    users[username]["word_list"].remove(word)
                except:
                    pass
                try:
                    users[username]["memoried_word_list"].remove(word)
                except:
                    pass
            save_user(username)

            #转到下一个页面
            if("words" in session.keys() and len(session["words"])>1):
                if(session["i"]==len(session["words"])-1):
                    session["words"]=[]
                    session["i"]=0
                    flash("This is the last word of this memory. Take a rest!")
                else:
                    session["i"]+=1
                    return redirect(url_for("display_word",word=session["words"][session["i"]]))

    person_id=users[username]["person_id"]
    #get word_information
    word_data=json.load(open(f'static/words/{word}.json','r',encoding='utf-8'))
    pronunciation_path=url_for('static',filename=word_data["pronunciation_path"].replace("\\","/"))
    try:
        translation=word_data["personal_translations"][str(person_id)]
    except:
        translation=""
    definitions=word_data["definitions"]
    synonyms_and_antonyms=word_data["synonyms_and_antonyms"]
    try:
        word_num=len(session["words"])
        i=session["i"]
    except:
        word_num=[]
        i=0
    hints=word_data["hints"]
    return render_template('word_information.html',word=word,pronunciation_path=pronunciation_path,
    translation=translation,definitions=definitions,synonyms_and_antonyms=synonyms_and_antonyms,word_num=word_num,i=i,hints=hints)

#添加单词
@app.route('/add_words',methods=['GET','POST'])
@login_required
def website_add_words():
    if(request.method=='POST'):
        lines=request.form["lines"]
        lines=lines.split('\n')
        if(type(lines)==str):
            lines=[lines]
        new_lines=[]
        for line in lines:
            if(line.replace('\r','')!=''):
                new_lines.append(line.replace('\r',''))
        username=current_user.get_name()
        person_id=users[username]["person_id"]
        info,error_lines=add_words(new_lines,username,person_id)
        flash(info)
        flash(error_lines)
        # return render_template('frontpage.html',logined=True)
    return render_template('add_words.html')

def sample_words(num,train_ratio=0.8):
    words=[]
    username=current_user.get_name()
    l1=users[username]["word_list"]
    l2=users[username]["memoried_word_list"]
    n1=len(l1)
    n2=len(l2)
    if(n1>=num):
        words=sample(l1,num)
    elif(n1+n2>=num):
        words=sample(l1+l2,num)
    else:
        words=l1+l2
    return words

#背单词
@app.route('/memory',methods=['GET','POST'])
@login_required
def memory_words():
    if(request.method=='POST'):
        num=int(request.form["num"])
        if(num==0):
            flash('Of course, 0 is not advisable.')
        else:
            #抽num个单词出来
            words=sample_words(num)
            session['words']=words
            session['i']=0
            return redirect(url_for("display_word",word=words[0]))
    return render_template('memory.html')

#用pywsgi在服务器上运行
if __name__ == '__main__':
    server=pywsgi.WSGIServer(('0.0.0.0',80),app)
    server.serve_forever()

#mesmeric