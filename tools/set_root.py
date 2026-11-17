"""Rewrite the hard-coded workspace root in every file to where you cloned this repo.
Usage: python3 tools/set_root.py /path/to/ai-paper-trading-toolkit"""
import os,sys
OLD='/home/user/workspace'; new=os.path.abspath(sys.argv[1]).rstrip('/')
root=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); n=0
for d,_,fs in os.walk(root):
    if '.git' in d: continue
    for f in fs:
        p=os.path.join(d,f)
        try: s=open(p,encoding='utf-8').read()
        except Exception: continue
        if OLD in s: open(p,'w',encoding='utf-8').write(s.replace(OLD,new)); n+=1
print(f'rewrote {n} files: {OLD} -> {new}')
