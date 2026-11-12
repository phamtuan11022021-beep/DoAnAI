"""Build the prose-led report with eight figures and consistent portrait pages."""
from pathlib import Path
import json,re
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from report_diagrams_compact import generate

OUT=Path(__file__).resolve().parent

def field(p,instruction,display=''):
 f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),instruction)
 r=OxmlElement('w:r');t=OxmlElement('w:t');t.text=str(display);r.append(t);f.append(r);p._p.append(f)

def build():
 manifest=generate();doc=Document();s=doc.sections[0]
 s.page_width=Cm(21);s.page_height=Cm(29.7)
 s.left_margin=Cm(3);s.right_margin=Cm(2);s.top_margin=Cm(2.2);s.bottom_margin=Cm(2.2)
 s.header_distance=Cm(.8);s.footer_distance=Cm(1);s.different_first_page_header_footer=True
 for st in doc.styles:
  if st.type!=1:continue
  st.font.name='Times New Roman';st.font.color.rgb=RGBColor(0,0,0)
  fonts=st._element.get_or_add_rPr().get_or_add_rFonts()
  for attr in list(fonts.attrib):
   if 'theme' in attr.lower():del fonts.attrib[attr]
  for k in ('ascii','hAnsi','eastAsia','cs'):fonts.set(qn('w:'+k),'Times New Roman')
  for border in st._element.xpath('./w:pPr/w:pBdr'):border.getparent().remove(border)
 normal=doc.styles['Normal'];normal.font.size=Pt(13)
 pf=normal.paragraph_format;pf.line_spacing=1.3;pf.space_after=Pt(6);pf.first_line_indent=Cm(.75);pf.widow_control=True
 for name,size in [('Title',18),('Heading 1',15),('Heading 2',13.5),('Heading 3',13)]:
  st=doc.styles[name];st.font.size=Pt(size);st.font.bold=True
  st.paragraph_format.first_line_indent=Cm(0);st.paragraph_format.space_before=Pt(10)
  st.paragraph_format.space_after=Pt(6);st.paragraph_format.keep_with_next=True
  st.paragraph_format.keep_together=True
 doc.styles['Heading 1'].paragraph_format.page_break_before=True
 cap=doc.styles['Caption'];cap.font.size=Pt(11);cap.font.italic=True
 cap.paragraph_format.first_line_indent=Cm(0);cap.paragraph_format.line_spacing=1.1;cap.paragraph_format.space_after=Pt(8)
 # Avoid a duplicated header on every page of an academic report.
 foot=s.footer.paragraphs[0];foot.alignment=WD_ALIGN_PARAGRAPH.CENTER;foot.paragraph_format.first_line_indent=Cm(0);field(foot,'PAGE','1')
 doc.core_properties.title='Xây dựng website tư vấn chọn trường và ngành học ứng dụng trí tuệ nhân tạo UniConnect AI'
 doc.core_properties.author='';doc.core_properties.subject='Báo cáo đề tài UniConnect AI'
 figures=[];tables=[];counts={'Figure':0,'Table':0};heading=''

 def rich(p,text):
  for i,chunk in enumerate(re.split(r'\*\*(.*?)\*\*',text)):
   r=p.add_run(chunk.replace('`',''));r.bold=(i%2==1)

 def caption(kind,title):
  counts[kind]+=1;p=doc.add_paragraph(style='Caption')
  p.alignment=WD_ALIGN_PARAGRAPH.CENTER
  p.add_run('Hình ' if kind=='Figure' else 'Bảng ');field(p,'SEQ '+kind+' \\* ARABIC',counts[kind]);p.add_run(' '+title)
  return p

 def table(block):
  rows=[[x.strip().replace('`','') for x in line.strip('|').split('|')] for line in block]
  rows=[r for r in rows if not all(re.fullmatch(':?-+:?',x.replace(' ','')) for x in r)]
  n=len(rows[0]);widths=([8.2,7.8] if rows[0][0]=='Bảng' else [4.2,11.8] if rows[0][0] in ('Nhóm chức năng','Điều kiện','Mô hình','Năm') else [9.2,6.8]) if n==2 else [3.1,8.5,4.4] if n==3 else [5.4,2.3,2.3,2.1,3.9]
  widths=[x*16/sum(widths) for x in widths]
  title=heading.split(' ',1)[-1] if re.match(r'^\d+\.\d+ ',heading) else heading
  if rows[0][0]=='Năm':title='Phân bố bản ghi chương trình theo năm'
  cap=caption('Table',title);cap.paragraph_format.keep_with_next=True
  t=doc.add_table(rows=1,cols=n);t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
  for j,w in enumerate(widths):t.columns[j].width=Cm(w)
  for i,row in enumerate(rows):
   cells=t.rows[0].cells if i==0 else t.add_row().cells
   for j,value in enumerate(row):
    cell=cells[j];cell.width=Cm(widths[j]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
    p=cell.paragraphs[0];p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.line_spacing=1.12
    p.paragraph_format.space_before=Pt(2);p.paragraph_format.space_after=Pt(2)
    p.paragraph_format.keep_with_next=(i==0 or (len(rows)<=10 and i<len(rows)-1))
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER if i==0 or (n>=5 and j>0) else WD_ALIGN_PARAGRAPH.LEFT
    r=p.add_run(value);r.font.size=Pt(11 if n>=5 else 11.5);r.bold=(i==0)
    pr=cell._tc.get_or_add_tcPr();shd=OxmlElement('w:shd');shd.set(qn('w:fill'),'EDEDED' if i==0 else 'FFFFFF');pr.append(shd)
    margins=OxmlElement('w:tcMar')
    for edge in ('top','left','bottom','right'):
     e=OxmlElement('w:'+edge);e.set(qn('w:w'),'40' if edge in ('top','bottom') else '70');e.set(qn('w:type'),'dxa');margins.append(e)
    pr.append(margins)
    borders=OxmlElement('w:tcBorders')
    for edge in ('top','left','bottom','right'):
     e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
    pr.append(borders)
   trpr=t.rows[i]._tr.get_or_add_trPr();trpr.append(OxmlElement('w:cantSplit'))
   if i==0:trpr.append(OxmlElement('w:tblHeader'))
  spacer=doc.add_paragraph();spacer.paragraph_format.line_spacing=Pt(1);spacer.paragraph_format.space_after=Pt(5);spacer.add_run().font.size=Pt(1)
  tables.append({'number':counts['Table'],'title':title,'rows':len(rows)-1})

 def picture(key):
  info=manifest[key];p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
  pf=p.paragraph_format;pf.first_line_indent=Cm(0);pf.keep_with_next=True;pf.space_before=Pt(4);pf.space_after=Pt(3);pf.line_spacing=1
  width=14.5 if key=='gon_ui' else 16
  pic=p.add_run().add_picture(str(OUT/info['image']),width=Cm(width));pic._inline.docPr.set('descr',info['title'])
  caption('Figure',info['title'])
  figures.append({'number':counts['Figure'],'key':key,'title':info['title'],'width_cm':width,'height_cm':width*info['height']/info['width']})

 source=(OUT/'BAO_CAO_UNICONNECT_AI_BAN_CHINH_SUA.md').read_text(encoding='utf-8')
 cover,body=source.split('## Tóm tắt đề tài',1)
 p=doc.add_paragraph('[CẦN ĐIỀN TÊN TRƯỜNG]');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Cm(0)
 p=doc.add_paragraph('[CẦN ĐIỀN KHOA HOẶC BỘ MÔN]');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Cm(0)
 p=doc.add_paragraph('BÁO CÁO ĐỀ TÀI');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.space_before=Cm(1.5);p.runs[0].bold=True
 title=cover.splitlines()[0][2:]
 p=doc.add_paragraph(title,style='Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_before=Cm(.6);p.paragraph_format.space_after=Cm(1)
 for line in cover.splitlines()[1:]:
  if not line.strip() or line.startswith('**'):continue
  p=doc.add_paragraph(line);p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.space_after=Pt(10)
 p=doc.add_paragraph('MỤC LỤC',style='Title');p.paragraph_format.page_break_before=True
 p=doc.add_paragraph();p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.space_after=Pt(0)
 field(p,'TOC \\o "1-2" \\h \\z \\u','Mục lục được cập nhật trong Word')
 p=doc.add_paragraph('DANH MỤC HÌNH VÀ BẢNG',style='Title');p.paragraph_format.page_break_before=True
 for title,instruction in [('Danh mục hình','TOC \\h \\z \\c "Figure"'),('Danh mục bảng','TOC \\h \\z \\c "Table"')]:
  p=doc.add_paragraph(title);p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.keep_with_next=True;p.runs[0].bold=True
  p=doc.add_paragraph();p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.space_after=Pt(0);field(p,instruction,'Danh mục được cập nhật trong Word')
 lines=('## Tóm tắt đề tài'+body).splitlines();i=0;first=True
 while i<len(lines):
  line=lines[i].strip();i+=1
  if not line:continue
  if line.startswith('|'):
   block=[line]
   while i<len(lines) and lines[i].strip().startswith('|'):block.append(lines[i].strip());i+=1
   table(block);continue
  if line.startswith('{{FIGURE:'):picture(line[9:-2]);continue
  if line.startswith('# '):heading=line[2:];doc.add_paragraph(heading,style='Heading 1');continue
  if line.startswith('## '):
   heading=line[3:];p=doc.add_paragraph(heading,style='Heading 2')
   if first:p.paragraph_format.page_break_before=True;first=False
   continue
  p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY;rich(p,line)
  if re.match(r'^\[\d+\]',line):
   p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.line_spacing=1.15;p.alignment=WD_ALIGN_PARAGRAPH.LEFT
   for r in p.runs:r.font.size=Pt(11.5)
 settings=doc.settings.element;update=OxmlElement('w:updateFields');update.set(qn('w:val'),'true');settings.append(update)
 doc.save(OUT/'BAO_CAO_UNICONNECT_AI_BAN_CHINH_SUA.docx')
 record={'figures':figures,'tables':tables,'total_figures':len(figures),'total_tables':len(tables),'sections':len(doc.sections),'source_words':len(source.split())}
 (OUT/'so_do/report_inventory.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in record.items() if k not in ('figures','tables')},ensure_ascii=False))

if __name__=='__main__':build()
