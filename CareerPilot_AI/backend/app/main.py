from __future__ import annotations
import io, json, os, re, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator
import jwt
from dotenv import load_dotenv
from docx import Document
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from pypdf import PdfReader
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

load_dotenv()
ROOT=Path(__file__).resolve().parents[2]
FRONTEND=ROOT/"frontend"
UPLOAD_DIR=Path(__file__).resolve().parents[1]/"uploads"
UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
MAX_MB=int(os.getenv("CAREERPILOT_MAX_UPLOAD_MB","8")); MAX_BYTES=MAX_MB*1024*1024
SECRET=os.getenv("CAREERPILOT_SECRET_KEY","local-dev-only-change-this")
DB_URL=os.getenv("CAREERPILOT_DATABASE_URL","sqlite:///./careerpilot.db")
engine=create_engine(DB_URL,connect_args={"check_same_thread":False} if DB_URL.startswith("sqlite") else {},future=True)
SessionLocal=sessionmaker(bind=engine,autoflush=False,autocommit=False,expire_on_commit=False)
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    email:Mapped[str]=mapped_column(String(320),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
    created_at:Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc))
class Analysis(Base):
    __tablename__="analyses"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    cv_filename:Mapped[str]=mapped_column(String(255))
    job_title:Mapped[str]=mapped_column(String(255))
    job_description:Mapped[str]=mapped_column(Text)
    cv_text:Mapped[str]=mapped_column(Text)
    score:Mapped[int]=mapped_column(Integer)
    result_json:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc))
Base.metadata.create_all(engine)
pwd=CryptContext(schemes=["bcrypt"],deprecated="auto"); bearer=HTTPBearer(auto_error=False)
app=FastAPI(title="CareerPilot AI API",version="0.1.0",description="Local CV/job matching MVP")
origins=[x.strip() for x in os.getenv("CAREERPILOT_FRONTEND_ORIGINS","http://127.0.0.1:8000,http://localhost:8000").split(",") if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
def get_db()->Generator[Session,None,None]:
    db=SessionLocal()
    try: yield db
    finally: db.close()
class AuthIn(BaseModel):
    email:str=Field(min_length=5,max_length=320)
    password:str=Field(min_length=8,max_length=128)
def token_for(user):
    now=datetime.now(timezone.utc)
    return jwt.encode({"sub":str(user.id),"email":user.email,"iat":now,"exp":now+timedelta(hours=12)},SECRET,algorithm="HS256")
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(get_db)):
    if not credentials: raise HTTPException(401,"Please log in to continue.")
    try: payload=jwt.decode(credentials.credentials,SECRET,algorithms=["HS256"]); uid=int(payload["sub"])
    except Exception: raise HTTPException(401,"Session invalid or expired. Please log in again.")
    user=db.get(User,uid)
    if not user: raise HTTPException(401,"User account not found.")
    return user
def norm(s): return re.sub(r"\s+"," ",s.lower()).strip()
SYN={"javascript":{"javascript","js"},"typescript":{"typescript","ts"},"machine learning":{"machine learning","ml"},"natural language processing":{"natural language processing","nlp"},"communication":{"communication","communicate","interpersonal"},"sql":{"sql","structured query language"},"data analysis":{"data analysis","analyze data","analyse data"},"deep learning":{"deep learning","neural networks"}}
def found(term,text):
    return any(re.search(r"(?<![a-z0-9])"+re.escape(a)+r"(?![a-z0-9])",text) for a in SYN.get(term.lower(),{term.lower()}))
CATALOG=["Python","Java","JavaScript","TypeScript","SQL","PostgreSQL","Excel","Power BI","Tableau","Machine Learning","Deep Learning","Natural Language Processing","Data Analysis","Statistics","Communication","Project Management","Git","Docker","FastAPI","React","Next.js","TensorFlow","PyTorch","AWS","Azure","Leadership"]
def extract_skills(job):
    lines=re.split(r"[\n.;•]+",job); all_found=[s for s in CATALOG if found(s,job.lower())]
    pref=[]; req=[]
    for skill in all_found:
        matching=[norm(line) for line in lines if found(skill,line.lower())]
        (pref if any(any(k in line for k in ["preferred","nice to have","bonus","desirable"]) for line in matching) else req).append(skill)
    return req,pref
def build_match(cv_text,job_text):
    cv=norm(cv_text); req,pref=extract_skills(job_text)
    rf=[s for s in req if found(s,cv)]; rm=[s for s in req if s not in rf]
    pf=[s for s in pref if found(s,cv)]; pm=[s for s in pref if s not in pf]
    exp=any(x in cv for x in ["experience","internship","worked","employment","professional"])
    proj=any(x in cv for x in ["project","developed","built","implemented","research"])
    edu=any(x in cv for x in ["bachelor","master","b.sc","m.sc","degree","certification","certified"])
    parts=[]
    if req: parts.append((.60,len(rf)/len(req)))
    if pref: parts.append((.20,len(pf)/len(pref)))
    parts.extend([(.10,float(exp)),(.05,float(proj)),(.05,float(edu))])
    score=round(100*sum(w*v for w,v in parts)/sum(w for w,v in parts))
    return {"score":score,"score_note":"A transparent keyword/evidence estimate, not a prediction of hiring success.","components":{"required_skill_coverage":{"weight":.6,"matched":len(rf),"total":len(req)},"preferred_skill_coverage":{"weight":.2,"matched":len(pf),"total":len(pref)},"experience_evidence":{"weight":.1,"found":exp},"project_evidence":{"weight":.05,"found":proj},"education_evidence":{"weight":.05,"found":edu}},"required_skills_found":rf,"required_skills_missing":rm,"preferred_skills_found":pf,"preferred_skills_missing":pm,"recommendations":[f"If accurate, add concrete evidence for {s} in a project or work bullet." for s in rm[:8]],"detected_requirements_note":"Skill detection is heuristic; review the job description and correct classification errors."}
def extract_text(filename,data):
    suffix=Path(filename).suffix.lower()
    try:
        if suffix==".pdf": text="\\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
        elif suffix==".docx":
            d=Document(io.BytesIO(data)); text="\\n".join(p.text for p in d.paragraphs)
            for table in d.tables: text+="\\n"+"\\n".join(" ".join(c.text for c in row.cells) for row in table.rows)
        else: raise HTTPException(415,"Unsupported file type. Upload PDF or DOCX.")
    except HTTPException: raise
    except Exception: raise HTTPException(400,"Could not read this document. Please try a valid PDF or DOCX.")
    if not text.strip(): raise HTTPException(422,"No selectable text found. This may be a scanned PDF; OCR is not configured.")
    return text.strip()[:200000]
@app.get("/health")
def health(): return {"status":"ok","service":"careerpilot-ai-api"}
@app.get("/",include_in_schema=False)
def home(): return FileResponse(FRONTEND/"index.html")
@app.post("/api/auth/register",status_code=201)
def register(data:AuthIn,db:Session=Depends(get_db)):
    email=data.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$",email): raise HTTPException(422,"Enter a valid email address.")
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,"An account with this email already exists.")
    u=User(email=email,password_hash=pwd.hash(data.password)); db.add(u); db.commit(); db.refresh(u)
    return {"access_token":token_for(u),"token_type":"bearer","email":u.email}
@app.post("/api/auth/login")
def login(data:AuthIn,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==data.email.strip().lower()))
    if not u or not pwd.verify(data.password,u.password_hash): raise HTTPException(401,"Email or password is incorrect.")
    return {"access_token":token_for(u),"token_type":"bearer","email":u.email}
@app.get("/api/me")
def me(user=Depends(current_user)): return {"id":user.id,"email":user.email,"created_at":user.created_at.isoformat()}
@app.post("/api/analyze",status_code=201)
async def analyze(job_title:str=Form("Untitled role"),job_description:str=Form(...),cv_file:UploadFile=File(...),user=Depends(current_user),db:Session=Depends(get_db)):
    if not job_description.strip(): raise HTTPException(422,"Enter a job description.")
    filename=cv_file.filename or "cv"; suffix=Path(filename).suffix.lower()
    if suffix not in {".pdf",".docx"}: raise HTTPException(415,"Unsupported file type. Upload PDF or DOCX.")
    if (cv_file.content_type or "") not in {"application/pdf","application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/octet-stream"}: raise HTTPException(415,"File content type does not match PDF or DOCX.")
    data=await cv_file.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES: raise HTTPException(413,f"File exceeds the {MAX_MB} MB limit.")
    cv=extract_text(filename,data); (UPLOAD_DIR/(uuid.uuid4().hex+suffix)).write_bytes(data)
    result=build_match(cv,job_description)
    rec=Analysis(user_id=user.id,cv_filename=filename[:255],job_title=(job_title.strip() or "Untitled role")[:255],job_description=job_description[:50000],cv_text=cv,score=result["score"],result_json=json.dumps(result))
    db.add(rec); db.commit(); db.refresh(rec)
    result.update({"analysis_id":rec.id,"job_title":rec.job_title,"cv_filename":rec.cv_filename,"created_at":rec.created_at.isoformat()})
    return result
@app.get("/api/analyses")
def list_analyses(user=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Analysis).where(Analysis.user_id==user.id).order_by(Analysis.created_at.desc())).all()
    return [{"id":r.id,"job_title":r.job_title,"cv_filename":r.cv_filename,"score":r.score,"created_at":r.created_at.isoformat()} for r in rows]
@app.get("/api/analyses/{analysis_id}")
def get_analysis(analysis_id:int,user=Depends(current_user),db:Session=Depends(get_db)):
    r=db.get(Analysis,analysis_id)
    if not r or r.user_id!=user.id: raise HTTPException(404,"Analysis not found.")
    result=json.loads(r.result_json); result.update({"analysis_id":r.id,"job_title":r.job_title,"cv_filename":r.cv_filename,"created_at":r.created_at.isoformat()}); return result
@app.delete("/api/analyses/{analysis_id}",status_code=204)
def delete_analysis(analysis_id:int,user=Depends(current_user),db:Session=Depends(get_db)):
    r=db.get(Analysis,analysis_id)
    if not r or r.user_id!=user.id: raise HTTPException(404,"Analysis not found.")
    db.delete(r); db.commit()
