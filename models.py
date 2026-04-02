from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Admin(Base):
    __tablename__ = 'admins'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)

class Job(Base):
    __tablename__ = 'jobs'
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    location = Column(String(255))
    responsibilities = Column(JSON, nullable=True)  # JSON list
    qualifications = Column(JSON, nullable=True)    # JSON list
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Candidate(Base):
    __tablename__ = 'candidates'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(50))
    linkedin = Column(String(255))
    website = Column(String(255))
    password = Column(String(255), nullable=True)
    resumes = Column(JSON, nullable=True)  # JSON list
    skills = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Application(Base):
    __tablename__ = 'applications'
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('jobs.id'))
    candidate_id = Column(Integer, ForeignKey('candidates.id'))
    cover_letter = Column(Text)
    resume_url = Column(String(1024))
    ats_score = Column(Integer, default=0)
    ats_analysis = Column(Text, nullable=True)
    status = Column(String(50), default='Applied')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship('Job')
    candidate = relationship('Candidate')

class Interview(Base):
    __tablename__ = 'interviews'
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey('applications.id'))
    scheduled_for = Column(DateTime(timezone=True))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
