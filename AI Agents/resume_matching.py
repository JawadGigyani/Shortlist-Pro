# Import required libraries
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv
import uvicorn
import os

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Resume Screening API",
    description="Simplified AI-powered resume screening for initial interview selection",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Django app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimpleMatchResult(BaseModel):
    """Simplified candidate screening result for initial interview prioritization"""
    # Core essentials only
    overall_score: int = Field(..., description="Overall match score (0-100)")
    recommendation: str = Field(..., description="Interview/Maybe/Skip")
    confidence: str = Field(..., description="High/Medium/Low")
    
    # Key insights for conversation
    strengths: List[str] = Field(..., description="Top 3 candidate strengths")
    concerns: List[str] = Field(..., description="Top 2 areas to explore")
    conversation_topics: List[str] = Field(..., description="5 questions to ask in initial interview")
    
    # Quick breakdown for scoring components
    skills_match: str = Field(..., description="Strong/Adequate/Weak")
    experience_match: str = Field(..., description="Strong/Adequate/Weak")
    education_fit: str = Field(..., description="Meets/Doesn't Meet requirements")
    
    # For database storage compatibility
    skills_score: int = Field(..., description="Skills alignment score (0-100)")
    experience_score: int = Field(..., description="Experience relevance score (0-100)")
    education_score: int = Field(..., description="Education alignment score (0-100)")
    
    # Simplified insights
    matched_skills: List[str] = Field(..., description="Key skills candidate has (max 10 skills)")
    missing_skills: List[str] = Field(..., description="Important skills candidate lacks (max 5 skills)")
    experience_summary: str = Field(..., description="One SHORT sentence experience assessment (max 200 chars)")
    
    # Interview guidance
    interview_priority: str = Field(..., description="High/Medium/Low/Skip")
    key_questions: List[str] = Field(..., description="Specific questions to ask this candidate")


# Request and Response Models for FastAPI
class MatchingRequest(BaseModel):
    """Request model for resume matching endpoint"""
    job_description: str = Field(..., description="Job description text")
    candidate_resume_json: str = Field(..., description="Parsed resume data in JSON format")

class MatchingResponse(BaseModel):
    """Response model for resume matching endpoint"""
    success: bool = Field(..., description="Whether the matching was successful")
    data: Optional[SimpleMatchResult] = Field(None, description="Matching analysis results")
    error: Optional[str] = Field(None, description="Error message if matching failed")


# Initialize the AI model
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",  # Using Gemini 1.5 Flash for fast analysis
    temperature=0,  # Low temperature for consistent, analytical responses
)

structured_matcher = model.with_structured_output(SimpleMatchResult)


def create_matching_prompt(job_description: str, candidate_resume_json: str) -> str:
    """Create a simplified matching prompt focused on initial interview screening"""
    return f"""
You are an expert HR screening specialist. Your task is to quickly assess if a candidate should be invited for an initial interview (informal conversation, not technical).

JOB DESCRIPTION:
{job_description}

CANDIDATE RESUME (Parsed JSON):
{candidate_resume_json}

🎯 SIMPLIFIED SCREENING METHODOLOGY:

Your goal is to answer: "Should we have a 15-20 minute conversation with this person?"

CORE ASSESSMENT CRITERIA:

1. BASIC QUALIFICATION CHECK (40% weight):
   - Do they meet minimum requirements (education, years of experience)?
   - Do they have core skills mentioned in the JD?
   - Is their background generally relevant?

2. SKILLS ALIGNMENT (35% weight):
   - Strong: Has most required skills with evidence
   - Adequate: Has some required skills, could learn others
   - Weak: Missing most critical skills

3. EXPERIENCE RELEVANCE (25% weight):
   - Strong: Relevant industry/role experience
   - Adequate: Some transferable experience
   - Weak: Little relevant experience

🎯 SIMPLE DECISION FRAMEWORK:

INTERVIEW RECOMMENDATION:
- "Interview": Meets basic requirements, worth talking to (Score: 60-100)
- "Maybe": Borderline candidate, consider if time allows (Score: 40-59)
- "Skip": Doesn't meet basic requirements (Score: 0-39)

CONFIDENCE LEVELS:
- High: Clear evidence supporting decision
- Medium: Some uncertainty but leaning one way
- Low: Difficult to assess from resume alone

📋 CONVERSATION PREPARATION:

STRENGTHS (Top 3):
- What are their best selling points?
- What makes them potentially interesting?

CONCERNS (Top 2):
- What questions/doubts need addressing?
- What might be potential issues?

CONVERSATION TOPICS (5 questions):
- Specific questions to ask in initial interview
- Focus on clarifying resume claims
- Understanding motivation and interest
- Assessing communication skills

🔍 SCORING GUIDELINES:

INTERVIEW (60-100):
- Meets most basic requirements
- Has relevant skills or experience
- Resume shows progression/growth
- Worth a conversation

MAYBE (40-59):
- Meets some requirements but has gaps
- Transferable skills but not perfect match
- Could be worth talking to if candidate pool is limited

SKIP (0-39):
- Missing critical requirements
- No relevant experience or skills
- Not a good fit for this role

⚡ KEY PRINCIPLES:
- This is PRE-SCREENING, not final assessment
- Focus on "worth talking to" not "perfect candidate"
- Consider potential and transferable skills
- Look for communication quality in resume
- Be practical about requirements vs nice-to-haves

🎯 OUTPUT REQUIREMENTS:
- Clear Interview/Maybe/Skip recommendation
- Practical conversation topics for initial screening
- Quick assessment of key areas (skills, experience, education)
- Specific questions tailored to this candidate
- KEEP ALL TEXT RESPONSES CONCISE (max 200 characters each)
- Experience summary: ONE SHORT SENTENCE only

FORMAT CONSTRAINTS:
- Strengths: 3 bullet points, max 50 chars each
- Concerns: 2 bullet points, max 50 chars each  
- Questions: 5 short questions, max 100 chars each
- Experience summary: 1 sentence, max 200 chars

REMEMBER: This screening is to identify candidates worth a brief conversation, not to make final hiring decisions. Focus on efficiency and practical insights for busy recruiters.
"""


@app.post("/match-resume", response_model=MatchingResponse)
async def match_resume(request: MatchingRequest):
    """
    Screen a candidate's resume for initial interview consideration
    
    Args:
        request: MatchingRequest containing job_description and candidate_resume_json
        
    Returns:
        MatchingResponse with simplified screening results or error message
    """
    try:
        # Validate inputs
        if not request.job_description.strip():
            raise HTTPException(status_code=400, detail="Job description cannot be empty")
        
        if not request.candidate_resume_json.strip():
            raise HTTPException(status_code=400, detail="Candidate resume JSON cannot be empty")
        
        # Create the full prompt
        full_prompt = create_matching_prompt(request.job_description, request.candidate_resume_json)
        
        # Process the matching request
        response = structured_matcher.invoke(full_prompt)
        
        # Return successful response
        return MatchingResponse(
            success=True,
            data=response,
            error=None
        )
        
    except Exception as e:
        # Handle any errors that occur during processing
        error_message = f"Error processing resume matching: {str(e)}"
        return MatchingResponse(
            success=False,
            data=None,
            error=error_message
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "resume-screening-api"}


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Resume Screening API",
        "version": "2.0.0",
        "description": "Simplified AI screening for initial interview selection",
        "endpoints": {
            "/match-resume": "POST - Screen resume for initial interview consideration",
            "/health": "GET - Health check",
            "/docs": "GET - API documentation"
        }
    }


if __name__ == "__main__":
    # Run the server
    port = int(os.getenv("PORT", 8002))  # Default to port 8002
    uvicorn.run(
        "resume_matching:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Enable auto-reload for development
        log_level="info"
    )