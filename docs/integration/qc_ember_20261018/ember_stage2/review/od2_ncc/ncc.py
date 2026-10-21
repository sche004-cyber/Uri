from PIL import Image; import numpy as np
shot=Image.open('shot_img.png').convert('L')   # 1080x1080 embedded image
tmpl_full=shot.crop((200,150,900,910))          # character region (700x760)
sheet=Image.open('sheet.png').convert('L')
panels={'IDLE':(0,0,448,600),'JOYFUL':(448,0,896,600),'FIERCE':(0,600,448,1200),'DEPLETED':(448,600,896,1200)}
def ncc(a,b):
    a=a-a.mean(); b=b-b.mean(); return float((a*b).sum()/np.sqrt((a*a).sum()*(b*b).sum()))
def search(panel_img, D=0.5):
    P=np.asarray(panel_img.resize((int(448*D),int(600*D)),Image.BILINEAR),float)
    best=(-2,None)
    for sc in np.arange(0.24,0.80,0.02):   # template scale relative to panel full-res
        w=int(700*sc*D); h=int(760*sc*D)
        if w>=P.shape[1] or h>=P.shape[0]: continue
        T=np.asarray(tmpl_full.resize((w,h),Image.BILINEAR),float); T=T-T.mean(); tn=np.sqrt((T*T).sum())
        for y in range(0,P.shape[0]-h,2):
            for x in range(0,P.shape[1]-w,2):
                W=P[y:y+h,x:x+w]; Wc=W-W.mean(); d=np.sqrt((Wc*Wc).sum())*tn
                if d==0: continue
                v=(Wc*T).sum()/d
                if v>best[0]: best=(v,(sc,x/D,y/D,w/D,h/D))
    return best
res={}
for name,box in panels.items():
    pimg=sheet.crop(box); v,(sc,x,y,w,h)=search(pimg)
    # recompute at 128x128 per brief
    crop=pimg.crop((int(x),int(y),int(x+w),int(y+h))).resize((128,128),Image.BILINEAR)
    t=tmpl_full.resize((128,128),Image.BILINEAR)
    v128=ncc(np.asarray(crop,float),np.asarray(t,float))
    # gradient-magnitude NCC (structure, less sensitive to global tone)
    def gm(a):
        a=np.asarray(a,float); gy,gx=np.gradient(a); return np.hypot(gx,gy)
    vg=ncc(gm(crop),gm(t))
    res[name]=(v,v128,vg,sc,x,y,w,h); print(name,'search_ncc=%.3f ncc128=%.3f gradncc128=%.3f scale=%.2f box=(%d,%d,%d,%d)'%(v,v128,vg,sc,x,y,w,h))
    crop.save('ncc_%s.png'%name)
tmpl_full.resize((128,128)).save('ncc_tmpl.png')
