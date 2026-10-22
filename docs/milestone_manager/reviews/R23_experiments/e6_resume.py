from common import *
m=new(); mid="M"+"X"*63; m.create_milestone(mid,"t"*200,objective="o"*3000)
p=m.projection()
for lim in (-5,0,10,59,60,199,200,201,250,500,6000):
    t=views.resume_brief(p,mid,None,lim); print(lim,len(t),len(t)<=max(lim,200))
rc,out=runcli("--home",str(m.home),"resume",mid,"--max-chars","10","--no-tasks"); print("cli",rc,len(out.rstrip("\n")))
m2=new(); m2.create_milestone("MM-A","A",objective="o"*3000); p2=m2.projection()
print("short id", [len(views.resume_brief(p2,"MM-A",None,l)) for l in (0,200,300)])
# a resume with a no-newline huge single line
m3=new(); m3.create_milestone("MM-B","A"*200, objective="x"*4000); p3=m3.projection()
print("single-line", [len(views.resume_brief(p3,"MM-B",None,l)) for l in (200,1000)])
