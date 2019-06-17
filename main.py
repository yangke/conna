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
import time
PROGRAM=4

if PROGRAM==0:    
    PROJECT_PATH="/home/yangke/Program/test/X11/gtk+/gtk+-2.24.30-all/gtk+-2.24.30/";
    FIELD_SEARCH_PATH="/home/yangke/Program/test/X11/gtk+/gtk+-2.24.30-all/gtk+-2.24.30/";
elif PROGRAM==1:
    PROJECT_PATH="/home/yangke/Program/test/X11/X11/libX11-1.6.3";
    FIELD_SEARCH_PATH="/home/yangke/Program/test/X11/X11/libX11-1.6.3";
elif PROGRAM==3:    
    PROJECT_PATH="/home/yangke/Program/Winux/wine-3.0.1/";#dlls
    FIELD_SEARCH_PATH="/home/yangke/Program/Winux/wine-3.0.1/";
elif PROGRAM==4:
    PROJECT_PATH="/home/yangke/Program/Winux/wine-4.0/";
    FIELD_SEARCH_PATH="/home/yangke/Program/Winux/wine-4.0/";


KEYWORDS="switch if for while return do".split()
IGNORE_SINKS="TRACE trace FIXME fixme WARN warn ERR err debug Debug dbg Dbg cmp Cmp free Free sizeof".split()
#"debugstr_w strncmp strcmpi strcmpiW SysFreeString SHFree HeapFree heap_free ME_DestroyString heap_realloc".split()
NEED_MOD_TARGETS_CHECK_FUNCS="strcpy strcpyW strncpy strncpyW lstrcpynA lstrcpynW lstrcpyA lstrcpyW memcpy memmove ME_InsertString".split()
DANGER_FUNC="strcpy strcpyW strncpy strncpyW lstrcpynA lstrcpynW lstrcpyA lstrcpyW memcpy".split() #strlen 

class FuncType:
    NORMAL=0, # funcname()
    PMEMBER=1,# ->funcname()
    MEMBER=2  # .funcname()

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
        print str
        array=str.split(",");
        i=0
#        num=a_type.count("*")
#         while i<len(array):
#             str=array[i]
#             while num > 0:
#                 str=str[str.find("*")+1:].strip()
#                 num-=1
#             array[i]=str.replace('*','').strip()
#             i+=1
        while i<len(array):
            array[i]=array[i].replace('*','').strip()
            i+=1  
        return array
    else:
        return [str.replace('*','').strip()]
    
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
    depth=0;
    commas_count=0
    while i>=0:
        if code[i]==")":
            depth+=1
        elif code[i]=="(":
            if depth==0:
                i-=1
                break 
            # func(...,(...),target->string)
            #     ^
            #     i
            # depth>0:
            depth-=1 
            # func(...,(...),target->string)
            #          ^
            #          i
        elif code[i]==',' and depth==0:
            commas_count+=1
        i-=1;
    
    if i>=0:
        while i>=0 and re.match(r'\s', code[i]):
            i-=1
        end=i+1
        is_func=False
        while i>=0 and re.match(r'[_a-z0-9A-Z]', code[i]):
            is_func=True
            i-=1
        if i>=-1 and is_func:
            start=i+1
            while re.match(r'\s', code[i]):
                i-=1
            
            func_name=code[start:end]
            
            if func_name=="":
                return None,None,None
            
            type=FuncType.NORMAL
            if i>=0 and code[i]=='.':
                type=FuncType.MEMBER
            elif i-1>=0 and code[i-1:i+1]=='->':
                type=FuncType.PMEMBER
                
            
            if func_name not in KEYWORDS:
                for ig in IGNORE_SINKS:
                    if func_name.find(ig)!=-1:
                        return None,None,None
                #if func_name=="memcpy":
                #    print  func_name,code
                return func_name,commas_count,type
      
    return None,None,None                     

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
            # specificially for wine ## start ##
            if "shfldr_fs.c" in filepath and linenum=='60':
                target= "sPathTarget"
            # specificially for wine ## end ##
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
                
                m1=re.match(r"^WCHAR \*.*",ll[i])
                m2=re.match(r"\s*[^_A-Za-z0-9]WCHAR \*.*",ll[i])
                if m1 or m2:
                    array=get_var_name(ll[i],"WCHAR *")
                    fields.extend(array)
                    print array
                    
                m3=re.match(r"^CHAR \*.*",ll[i])
                m4=re.match(r"\s*[^_A-Za-z0-9]CHAR \*.*",ll[i])
                if m3 or m4:
                    array=get_var_name(ll[i],"CHAR *")
                    fields.extend(array)
                    print array
                
                m5=re.match(r"^wchar \*.*",ll[i])
                m6=re.match(r"\s*[^_A-Za-z0-9]wchar \*.*",ll[i])
                if m5 or m6:
                    str=get_var_name(ll[i],"wchar *")
                    fields.extend(array)
                    print array
                
                m7=re.match(r"^char \*.*",ll[i])
                m8=re.match(r"\s*[^_A-Za-z0-9]char \*.*",ll[i])
                if m7 or m8:
                    array=get_var_name(ll[i]," char *")
                    fields.extend(array)
                    #fields.append(array)
                    #print ll[i]
                    print array
                
                m9=re.match(r"^gchar \*.*",ll[i])
                m10=re.match(r"\s*[^_A-Za-z0-9]gchar \*.*",ll[i])
                if m9 or m10:
                    array=get_var_name(ll[i]," gchar *")
                    fields.extend(array)
                    #fields.append(array)
                    #print ll[i]
                    print array
                
                m11=re.match(r"^LPWSTR .*",ll[i])
                m12=re.match(r"\s*[^_A-Za-z0-9]LPWSTR .*",ll[i])
                if m11 or m12:
                    array=get_var_name(ll[i],"LPWSTR")
                    if target=="sPathTarget":
                        assert(array[0]==target)
                    if len(array)>0:
                        fields.extend(array)
                        print array
                        
                m13=re.match(r"^LPSTR .*",ll[i])
                m14=re.match(r"\s*[^_A-Za-z0-9]LPSTR .*",ll[i])
                if m13 or m14:
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
    #print "mememmememem"
    #$print prefix[-10:]
    #if prefix[-10:][0:9]=="ame) + 1;":
    #    print prefix
        
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
            #Add Code 
            if j>0 and re.match(r"[_A-Za-z0-9];",p[j-1:j+1]):
                while j>=0 and p[j]!=")":
                    j-=1;
                
            #End Add Code
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
def check_return_length(field_name,str):
    #print str
    m=re.search(r"=\s*[_A-Za-z0-9]*strlen[_A-Za-z0-9]*\s*\(.*\->"+field_name.replace("_",r"\_"),str)
    if m:
        i=m.span()[0]-1
        if i<0: return False
        end =i
        while re.match(r"\s",str[i]) and i>0:
            i-=1
        flag=True
        while re.match(r"[_A-Za-z0-9]",str[i]) and i>0:
            flag=False
            i-=1
        if flag:
            return False
        len_name=str[i:end].strip()
        suffix=str[m.span()[1]:]
        m2=re.search(r"if\s*\([^\{\}\(\)]"+len_name.replace("_",r"\_"),suffix)
        if m2:
            return True
    return False
def get_length_field(code, end_of_target):
    i=end_of_target
    while i<len(code) and re.match(r"\s",code[i]): 
        i+=1
    
    if i<len(code) and code[i]==",":
        i+=1
        start=i
        while i<len(code):
            if re.match(r"\)",code[i]):
                field=code[start:i].strip()
                if field =="":
                    return None
                return field
            i+=1
    return None    
        
def run():
    
    fields=find_fields(FIELD_SEARCH_PATH)
    
    out=''
    dbg_inst=''
    goodlines=[]
    dangerous_lines=[]
    dangerous_count=0
    badline_count=0
    goodline_count=0
    for field_name in fields:
        #if field_name!="sPathTarget":
        #    continue
        p1 = Popen('find '+PROJECT_PATH+' -name "*.[ch]"',
                          stdout=PIPE,shell=True )
        p2 = Popen(['sed "/\/tests\//d"'], stdin=p1.stdout,
                          stdout=PIPE, shell=True)   
        p3 = Popen('xargs grep "\->'+field_name+'.*)" -rn', stdin=p2.stdout,
                          stdout=PIPE,shell=True )
        out1, err1 = p3.communicate()
        #print out1
        lines=out1.strip().split('\n')
        for line in lines:
            triple=line.split(':')
            if len(triple)>2:
                code=line.split(':')[2]
                target_str=r'->'+field_name.lstrip('*').strip()
                end=code.find(target_str)
                if end <0 or end+len(target_str)==len(code):
                    continue
                elif re.match(r'[\._A-Za-z]',code[end+len(target_str)]):
                    continue
                ##############################################################
                # remove the sink pattern like: 
                # "dump_arg(rs, &ins->output,..."
                #                   ^
                #                  end
                #is_sink,index=is_call_sink(code,end)
                if is_call_sink(code,end):
                    continue
                
                callee_name,commas_count,type =get_callee_name(code,end)
                ##############################################################
                # remove the sink pattern caused by reserved copy function: 
                # "memcpy(This->sPathTarget, wszTemp,..."
                #             ^
                #            end
                if callee_name  and type== FuncType.NORMAL:
                    if callee_name in DANGER_FUNC:
                        if "strncpy" or "strcpyn" in callee_name:
                            len_field=get_length_field(code,end+len(target_str))
                            if len_field:
                                cons=len_field.strip().lstrip("sizeof(").rstrip(")").strip()
                                if re.match(r"[\._A-Z0-9]+",cons):
                                    continue
                        if commas_count==0:
                            continue
                        goodlines.append(line)
                        goodline_count+=1
                        
                        ff=file(line.split(':')[0],"r")
                        content=ff.readlines()
                        end_index=int(line.split(':')[1])
                        prefix=''.join(content[:end_index])
                        x,y=findFuncPos(prefix)
                        
                        assert(x!=None)
                        func_name=prefix[x:y]
                        
                        if field_name=="lpszUserName":
                            print "GOY"
                        
                        if (re.search(r'if\s*\(.*strlen.*\->'+field_name+'.*\)',prefix[y:])):
                        #if (re.search(r'if\s*\(.*\->'+field_name+'.*\)',prefix[y:])):
                            print func_name,"80% checked"
                        elif check_return_length(field_name,prefix[y:]):
                            print func_name,"80% checked"
                        else:
                            dangerous_count+=1
                            dangerous_lines.append(callee_name+","+field_name+"\n"+line)
                            print func_name,"100% not check"
                            dbg_inst+="b "+func_name+"\n"
                            out+= callee_name+","+field_name+","+func_name+"\n"
                            out+= line+"\n"
                    #out+= callee_name+","+field_name+","+func_name+"\n"
                    #out+= line+"\n"
                    
            else:
                badline_count+=1           
    print "badline_count:"+str(badline_count)
    print "goodline_count:"+str(goodline_count)
    print "dangerous_count:"+str(dangerous_count)
    
    f=file("./out","w")
    f.write(out);
    f.close()
    f=file("./dbg_inst","w")
    dbg_inst='\n'.join(list(set(dbg_inst.split('\n'))))
    f.write(dbg_inst[1:]);
    f.close()
    
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
    time_start=time.time()
    run()
    time_end=time.time()
    print('totally cost',time_end-time_start)
    
