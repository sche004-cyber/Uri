import time, os, json, tracemalloc, psutil, io
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from pptx import Presentation
from pptx.util import Inches, Pt as PPt
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
import pymupdf, pypdf, pytesseract
from PIL import Image
pytesseract.pytesseract.tesseract_cmd=r"C:\Program Files\Tesseract-OCR\tesseract.exe"
R={}
proc=psutil.Process()
def t(name,fn):
    m0=proc.memory_info().rss; s=time.perf_counter(); out=fn(); R[name]={"ms":round((time.perf_counter()-s)*1000,1),"rss_delta_mb":round((proc.memory_info().rss-m0)/2**20,1)}; return out
rows=[("Name","Designation","Station","Date of joining")]+[(f"Officer {i}",["Tahsildar","Deputy Tahsildar","Clerk"][i%3],f"Taluk {i%7}",f"2026-0{1+i%9}-1{i%9}") for i in range(40)]
def letter():
    d=Document(); s=d.sections[0]; s.left_margin=s.right_margin=Cm(2.5)
    hp=s.header.paragraphs[0]; hp.text="GOVERNMENT OF EXAMPLE STATE\nOffice of the District Collector"; hp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    fp=s.footer.paragraphs[0]; fp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=fp.add_run(); 
    for kind,txt in (("begin",None),(None," PAGE "),("end",None)):
        if kind: e=OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"),kind); r._r.append(e)
        else: e=OxmlElement("w:instrText"); e.set(qn("xml:space"),"preserve"); e.text=txt; r._r.append(e)
    d.add_paragraph("No. A1/1234/2026\t\tDated: 14-10-2026")
    d.add_heading("OFFICE ORDER",1).alignment=WD_ALIGN_PARAGRAPH.CENTER
    d.add_paragraph("Sub: Transfers and postings — orders issued.")
    for i in range(3): d.add_paragraph("In exercise of the powers conferred, the following officers are transferred and posted as shown below with immediate effect. "*3)
    tb=d.add_table(rows=0,cols=4); tb.style="Table Grid"
    for row in rows:
        c=tb.add_row().cells
        for j,v in enumerate(row): c[j].text=v
    d.add_paragraph("\nDistrict Collector").alignment=WD_ALIGN_PARAGRAPH.RIGHT
    d.save("order.docx"); return "order.docx"
t("docx_create_order_40rows",letter)
def mailmerge():
    for i,row in enumerate(rows[1:]):
        d=Document("order.docx")
        for p in d.paragraphs:
            if p.text.startswith("Sub:"): p.text=f"Sub: Posting of {row[0]} as {row[1]}"
        d.save(f"merge_{i}.docx")
t("docx_mailmerge_40_letters",mailmerge)
def edit_preserve():
    d=Document("order.docx"); d.paragraphs[2].runs[0].text=d.paragraphs[2].runs[0].text.replace("Transfers","Transfer"); d.save("order_edit.docx")
t("docx_edit_reopen_save",edit_preserve)
def deck():
    p=Presentation(); p.slide_width=Inches(13.333); p.slide_height=Inches(7.5)
    for k in range(10):
        s=p.slides.add_slide(p.slide_layouts[1]); s.shapes.title.text=f"Section {k+1}"; s.placeholders[1].text="Point one\nPoint two\nPoint three"
        s.notes_slide.notes_text_frame.text="Speaker notes"
    s=p.slides.add_slide(p.slide_layouts[5]); s.shapes.title.text="Postings by designation"
    cd=CategoryChartData(); cd.categories=["Tahsildar","Deputy Tahsildar","Clerk"]; cd.add_series("Count",(14,13,13))
    s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED,Inches(1),Inches(1.5),Inches(11),Inches(5.5),cd)
    p.save("deck.pptx")
t("pptx_create_11_slides_chart",deck)
def mkpdf():
    doc=pymupdf.open(); 
    for k in range(20):
        pg=doc.new_page(); pg.insert_text((72,72),f"Notice {k} — Corrigendum to tender No. 55/2026",fontsize=12)
        y=110
        for r in rows[:15]:
            x=72
            for v in r: pg.insert_text((x,y),v,fontsize=9); x+=120
            y+=16
    doc.save("notice.pdf"); return "notice.pdf"
t("pdf_generate_20p",mkpdf)
t("pdf_text_extract_20p",lambda: [p.get_text() for p in pymupdf.open("notice.pdf")])
t("pdf_find_tables_p1",lambda: len(pymupdf.open("notice.pdf")[0].find_tables().tables))
def merge():
    w=pypdf.PdfWriter(); [w.append("notice.pdf") for _ in range(3)]; w.write("merged.pdf")
t("pypdf_merge_3x20p",merge)
def ocr():
    pix=pymupdf.open("notice.pdf")[0].get_pixmap(dpi=200); pix.save("p1.png"); return pytesseract.image_to_string(Image.open("p1.png"))[:80]
R["ocr_sample"]=t("tesseract_ocr_1page_200dpi",ocr)
R["render_pdf_page_png"]=t("pymupdf_render_page_150dpi",lambda: pymupdf.open("notice.pdf")[0].get_pixmap(dpi=150).save("r.png") or "ok")
try:
    R["pymupdf_open_docx"]=str(pymupdf.open("order.docx").page_count)
except Exception as e: R["pymupdf_open_docx"]="FAIL "+type(e).__name__+": "+str(e)[:120]
R["peak_rss_mb"]=round(proc.memory_info().rss/2**20,1)
R["versions"]={"python-docx":__import__("docx").__version__ if hasattr(__import__("docx"),"__version__") else "1.2.0","python-pptx":__import__("pptx").__version__,"pymupdf":pymupdf.VersionBind,"pypdf":pypdf.__version__,"tesseract":str(pytesseract.get_tesseract_version())}
print(json.dumps(R,indent=1))
