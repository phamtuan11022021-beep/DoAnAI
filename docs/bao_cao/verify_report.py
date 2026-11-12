from pathlib import Path
from zipfile import ZipFile
from lxml import etree
import hashlib,json,re
import pymupdf

root=Path(__file__).resolve().parents[2]
out=root/'docs/bao_cao'
stem='BAO_CAO_UNICONNECT_AI_BAN_CHINH_SUA'
source=(out/(stem+'.md')).read_text(encoding='utf-8')
pdf=pymupdf.open(out/(stem+'.pdf'))
with ZipFile(out/(stem+'.docx')) as z:
 tree=etree.fromstring(z.read('word/document.xml'))
 styles=etree.fromstring(z.read('word/styles.xml'))
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
instructions=[''.join(p.xpath('.//w:instrText/text() | .//w:fldSimple/@w:instr',namespaces=ns)) for p in tree.xpath('//w:p',namespaces=ns)]
images=tree.xpath('//wp:inline',namespaces=ns)
tables=tree.xpath('//w:tbl',namespaces=ns)
schema=json.loads((out/'so_do/schema_mysql.json').read_text(encoding='utf-8'))
blanks=[i+1 for i,p in enumerate(pdf) if len(p.get_text().strip())<30 and not p.get_images()]
edge=[]
for i,p in enumerate(pdf):
 for word in p.get_text('words'):
  if word[0]<15 or word[1]<8 or word[2]>p.rect.width-15 or word[3]>p.rect.height-8:edge.append([i+1,word[4]])
checks={
 'eight_figures':len(images)==8 and len(re.findall(r'\{\{FIGURE:',source))==8,
 'nine_tables':len(tables)==9,
 'seven_chapters':len(re.findall(r'^# Chương ',source,re.M))==7,
 'single_portrait_section':len(tree.xpath('//w:sectPr',namespaces=ns))==1 and all(p.rect.width<p.rect.height for p in pdf),
 'figure_sequence':sum('SEQ Figure' in s for s in instructions)==8,
 'table_sequence':sum('SEQ Table' in s for s in instructions)==9,
 'automatic_indexes':sum(s.strip().startswith('TOC ') for s in instructions)==3,
 'no_blank_pages':not blanks,
 'no_text_at_page_edges':not edge,
 'no_field_errors':not any(x in ''.join(p.get_text() for p in pdf) for x in ('Error!','Lỗi! Không tìm')),
 '27_tables_in_appendix':all(t['name'] in source for t in schema['tables']),
 '33_physical_fk_metadata':sum(bool(c.get('foreign_key')) for t in schema['tables'] for c in t['constraints'].values())==33,
 'short_tables_keep_rows_together':all(all(p.xpath('./w:pPr/w:keepNext',namespaces=ns) for row in table.xpath('./w:tr',namespaces=ns)[:-1] for p in row.xpath('.//w:p',namespaces=ns)) for table in tables if len(table.xpath('./w:tr',namespaces=ns))<=10),
}
record={'date':'2026-11-09','pages':len(pdf),'figures':len(images),'diagrams':7,'screenshots':1,'tables':len(tables),'source_words':len(source.split()),
 'checks':checks,'all_checks_passed':all(checks.values()),'blank_pages':blanks,'edge_text':edge,
 'render':'Microsoft Word via render_report.vbs; canonical renderer diagnosed missing soffice.exe; PDF pages rasterized for visual review.',
 'visual_review':'All 39 pages reviewed in contact sheets; SQL and numeric/schema tables also reviewed in enlarged page renders. No blank pages, clipped page-edge text, detached short table rows or mixed page orientation detected.',
 'scope':'Report revision only; historical software/data/model results are retained with dates, not claimed as a new application test or training run.',
 'remaining':['Fill verified cover identity','Apply faculty-specific administrative forms if required'],
 'sha256':{suffix:hashlib.sha256((out/(stem+suffix)).read_bytes()).hexdigest() for suffix in ('.docx','.pdf','.md')}}
(out/'KIEM_TRA_BAO_CAO_BAN_CHINH_SUA.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False,indent=2))
assert all(checks.values())
