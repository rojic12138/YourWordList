#输入一个单词，查找单词信息，如果没在本地找到则爬取
#单词要求全小写
from html import entities
import os
import json
from nltk.corpus import wordnet as wn
import requests 
from bs4 import BeautifulSoup
import re
headers={
'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def get_pronunciation(word:str):
    """从howjsay下载单词mp3音频"""
    path=os.path.join("static/audio",word+".mp3")
    #检查是否已经有音频
    if(os.path.exists(path)):
        print(f'{word} has audio')
        return path
    r=requests.get(f"https://d1qx7pbj0dvboc.cloudfront.net/{word}.mp3")
    audio=r.content
    with open(path,'wb') as f:
        f.write(audio)
    return os.path.join("audio",word+".mp3")

def get_definitions(word:str):
    """从merriam-webster下载单词含义与例句"""
    r=requests.get(f"https://www.merriam-webster.com/dictionary/{word}",headers=headers)
    soup=BeautifulSoup(r.text,'lxml').body
    definitions=[]
    #dictionary-entry-1 > div.vg > div > span
    #dictionary-entry-1 > div.vg > div > span > div > span
    entries=soup.select('div[id^="dictionary-entry-"] span[class^="sb-"]')

    #1.按class=sb-x找，但顺序不合要求
    # while(1):
    #     if(len(soup.select(f"span.^sb"))!=0):
    #         entries+=soup.select(f"span.sb-{i}")
    #         i+=1
    #     else:
    #         break

    #2.从大往小找，但未知情况可能有很多
    # if(soup.select("#dictionary-entry-1 > div.vg > div > span")[0]["class"][0].startswith("sb")):
    #     entries+=soup.select("#dictionary-entry-1 > div.vg > div > span")
    #     i=2
    #     while(1):
    #         try:
    #             if(soup.select(f"#dictionary-entry-{i} > div.vg > div > span")[0]["class"][0].startswith("sb")):
    #                 entries+=soup.select(f"#dictionary-entry-{i} > div.vg > div > span")
    #             i+=1
    #         except:
    #             break
    # else:
    #     print(word,"selector error")

    for entry in entries:
        meanings=entry.select(".dtText")
        meanings+=entry.select(".unText")
        meaning=""
        for m in meanings:
            meaning+=(m.text.lstrip(": ")+" ")
        meaning=re.sub('entry \d sense \d','',meaning)

        example=[]
        sent_without_author=entry.select(".no-aq")
        for s in sent_without_author:
            example.append(s.text)
        
        sent_with_author=entry.select(".has-aq")
        for i in range(len(sent_with_author)//2):
            reference=sent_with_author[i*2].text
            author=sent_with_author[i*2+1].text
            example.append(reference+"  "+author)

        definitions.append({"meaning":meaning,"example":example})
    return definitions

def get_synonyms_and_antonyms(word:str):
    """利用wordnet，根据单词的不同含义，得到同义词与反义词"""
    synsets=wn.synsets(word)
    synonyms_and_antonyms=[]
    for synset in synsets:
        meaning=synset.definition()
        synonyms=synset.lemma_names()
        antonyms=[x.name() for x in synset.lemmas()[0].antonyms()]
        if(len(synonyms)>1 or len(antonyms)>0):
            meaning=re.sub('(; )+','; ',meaning)
            synonyms_and_antonyms.append({"meaning":meaning,"synonyms":synonyms,"antonyms":antonyms})
    return synonyms_and_antonyms

def asemble_word(word:str,wn_word:str,word_id:int):
    """组装单词，保存为json"""
    pronunciation_path=get_pronunciation(word)
    definitions=get_definitions(word)
    synonyms_and_antonyms=get_synonyms_and_antonyms(wn_word)
    hints=get_hints(word)
    d={"word":word,"id":word_id,"pronunciation_path":pronunciation_path,
    "definitions":definitions,"synonyms_and_antonyms":synonyms_and_antonyms,
    "personal_translations":{},"hints":hints}
    with open(os.path.join('static/words',word+".json"),'w',encoding='utf-8') as f:
        f.write(json.dumps(d,indent=4))

def check_word_information(word:str):
    """在本地查找是否有单词文件，没有的话先判断是否是英语单词，是就组装一个文件"""
    words=os.listdir('static/words')
    if(word+".json" not in words):
        #检查是否是英语单词，即在wn中出现
        try:
            wn_word=re.sub(' ','_',word)
            wn.synsets(wn_word)[0]
        except:
            return False,0
        word_id=len(words)
        asemble_word(word,wn_word,word_id)
    else:
        word_id=json.load(open(os.path.join("static/words",word+".json")))["id"]
    return True,word_id

def get_word_information(word:str):
    """返回单词的dict"""
    return json.load(open(os.path.join('static/words',word+".json"),'r',encoding='utf-8'))

def add_annotation(word,person_id,annotation):
    """添加注释"""
    with open(os.path.join('static/words',word+".json"),'r',encoding='utf-8') as f:
        d=json.load(f)
    d["personal_translations"][person_id]=annotation
    with open(os.path.join('static/words',word+".json"),'w',encoding='utf-8') as f:
        f.write(json.dumps(d,indent=4))

def add_words(lines:list[str],person_name:str,person_id:str):
    """ 添加单词列表 
    args:
        word 中文释义
        （要求中文释义在一行最后，用空格与其他单词隔开，
        比如 take a photo 拍张照片、拍照
        判断是否有中文释义就是看最后一个单词的第一个字符是否是字母
    """
    num_lines=len(lines)
    error_lines=[]
    c=0#记录添加了多少个单词
    user_data=json.load(open(f"users/{person_name}.json",'r',encoding='utf-8'))
    for line in lines:
        if(c%100==0):
            print("complete {:.0f}%".format(c/num_lines*100))
        c+=1
        line=line.lower().strip('\n')
        if(len(line.split('|'))==2):#有注释
            annotation=line.split('|')[-1].strip()#去空格
            word=line.split('|')[0].strip()
            ok,word_id=check_word_information(word)
            if(not ok):
                error_lines.append(line)
                continue
            add_annotation(word,person_id,annotation) 
        elif(len(line.split('|'))==1):#没注释
            word=line.strip()
            ok,word_id=check_word_information(word)
            if(not ok):
                error_lines.append(line)
                continue
        else:#有多个注释，报错
            error_lines.append(line)
            continue
        if(word not in user_data["word_list"]):
            user_data["word_list"].append(word)
        if(word in user_data["memoried_word_list"]):
            user_data["memoried_word_list"].append(word)
        if(word not in user_data["mastered_word_list"]):
            user_data["mastered_word_list"].append(word)
    #保存user_data
    with open(f"users/{person_name}.json",'w',encoding='utf-8') as f:
        f.write(json.dumps(user_data,indent=4))

    info=f"successfully add {c-len(error_lines)} word(s), with {len(error_lines)} error word(s),\
    please check whether they are English words:"
    return info,error_lines

def add_words_from_txt(txt_path:str,person_id:int):
    """从txt文件中添加单词"""
    with open(txt_path,'r',encoding='utf-8') as f:
        data=f.readlines()
    add_words(data,person_id)

def get_hints(word):
    #从www.vocabulary.com获得两个hint
    r=requests.get(f"https://www.vocabulary.com/dictionary/{word}",headers=headers)
    soup=BeautifulSoup(r.text,'lxml').body
    try:
        short=soup.select('p[class="short"]')[0].text
    except:
        short=""
    try:
        long=soup.select('p[class="long"]')[0].text
    except:
        long=""
    if(short!="" or long !=""):
        return [short,long]
    else:
        return []
