'''
Created on Sep 3, 2018

@author: yangke
'''
import os
from subprocess import Popen, PIPE
from subprocess import check_output
import signal
import logging
import re

PROJECT_PATH="/home/yangke/Program/Winux/wine-3.0.1/dlls/";
FIELD_SEARCH_PATH="/home/yangke/Program/Winux/wine-3.0.1/";
KEYWORDS="switch if for while return do".split()
IGNORE_SINKS="TRACE trace FIXME fixme WARN warn ERR err debug Debug dbg Dbg cmp Cmp free Free sizeof".split()
#"debugstr_w strncmp strcmpi strcmpiW SysFreeString SHFree HeapFree heap_free ME_DestroyString heap_realloc".split()
NEED_MOD_TARGETS_CHECK_FUNCS="strncpy strcpy strcpyW strncpyW memcpy memmove lstrcpynA lstrcpynW lstrcpyW ME_InsertString".split()
DANGER_FUNC="strcpy strlen memcpy"

def restore_signals(): # from http://hg.python.org/cpython/rev/768722b2ae0a/
    signals = ('SIGPIPE', 'SIGXFZ', 'SIGXFSZ')
    for sig in signals:
        if hasattr(signal, sig):
            signal.signal(getattr(signal, sig), signal.SIG_DFL)
            
def get_var_name(line,a_type):
    start=line.find(a_type)+len(a_type)
    end1=line.find(";",start)
    end2=line.find("[",start)
    end=end1 if end1<end2 else end2
    if end2==-1:
        end=end1
    str=line[start:end].strip()
    if "/" in line[:end] or "const " in line[:end]:
        return []
    if "," in str:
        array=str.split(",");
        i=1
        num=a_type.count("*")
        while i<len(array):
            str=array[i]
            while num > 0:
                str=str[str.find("*")+1:].strip()
                num-=1
            array[i]=str
            i+=1
        return array
    else:
        return [str]
    
'''
recognize this assignment pattern
code "dump_arg(rs, &ins->output,..."
                       ^
         deref_symbol_pos
'''
def is_call_sink(code,deref_symbol_pos):#FIXME sometimes need previous code
    i=code[:deref_symbol_pos].find('&')
    if i>0 and code[i+1]!="&" and re.match(r'^[_a-zA-Z][_a-zA-Z0-9]*((\->|\.)[_a-zA-Z][_a-zA-Z0-9]*)*$',code[i+1:deref_symbol_pos]):
        return True
    return False    
    '''
    j=deref_symbol_pos-1
    in_field=False
    while j>=0:
        if re.match(r'[_A-Za-z0-9]',code[j]):
            in_field=True
            j-=1
            continue
        elif j>=1 and in_field and  code[j-1:j+1]=="->":
            in_field=False
            j-=2
        elif j>=0 and in_field and code[j]==".":
            in_field=False
            j-=1
        elif j>=0 and in_field and code[j]=="&":
            return True,j
        elif j>=0 and in_field:
            return False,j+1
        elif j>=0 and not in_field and re.match(r'\s',code[j]):
            j-=1
        elif j>=0 and not in_field and not re.match(r'\s',code[j]):
            print code,"###",code[j]
            return False,-1
        else:
            return False,-1
            
    return False,-1
    '''  
'''
get the sink callee name 
e.g. 
input:
code="dump_arg(rs, &ins->output,..."
                       ^
         deref_symbol_pos
return: "dump_arg"

'''
def get_callee_name(code,deref_symbol_pos):
    i=deref_symbol_pos
    s=[]
    commas_count=0
    while i>=0:
        if code[i]==")":
            s.append(")")
        elif code[i]=="(":
            if len(s)==0:
                i-=1
                break
            elif len(s)>0:
                s.pop()
        elif code[i]==',' and len(s)==0:
            commas_count+=1
        i-=1;
    
    if i>=0:
        end=i+1
        is_func=False
        while i>=0 and re.match(r'[_a-z0-9A-Z]', code[i]):
            is_func=True
            i-=1
        if i>=-1 and is_func:
            start=i+1
            while re.match(r'\s', code[i]):
                i-=1
            if i>=0 and code[i]=='.':
                func_name='.'+code[start:end]
            elif i-1>=0 and code[i-1:i+1]=='->':
                func_name='->'+code[start:end]
                #assert(0)
            else:
                func_name=code[start:end]
            if func_name not in KEYWORDS:
                for ig in IGNORE_SINKS:
                    if func_name.find(ig)!=-1:
                        return None,None
                #if func_name=="memcpy":
                #    print  func_name,code
                return func_name,commas_count
      
    return None,None                       

def find_fields(field_search_path):
    #field_search_path="/home/yangke/Program/Winux/wine-3.0.1/dlls/shell32";
    #check_output('find '+field_search_path+' -name "*.[ch]" | grep "struct [_A-Za-z][_0-9A-Za-z]* {" -rn', shell=True, preexec_fn=restore_signals)

    p1 = Popen('find '+field_search_path+' -name "*.[ch]"',
                          stdout=PIPE,shell=True )
                          #stderr=subprocess.PIPE, close_fds=True)
    p2 = Popen(['sed "/\/tests\//d"'], stdin=p1.stdout,
                          stdout=PIPE, shell=True)                          
    p3 = Popen('xargs grep "struct [_A-Za-z][_0-9A-Za-z]* {" -rn', stdin=p2.stdout,
                          stdout=PIPE,shell=True )
    p4 = Popen(['sed "/const struct/d"'], stdin=p3.stdout,
                          stdout=PIPE, shell=True)
    out0, err0 = p4.communicate()
    

    
    p1 = Popen('find '+field_search_path+' -name "*.[ch]"',
                          stdout=PIPE,shell=True )
    p2 = Popen(['sed "/\/tests\//d"'], stdin=p1.stdout,
                          stdout=PIPE, shell=True) 
    p3 = Popen('xargs grep "typedef struct {" -rn', stdin=p2.stdout,
                          stdout=PIPE,shell=True )
    
    p4 = Popen(['sed "/const struct/d"'], stdin=p3.stdout,
                          stdout=PIPE, shell=True)
    out1, err1 = p4.communicate()
    
    out=out0+out1
    lines=out.split("\n")
    pairs= [l.split(":")[:2]for l in lines]
    fields=[]
    bads=[]
    for pair in pairs:
        if len(pair)==2:
            filepath,linenum=pair
            target=''
            if "shfldr_fs.c" in filepath and linenum=='60':
                target= "sPathTarget"
            f=file(filepath,"r")
            ll=f.readlines()
            f.close()
            i=int(linenum)+1
            while "}" not in ll[i]:
                #print ll[i]
                if "(" in ll[i]:
                    i+=1
                    continue
                if ")" in ll[i]:
                    i+=1
                    continue
                
                '''
                if "WCHAR *" in ll[i]:
                    str=get_var_name(ll[i],"WCHAR *")
                    fields.append(str)
                    print str
                if " CHAR *" in ll[i]:
                    str=get_var_name(ll[i],"WCHAR *")
                    fields.append(str)
                    print str
                if "wchar *" in ll[i]:
                    str=get_var_name(ll[i],"WCHAR *")
                    fields.append(str)
                    print str
                if " char *" in ll[i]:
                    array=get_var_name(ll[i]," char *")
                    fields.extend(array)
                    #fields.append(array)
                    #print ll[i]
                    print array
                '''
                if "LPWSTR" in ll[i]:
                    array=get_var_name(ll[i],"LPWSTR")
                    if target=="sPathTarget":
                        assert(array[0]==target)
                    if len(array)>0:
                        fields.extend(array)
                if "LPSTR" in ll[i]:
                    array=get_var_name(ll[i],"LPSTR")
                    if len(array)>0:
                        fields.extend(array)
                        if 'a' in array:   
                            print array
                            print pair
                i+=1
        else:
            bads.append(pair)
    #print bads
    fields=list(set(fields))
    for field in fields:
        print field
    print "find %d fields" %(len(fields))
    return fields

def findFuncPos(prefix):##need fix
    p=prefix
    j=len(p)-1
    start=len(p)
    end = len(p)
    while j>=0:
        while j>=0 and  p[j]!='{':
            j-=1
        if j>=0:
            j-=1
            while j>=0 and re.match(r"\s",p[j]):
                j-=1
            if p[j]!=')':
                j-=1
                continue
            else:
                j-=1
                matched=False
                s=[]
                while j>=0:
                    if p[j]=="(":
                        if len(s)==0:
                            matched=True
                            break
                        else:
                            s.pop()
                    elif p[j]==")":
                        s.append(")")
                    j-=1
                if matched:
                    j-=1
                    while j>=0 and re.match(r"\s",p[j]):
                        j-=1
                    end = j+1
                    if re.match(r"[_A-Za-z0-9]",p[j]):
                        while j>=0 and re.match(r"[_A-Za-z0-9]",p[j]):
                            j-=1
                        start=j+1
                        if start<end:
                            if p[start:end] not in KEYWORDS:
                                if not re.match("^[_A-Z]+$",p[start:end]):
                                    return start,end
            
            j-=1
    return None,None

def run():
    
    fields=find_fields(FIELD_SEARCH_PATH)
    
    
    '''
    dbg_inst=""
    
    for l in goodlines:
        if l!="":
            i=0
            find0=False
            find1=False
            while i<len(l) and l[i]!=":":
                find0=True
                i+=1
            j=i
            while l[j]!='/':
                j-=1
            i+=1
            while i<len(l) and l[i]!=":":
                if find0:
                    find1=True
                i+=1
            if find1:
                dbg_inst+="b "+l[:i]+"\n"
                print "b "+l[:i]+"\n"
    f=file("dbg_inst","w")
    f.write(dbg_inst)
    f.close()
    print dbg_inst
    '''
    '''
    p2 = Popen('grep "struct [_A-Za-z][_0-9A-Za-z]* {" -rn', stdin=p1.stdout,
                          stdout=PIPE)
  
    '''
    #cmd1='find '+project_path+' -name "*.[ch]" |grep "struct [_A-Za-z][_0-9A-Za-z]* {" -rn |sed "/\/tests\//d"|sed "/const struct/d"'
    #typedef_structs=os.popen(cmd1).readlines()
    #goodline, err = p2.communicate()
    #print goodline
    '''
    p = subprocess.Popen(cmd1, stdout=subprocess.PIPE, shell=True,
                         stderr=subprocess.PIPE, close_fds=True)
    log = logging.getLogger()
    log.debug('running:%s' % cmd1)
    goodline, err = p.communicate()
    log.debug(goodline)
    if p.returncode != 0:
        log.critical("Non zero exit code:%s executing: %s" % (p.returncode, cmd1))
    return p.stdout
    '''
    #str='find /home/yangke/Program/Winux/wine-3.0.1/dlls/ -name "*.[ch]"'
    #print os.popen(str).readlines()
    #print "#############"
    '''
    cmd2='find '+project_path+' -name "*.[ch]" |grep "typedef struct {" -rn|sed "/\\/tests\\//d" |sed "/const struct/d"'
    struct_xs=os.popen(cmd2).readlines()
    print cmd2
    print len(typedef_structs)
    print len(struct_xs)
    '''

if __name__ == '__main__':
    
    run()