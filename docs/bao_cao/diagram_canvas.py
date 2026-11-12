"""Deterministic PNG/SVG diagrams and editable schema sources for the report."""
from pathlib import Path
from html import escape
import json, math, re
from PIL import Image, ImageDraw, ImageFont

HERE=Path(__file__).resolve().parent
ASSETS=HERE/'assets'; SOURCES=HERE/'so_do'
ASSETS.mkdir(exist_ok=True); SOURCES.mkdir(exist_ok=True)
FONT='C:/Windows/Fonts/arial.ttf'; BOLD='C:/Windows/Fonts/arialbd.ttf'
MANIFEST={}

class Canvas:
 def __init__(self,key,title,w=1500,h=1050,landscape=False):
  self.key=key; self.title=title; self.w=w; self.h=h; self.landscape=landscape
  self.image=Image.new('RGB',(w,h),'white'); self.d=ImageDraw.Draw(self.image)
  self.svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="white"/>']
  self.nodes={}; self.edges=[]
  self.text(w/2,38,title,30,True)
 def text(self,x,y,text,size=26,bold=False,anchor='mm',color='#172231'):
  f=ImageFont.truetype(BOLD if bold else FONT,size)
  self.d.text((x,y),text,font=f,fill=color,anchor=anchor)
  a='middle' if anchor.startswith('m') else 'start'
  self.svg.append(f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}" text-anchor="{a}" dominant-baseline="middle">{escape(text)}</text>')
 def wrap(self,label,width,size):
  f=ImageFont.truetype(FONT,size); result=[]
  for line in str(label).split('\n'):
   current=''
   for word in line.split(' '):
    trial=(current+' '+word).strip()
    if self.d.textlength(trial,font=f)>width and current: result.append(current); current=word
    else: current=trial
   result.append(current)
  return result
 def rect(self,b,fill='#f0f3f7',stroke='#445367',width=2):
  self.d.rectangle(b,fill=fill,outline=stroke,width=width)
  self.svg.append(f'<rect x="{b[0]}" y="{b[1]}" width="{b[2]-b[0]}" height="{b[3]-b[1]}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')
 def node(self,key,label,x,y,w=320,h=100,kind='process',size=26):
  b=(x,y,x+w,y+h); self.nodes[key]={'box':b,'label':label,'kind':kind}
  fill='#f0f3f7'
  if kind=='decision':
   points=[(x+w/2,y),(x+w,y+h/2),(x+w/2,y+h),(x,y+h/2)]
   self.d.polygon(points,fill='#fff7e8',outline='#445367',width=2)
   self.svg.append(f'<polygon points="{" ".join(f"{a},{b}" for a,b in points)}" fill="#fff7e8" stroke="#445367" stroke-width="2"/>')
  elif kind in ('start','end','usecase','process_circle'):
   self.d.ellipse(b,fill=fill,outline='#445367',width=2)
   self.svg.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="{fill}" stroke="#445367" stroke-width="2"/>')
  elif kind=='store':
   self.rect(b,'#eaf2ef'); self.line([(x+15,y),(x+15,y+h)],arrow=False)
  elif kind=='actor':
   self.d.ellipse((x+w/2-19,y,x+w/2+19,y+38),outline='#445367',width=3)
   self.svg.append(f'<circle cx="{x+w/2}" cy="{y+19}" r="19" fill="white" stroke="#445367" stroke-width="3"/>')
   for p in [[(x+w/2,y+38),(x+w/2,y+100)],[(x+w/2-38,y+62),(x+w/2+38,y+62)],[(x+w/2,y+100),(x+w/2-32,y+137)],[(x+w/2,y+100),(x+w/2+32,y+137)]]: self.line(p,arrow=False)
   self.text(x+w/2,y+167,label,size); return
  else: self.rect(b,'white' if kind=='external' else fill)
  lines=self.wrap(label,w*(.68 if kind=='decision' else .90),size)
  lineh=size*1.28
  if len(lines)*lineh>h-10: raise ValueError(f'Label does not fit {self.key}/{key}: {lines}')
  for i,line in enumerate(lines): self.text(x+w/2,y+h/2+(i-(len(lines)-1)/2)*lineh,line,size)
 def line(self,points,label='',arrow=True,dashed=False,at=None,crow=False):
  color='#455365'
  self.d.line(points,fill=color,width=3)
  self.svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="3"'+(' stroke-dasharray="9 6"' if dashed else '')+'/>')
  end=points[-1]; prev=points[-2]; angle=math.atan2(end[1]-prev[1],end[0]-prev[0]); length=15
  if arrow:
   p=[end,(end[0]-length*math.cos(angle-.45),end[1]-length*math.sin(angle-.45)),(end[0]-length*math.cos(angle+.45),end[1]-length*math.sin(angle+.45))]
   self.d.polygon(p,fill=color); self.svg.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in p)}" fill="{color}"/>')
  if crow:
   for delta in (-.5,.5): self.line([end,(end[0]-23*math.cos(angle+delta),end[1]-23*math.sin(angle+delta))],arrow=False)
  if label:
   x,y=at if at else ((points[0][0]+points[-1][0])/2,(points[0][1]+points[-1][1])/2)
   f=ImageFont.truetype(FONT,23); box=self.d.textbbox((x,y),label,font=f,anchor='mm')
   self.d.rectangle((box[0]-5,box[1]-4,box[2]+5,box[3]+4),fill='white')
   self.svg.append(f'<rect x="{box[0]-5}" y="{box[1]-4}" width="{box[2]-box[0]+10}" height="{box[3]-box[1]+8}" fill="white"/>')
   self.text(x,y,label,23)
 def edge(self,a,b,label='',side_a='bottom',side_b='top',via=None,at=None,arrow=True,crow=False):
  def point(key,side):
   x1,y1,x2,y2=self.nodes[key]['box']
   if self.nodes[key]['kind']=='actor' and side=='right':return ((x1+x2)/2+38,y1+62)
   return {'top':((x1+x2)/2,y1),'bottom':((x1+x2)/2,y2),'left':(x1,(y1+y2)/2),'right':(x2,(y1+y2)/2)}[side]
  self.line([point(a,side_a),*(via or []),point(b,side_b)],label,arrow=arrow,at=at,crow=crow)
  self.edges.append((a,b,label))
 def finish(self,note=''):
  if note: self.text(self.w/2,self.h-28,note,22)
  self.image.save(ASSETS/(self.key+'.png'))
  (SOURCES/(self.key+'.svg')).write_text('\n'.join(self.svg)+ '\n</svg>',encoding='utf-8')
  (SOURCES/(self.key+'.json')).write_text(json.dumps({'title':self.title,'nodes':self.nodes,'edges':self.edges},ensure_ascii=False,indent=2),encoding='utf-8')
  MANIFEST[self.key]={'title':self.title,'image':'assets/'+self.key+'.png','svg':'so_do/'+self.key+'.svg','landscape':self.landscape,'width':self.w,'height':self.h}
