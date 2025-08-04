import json
import tempfile
import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from typing import List, Optional, Dict, Any
from langchain_community.document_loaders import PDFPlumberLoader
import uvicorn

from dotenv import load_dotenv

load_dotenv()  # Load .env file

class BasicInfo(BaseModel):
    """Basic contact and personal information"""
    full_name: str = Field("", description="Complete full name")
    email: str = Field("", description="Primary email address")
    phone: Optional[str] = Field(None, description="Phone number (formatted consistently)")
    location: Optional[str] = Field(None, description="City, State/Country")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL if available")
    github_url: Optional[str] = Field(None, description="GitHub profile URL if available")
    portfolio_url: Optional[str] = Field(None, description="Portfolio/website URL if available")

class ProfessionalSummary(BaseModel):
    """Professional summary and career information"""
    summary: Optional[str] = Field(None, description="Professional summary/objective statement (2-3 sentences)")
    career_level: str = Field("Entry-level", description="Entry-level/Mid-level/Senior-level/Executive")
    years_of_experience: int = Field(0, description="Total years of professional experience")

class WorkExperience(BaseModel):
    """Individual work experience entry"""
    company_name: str = Field("", description="Company name")
    job_title: str = Field("", description="Job title/role")
    employment_type: Optional[str] = Field("Full-time", description="Full-time/Part-time/Internship/Contract/Freelance")
    start_date: str = Field("", description="MM/YYYY or YYYY format")
    end_date: str = Field("", description="MM/YYYY or 'Present'")
    location: Optional[str] = Field(None, description="City, Country")
    duration_months: int = Field(0, description="Total months worked")
    responsibilities: List[str] = Field(default_factory=list, description="Key responsibilities and achievements")
    skills_used: List[str] = Field(default_factory=list, description="Skills applied in this role")
    industry: Optional[str] = Field(None, description="Industry/domain if identifiable")

class Education(BaseModel):
    """Individual education entry"""
    degree_title: str = Field("", description="Full degree title")
    institution_name: str = Field("", description="University/School name")
    start_date: str = Field("", description="MM/YYYY or YYYY")
    end_date: str = Field("", description="MM/YYYY or YYYY")
    location: Optional[str] = Field(None, description="City, Country")
    grade_gpa: Optional[str] = Field(None, description="CGPA/Grade if mentioned")
    relevant_courses: Optional[List[str]] = Field(default_factory=list, description="Relevant courses")
    degree_level: str = Field("Bachelor's", description="High School/Bachelor's/Master's/PhD/Diploma")

class Project(BaseModel):
    """Individual project entry"""
    title: str = Field("", description="Project title")
    description: str = Field("", description="Brief project description")
    technologies_used: List[str] = Field(default_factory=list, description="Technologies used in the project")
    github_link: Optional[str] = Field(None, description="GitHub URL if available")
    live_demo: Optional[str] = Field(None, description="Demo URL if available")
    duration: Optional[str] = Field(None, description="Project duration if mentioned")

class Certification(BaseModel):
    """Individual certification entry"""
    name: str = Field("", description="Certification name")
    issuing_organization: str = Field("", description="Issuing body/organization")
    issue_date: str = Field("", description="MM/YYYY format")
    expiry_date: Optional[str] = Field(None, description="MM/YYYY or 'No expiry'")
    credential_url: Optional[str] = Field(None, description="Verification URL if available")
    credential_id: Optional[str] = Field(None, description="Certificate ID if available")

class ExtracurricularActivity(BaseModel):
    """Individual extracurricular activity entry"""
    title: str = Field("", description="Activity title or role")
    organization: str = Field("", description="Organization, club, or community name")
    activity_type: str = Field("", description="Type: Volunteer Work, Club/Society, Community Service, Sports, Leadership, etc.")
    start_date: str = Field("", description="MM/YYYY or YYYY format")
    end_date: str = Field("", description="MM/YYYY or 'Present'")
    location: Optional[str] = Field(None, description="City, Country")
    description: str = Field("", description="Brief description of activities and achievements")
    skills_gained: List[str] = Field(default_factory=list, description="Skills developed through this activity")
    achievements: List[str] = Field(default_factory=list, description="Notable achievements or recognition")

class AdditionalInfo(BaseModel):
    """Additional information about the candidate"""
    availability: Optional[str] = Field(None, description="Notice period/availability")
    willing_to_relocate: Optional[str] = Field(None, description="Yes/No/Unknown")
    salary_expectations: Optional[str] = Field(None, description="If mentioned")
    preferred_work_mode: Optional[str] = Field(None, description="Remote/Hybrid/On-site/Unknown")

class ResumeData(BaseModel):
    """Complete resume data structure for job matching and database storage"""
    basic_info: BasicInfo = Field(default_factory=BasicInfo, description="Basic contact and personal information")
    professional_summary: ProfessionalSummary = Field(default_factory=ProfessionalSummary, description="Professional summary and career info")
    skills: List[str] = Field(default_factory=list, description="List of skills mentioned in the resume")
    work_experience: List[WorkExperience] = Field(default_factory=list, description="Work experience entries")
    education: List[Education] = Field(default_factory=list, description="Education entries")
    projects: List[Project] = Field(default_factory=list, description="Project entries")
    certifications: List[Certification] = Field(default_factory=list, description="Certification entries")
    extracurricular: List[ExtracurricularActivity] = Field(default_factory=list, description="Extracurricular activities including volunteer work")
    additional_info: AdditionalInfo = Field(default_factory=AdditionalInfo, description="Additional candidate information")

class ParseResponse(BaseModel):
    """Response model for the API"""
    success: bool = Field(..., description="Whether parsing was successful")
    data: Optional[ResumeData] = Field(None, description="Parsed resume data")
    error: Optional[str] = Field(None, description="Error message if parsing failed")
    filename: Optional[str] = Field(None, description="Original filename")

# Initialize FastAPI app
app = FastAPI(
    title="Resume Parser API",
    description="AI-powered resume parsing service using Google Gemini",
    version="1.0.0"
)

# Add CORS middleware to allow requests from Django frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],  # Django server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the AI model
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.1,
)

structured_model = model.with_structured_output(ResumeData)

def process_resume_file(file_path: str) -> ResumeData:
    """
    Process a single resume file through the two-stage parsing pipeline
    
    Args:
        file_path: Path to the resume file
        
    Returns:
        ResumeData: Parsed and refined resume data
        
    Raises:
        Exception: If parsing fails at any stage
    """
    try:
        # Load the PDF file
        loader = PDFPlumberLoader(file_path)
        docs = loader.load()
        
        if not docs:
            raise Exception("Could not extract text from PDF file")
        
        resume_text = "\n\n".join([doc.page_content for doc in docs])
        
        
        if not resume_text.strip():
            raise Exception("PDF file appears to be empty or contains no readable text")
        
        # Stage 1: Initial parsing
        initial_parse_prompt = f"Parse the attached resume and return JSON: {resume_text}"
        
        initial_parse = structured_model.invoke(initial_parse_prompt)
        initial_parse_json = json.dumps(initial_parse.model_dump(), indent=2)
        
        
        # Print some work experience details if available
        if initial_parse.work_experience:
            for i, exp in enumerate(initial_parse.work_experience):
                print(f"  - Work exp {i+1}: {exp.job_title} at {exp.company_name}")
        
        # Print some education details if available
        if initial_parse.education:
            for i, edu in enumerate(initial_parse.education):
                print(f"  - Education {i+1}: {edu.degree_title} from {edu.institution_name}")
        
        # Stage 2: Refinement and quality control
        final_parse_prompt = f"""
You are a professional resume data quality controller. Your task is to review and correct the initially parsed resume data, fixing any parsing errors, inconsistencies, or misclassifications while maintaining strict data fidelity.

Initially Parsed Data:
{initial_parse_json}

DATA CORRECTION OBJECTIVES:
- Fix any obvious parsing errors or misclassifications
- Correct data that was placed in wrong sections
- Standardize formats and naming conventions
- Calculate missing durations and experience totals
- Ensure data consistency across all sections
- Use ONLY the information present in the initially parsed data

CRITICAL CORRECTION RULES:

📋 SECTION CLASSIFICATION FIXES:
- Move volunteer work, community service, club activities from work_experience to extracurricular section
- Move certifications/courses from work_experience to certifications
- Ensure only actual paid employment appears in work_experience
- Verify education entries are in correct format
- Classify extracurricular activities by type: Volunteer Work, Club/Society, Community Service, Sports, Leadership, etc.

📅 DATE & DURATION CORRECTIONS:
- Standardize all dates to MM/YYYY format (e.g., "Nov 2023" → "11/2023")
- Calculate accurate duration_months for each work experience
- Calculate total years_of_experience based on actual work history
- Handle "Present", "Current", "Ongoing" dates appropriately

🔧 SKILL STANDARDIZATION:
- Normalize technical skills (e.g., "ML" → "Machine Learning", "JS" → "JavaScript")
- Remove duplicate skills across all sections
- Standardize skill names to industry conventions
- Keep skills as mentioned, don't infer new ones

👔 CAREER LEVEL ASSESSMENT:
- Determine career_level based on actual work experience:
  * "Entry-level": 0-2 years or student/recent graduate
  * "Mid-level": 3-7 years professional experience
  * "Senior-level": 8+ years with leadership/senior roles
  * "Executive": C-level, VP, Director positions

📊 DATA TYPE CORRECTIONS:
- Ensure years_of_experience is an INTEGER
- Ensure duration_months values are INTEGERS
- Convert string numbers to actual numbers where appropriate
- Maintain proper array structures for lists

🏢 WORK EXPERIENCE REFINEMENT:
- Verify company names are correctly extracted
- Ensure job titles are properly formatted
- Confirm employment_type classification is accurate
- Validate location information
- Enhance responsibility descriptions for clarity

🎓 EDUCATION CORRECTIONS:
- Verify degree titles are complete and accurate
- Ensure institution names are correctly formatted
- Confirm degree_level classifications
- Validate GPA/grade formats

QUALITY ASSURANCE CHECKS:
- Verify all required fields are populated or null
- Check for logical consistency (dates, durations, experience levels)
- Ensure professional summary aligns with actual experience
- Validate that skills match what's mentioned in experience/projects
- Confirm contact information accuracy

STRICT FIDELITY REQUIREMENTS:
- Use ONLY information from the initially parsed data
- Do NOT add skills, experiences, or details not explicitly mentioned
- Do NOT infer information based on job titles or company names
- Do NOT make assumptions about missing information
- If data cannot be corrected with available information, leave as-is

IMPORTANT: 
- Return a corrected and refined version of the resume data
- Maintain the exact same structure as the input
- Focus on accuracy and consistency improvements
- Do not add new information - only correct existing data
- Ensure all corrections are based on evidence in the parsed data
"""
        
        # Get the final refined result
        final_parse = structured_model.invoke(final_parse_prompt)
        
        # Print some work experience details if available
        if final_parse.work_experience:
            for i, exp in enumerate(final_parse.work_experience):
                print(f"  - Final work exp {i+1}: {exp.job_title} at {exp.company_name}")
        
        return final_parse
        
    except Exception as e:
        raise Exception(f"Resume processing failed: {str(e)}")

@app.post("/parse-resumes", response_model=ParseResponse)
async def parse_resume(file: UploadFile = File(...)):
    """
    Parse a single resume file and return structured data
    
    Args:
        file: The uploaded resume file (PDF)
        
    Returns:
        ParseResponse: Contains parsed data or error information
    """
    
    print(f"Received file: {file.filename}, size: {file.size if hasattr(file, 'size') else 'unknown'}")
    
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400, 
            detail="Only PDF files are supported for resume parsing"
        )
    
    # Create a temporary file to store the uploaded content
    temp_file = None
    temp_file_path = None
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await file.read()
            if not content:
                raise Exception("Uploaded file is empty")
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        print(f"Processing file: {temp_file_path}")
        
        # Process the resume
        parsed_data = process_resume_file(temp_file_path)
        
        print(f"Successfully parsed resume: {file.filename}")
        
        return ParseResponse(
            success=True,
            data=parsed_data,
            filename=file.filename
        )
        
    except Exception as e:
        print(f"Error processing {file.filename}: {str(e)}")
        return ParseResponse(
            success=False,
            error=str(e),
            filename=file.filename if file.filename else "unknown"
        )
        
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as cleanup_error:
                print(f"Failed to cleanup temp file: {cleanup_error}")
                pass  # Ignore cleanup errors

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Resume Parser API"}

@app.post("/test-upload")
async def test_upload(file: UploadFile = File(...)):
    """Test file upload endpoint to debug 422 errors"""
    try:
        content = await file.read()
        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(content),
            "status": "success"
        }
    except Exception as e:
        return {
            "error": str(e),
            "status": "failed"
        }

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Resume Parser API",
        "version": "1.0.0",
        "endpoints": {
            "parse": "/parse-resumes",
            "test": "/test-upload",
            "health": "/health",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "resume_parser:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )