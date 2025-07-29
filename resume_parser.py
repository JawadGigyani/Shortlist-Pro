import os
import json
import fitz
import docx
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv

load_dotenv()  # Load .env file

# Initialize FastAPI app
app = FastAPI(title="Resume Parser API", description="AI-powered resume parsing service")

# Define Pydantic models for structured output
class Education(BaseModel):
    degree: str = Field(..., description="Degree obtained")
    major: Optional[str] = Field(None, description="Field of study")
    university_name: str = Field(..., description="Name of educational institution")
    start_year: Optional[str] = Field(None, description="Start year (YYYY)")
    end_year: Optional[str] = Field(None, description="End year (YYYY or 'Present')")

class WorkExperience(BaseModel):
    job_title: str = Field(..., description="Job position title")
    company_name: str = Field(..., description="Name of employer")
    location: Optional[str] = Field(None, description="Location of employment")
    start_date: str = Field(..., description="Start date (MM/YYYY)")
    end_date: Optional[str] = Field(None, description="End date (MM/YYYY or 'Present')")
    description: Optional[str] = Field(None, description="Job responsibilities and achievements")

class ResumeData(BaseModel):
    full_name: str = Field(..., description="Full name of the candidate")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    skills: List[str] = Field(..., description="List of skills and competencies")
    work_experience: List[WorkExperience] = Field(..., description="List of work experiences")
    education: List[Education] = Field(..., description="List of educational qualifications")
    certifications: Optional[List[str]] = Field(None, description="List of certifications")

class ResumeParserAgent:
    """Agent for parsing resume documents into structured data"""
    
    def __init__(self):
        self.model = ChatGroq(
            model_name="llama3-8b-8192",
            temperature=0.1,
            api_key=os.getenv("GROQ_API_KEY")
        )
        self.parser = JsonOutputParser(pydantic_object=ResumeData)
        
        self.prompt = PromptTemplate(
            template="""
            <|begin_of_text|>
            <|start_header_id|>system<|end_header_id|>
            You are an expert resume parser. Extract structured information from the resume text.
            Follow these rules:
            1. Return ONLY valid JSON in the specified format
            2. Use null for missing information
            3. Maintain chronological order (most recent first)
            4. Clean and normalize data
            5. Extract ALL available information
            6. For dates, use MM/YYYY format or 'Present' for current positions
            
            Output Format Instructions:
            {format_instructions}
            
            <|eot_id|>
            <|start_header_id|>user<|end_header_id|>
            RESUME TEXT:
            {resume_text}
            <|eot_id|>
            """,
            input_variables=["resume_text"],
            partial_variables={
                "format_instructions": self.parser.get_format_instructions()
            }
        )
        
        self.chain = self.prompt | self.model | self.parser
    
    def parse_resume(self, resume_text: str) -> Dict[str, Any]:
        """Parse resume text into structured data"""
        try:
            return self.chain.invoke({"resume_text": resume_text})
        except Exception as e:
            print(f"Parsing error: {str(e)}")
            return None

class ResumeProcessingPipeline:
    """End-to-end resume processing pipeline"""
    
    def __init__(self, input_folder: str = "resumes/"):
        self.input_folder = input_folder
        self.output_file = "parsed_resumes.json"
        self.parser_agent = ResumeParserAgent()
    
    def extract_text_from_file(self, file_content: bytes, filename: str) -> Optional[str]:
        """Extract text from uploaded file content"""
        try:
            # Create temporary file
            suffix = os.path.splitext(filename)[1].lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            try:
                if suffix == ".pdf":
                    text = ""
                    with fitz.open(temp_file_path) as doc:
                        for page in doc:
                            text += page.get_text()
                    return text.strip()
                
                elif suffix == ".docx":
                    doc = docx.Document(temp_file_path)
                    return "\n".join([para.text for para in doc.paragraphs]).strip()
                
                print(f"Unsupported format: {filename}")
                return None
            
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
        
        except Exception as e:
            print(f"Text extraction failed for {filename}: {str(e)}")
            return None
    
# Initialize the parser agent
parser_agent = ResumeParserAgent()
processing_pipeline = ResumeProcessingPipeline()

@app.post("/parse-resumes")
async def parse_resumes(files: List[UploadFile] = File(...)):
    """
    FastAPI endpoint to parse uploaded resume files
    """
    try:
        if not os.getenv("GROQ_API_KEY"):
            raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")
        
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        results = []
        
        for file in files:
            # Validate file format
            file_extension = os.path.splitext(file.filename)[1].lower()
            if file_extension not in [".pdf", ".docx"]:
                results.append({
                    "filename": file.filename,
                    "status": "error",
                    "message": f"Unsupported file format: {file_extension}"
                })
                continue
            
            try:
                # Read file content
                file_content = await file.read()
                
                # Extract text
                text = processing_pipeline.extract_text_from_file(file_content, file.filename)
                if not text:
                    results.append({
                        "filename": file.filename,
                        "status": "error",
                        "message": "Failed to extract text from file"
                    })
                    continue
                
                # Parse with agent
                parsed_data = parser_agent.parse_resume(text)
                if not parsed_data:
                    results.append({
                        "filename": file.filename,
                        "status": "error",
                        "message": "Failed to parse resume content"
                    })
                    continue
                
                # Add filename and status
                parsed_data["filename"] = file.filename
                parsed_data["status"] = "success"
                results.append(parsed_data)
                
            except Exception as e:
                results.append({
                    "filename": file.filename,
                    "status": "error",
                    "message": f"Processing error: {str(e)}"
                })
        
        return JSONResponse(content={"results": results})
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Resume Parser API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Detailed health check"""
    groq_configured = bool(os.getenv("GROQ_API_KEY"))
    return {
        "status": "healthy",
        "groq_api_configured": groq_configured,
        "supported_formats": [".pdf", ".docx"]
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Resume Parser API server...")
    print("📄 Supported formats: PDF, DOCX")
    print("🔗 API Documentation: http://127.0.0.1:8001/docs")
    uvicorn.run(app, host="127.0.0.1", port=8001, reload=True)