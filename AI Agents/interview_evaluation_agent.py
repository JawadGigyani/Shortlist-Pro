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
    title="Interview Evaluation API",
    description="AI-powered interview transcript evaluation for hiring decisions",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Django app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InterviewEvaluationResult(BaseModel):
    """Simplified interview evaluation result for pre-screening interviews"""
    
    # Simplified 3-criteria scoring (0-10 scale)
    communication_clarity: float = Field(..., description="Communication clarity and professional articulation (0-10)")
    relevant_experience: float = Field(..., description="Experience relevance and depth matching resume claims (0-10)")
    role_interest_fit: float = Field(..., description="Understanding of role and genuine interest (0-10)")
    
    # Overall calculated score
    overall_score: float = Field(..., description="Overall candidate assessment score (0-10, calculated from above 3 criteria)")
    
    # Simplified hiring recommendation for pre-screening
    recommendation: str = Field(..., description="PROCEED/CONDITIONAL/REJECT/INSUFFICIENT")
    confidence_level: str = Field(..., description="High/Medium/Low confidence in evaluation")
    
    # Focused qualitative assessments
    key_strengths: List[str] = Field(..., description="Top 3 candidate strengths identified")
    areas_of_concern: List[str] = Field(..., description="Top 2 areas of concern for this role")
    overall_impression: str = Field(..., description="Brief overall impression and rationale (max 200 chars)")
    
    # Pre-screening specific analysis
    resume_alignment: str = Field(..., description="How well interview answers align with resume claims (max 150 chars)")
    communication_quality: str = Field(..., description="Quality of communication and articulation (max 150 chars)")
    role_understanding: str = Field(..., description="Candidate's understanding of the role and company (max 150 chars)")
    
    # Next steps for qualified candidates
    recommended_next_steps: str = Field(..., description="Specific recommendations if candidate proceeds (max 200 chars)")
    questions_to_explore: List[str] = Field(..., description="Key questions for next interview round (max 3)")
    
    # Quick interview highlights
    best_responses: List[str] = Field(..., description="Best interview responses/moments (max 2)")
    concerns_for_next_round: List[str] = Field(..., description="Specific concerns to address (max 2)")


# Request and Response Models for FastAPI
class EvaluationRequest(BaseModel):
    """Request model for interview evaluation endpoint"""
    job_description: str = Field(..., description="Job description for the position")
    candidate_resume_data: str = Field(..., description="Candidate resume information")
    interview_transcript: str = Field(..., description="Complete interview transcript with speaker labels")
    interview_duration_minutes: Optional[int] = Field(None, description="Interview duration in minutes")
    
    # Resume matching context (from initial screening)
    resume_overall_score: Optional[float] = Field(None, description="Overall resume match score (0-100)")
    resume_skills_score: Optional[float] = Field(None, description="Skills match score (0-100)")
    resume_experience_score: Optional[float] = Field(None, description="Experience match score (0-100)")
    resume_education_score: Optional[float] = Field(None, description="Education match score (0-100)")
    matched_skills: Optional[List[str]] = Field(None, description="Skills that matched from resume")
    missing_skills: Optional[List[str]] = Field(None, description="Critical skills missing from resume")
    experience_gap: Optional[str] = Field(None, description="Description of experience gaps")

class EvaluationResponse(BaseModel):
    """Response model for interview evaluation endpoint"""
    success: bool = Field(..., description="Whether the evaluation was successful")
    data: Optional[InterviewEvaluationResult] = Field(None, description="Evaluation results")
    error: Optional[str] = Field(None, description="Error message if evaluation failed")


# Initialize the AI model
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",  # Using latest Gemini model for complex analysis
    temperature=0.1,  # Low temperature for consistent, analytical responses
)

structured_evaluator = model.with_structured_output(InterviewEvaluationResult)


def create_evaluation_prompt(job_description: str, candidate_resume_data: str, interview_transcript: str, 
                           duration_minutes: Optional[int] = None, resume_context: Optional[Dict[str, Any]] = None) -> str:
    """Create a comprehensive evaluation prompt for interview transcript analysis"""
    duration_info = f"(Duration: {duration_minutes} minutes)" if duration_minutes else ""
    
    # Extract resume matching context
    resume_info = ""
    if resume_context:
        resume_info = f"""

🔍 INITIAL RESUME SCREENING RESULTS:
Overall Resume Match: {resume_context.get('resume_overall_score', 'N/A')}%
- Skills Match: {resume_context.get('resume_skills_score', 'N/A')}%
- Experience Match: {resume_context.get('resume_experience_score', 'N/A')}%
- Education Match: {resume_context.get('resume_education_score', 'N/A')}%

✅ MATCHED SKILLS: {', '.join(resume_context.get('matched_skills', [])) if resume_context.get('matched_skills') else 'None listed'}
❌ MISSING CRITICAL SKILLS: {', '.join(resume_context.get('missing_skills', [])) if resume_context.get('missing_skills') else 'None identified'}
⚠️ EXPERIENCE GAPS: {resume_context.get('experience_gap', 'N/A')}

⚖️ IMPORTANT: Use this resume analysis to inform your interview evaluation. A candidate with low resume scores should not receive high interview scores unless they demonstrate exceptional additional qualifications during the interview."""
    
    return f"""
You are a senior HR specialist conducting comprehensive candidate evaluations. You must consider BOTH the initial resume screening results AND the interview performance to make informed hiring decisions.

🎯 CONTEXT:
JOB DESCRIPTION: {job_description}

CANDIDATE RESUME: {candidate_resume_data}
{resume_info}

INTERVIEW TRANSCRIPT {duration_info}: {interview_transcript}

📊 SIMPLIFIED PRE-SCREENING EVALUATION (0-10 scale):

Focus on these 3 KEY CRITERIA for initial screening:

1. COMMUNICATION CLARITY (0-10):
   - Can the candidate express themselves clearly and professionally?
   - Do they articulate thoughts in a structured, understandable way?
   - Are they confident in their communication?
   
   8-10: Excellent communicator, clear and professional
   6-7: Good communication, minor areas for improvement  
   4-5: Adequate communication, some unclear moments
   2-3: Below average communication, noticeable issues
   0-1: Poor communication, significant barriers

2. RELEVANT EXPERIENCE (0-10):
   ⚠️ CRITICAL: This score must reflect BOTH resume analysis AND interview performance
   
   🚨 STRICT SCORING METHODOLOGY (HARD CAPS):
   - If Resume Experience < 30%: Interview MAX 3/10 (severe experience gap)
   - If Resume Experience 30-40%: Interview MAX 4/10 (significant experience gap)
   - If Resume Experience 40-60%: Interview MAX 6/10 (moderate experience, room for growth)
   - If Resume Experience 60-80%: Interview MAX 8/10 (good experience base)
   - If Resume Experience > 80%: Interview confirms full 8-10/10 potential
   
   ⚖️ EVALUATION CRITERIA:
   - Does their interview performance validate resume claims?
   - Can they provide concrete examples from their limited experience?
   - Do they acknowledge skill gaps honestly and show learning potential?
   - Are they realistic about their current capabilities vs role requirements?
   
   IMPORTANT: A candidate with 30% resume experience CANNOT score 6+ regardless of how well they articulate their limited experience.
   
   8-10: Strong relevant experience + excellent interview examples
   6-7: Adequate experience + good interview demonstration  
   4-5: Limited experience but honest about gaps + shows potential
   2-3: Weak experience + poor interview examples
   0-1: Insufficient experience + cannot articulate relevant examples

3. ROLE INTEREST & FIT (0-10):
   - Do they understand what this position involves?
   - Have they researched the company/role appropriately?
   - Do they show genuine interest and engagement?
   
   8-10: Excellent role understanding, high engagement
   6-7: Good role awareness, shows genuine interest
   4-5: Basic understanding, moderate interest
   2-3: Limited role awareness, low engagement
   0-1: Poor role understanding, disengaged

📋 STRICT RECOMMENDATION FRAMEWORK:

PROCEED (Overall ≥7.0 AND Resume Score ≥60%):
- Strong candidate ready for next interview round
- Both resume and interview performance meet high standards
- Recommend proceeding with confidence

CONDITIONAL (Overall 5.0-6.9 AND Resume Score 40-60%):
- Mixed signals requiring careful consideration  
- Either resume adequate but interview concerns, or vice versa
- May proceed with specific skill development plan and mentoring

REJECT (Overall <5.0 OR Resume Score <40% OR Experience Score <30%):
- Does not meet minimum hiring standards
- Significant gaps that cannot be bridged through basic training
- Resume and/or interview performance insufficient
- Not recommended for next round

INSUFFICIENT (Special cases):
- Interview too brief or technical issues prevented proper assessment
- Data quality issues prevent fair evaluation
- Requires interview retry or additional screening

📝 ASSESSMENT REQUIREMENTS:

STRENGTHS (Max 3):
- Specific positive observations from interview
- Evidence-based examples
- Key selling points for next round

CONCERNS (Max 3):
- Specific issues or gaps identified
- Areas that may cause problems
- Red flags or hesitations

KEY INSIGHTS (Max 2):
- Important observations about candidate
- Notable patterns or characteristics
- Unique aspects worth mentioning

NEXT STEPS GUIDANCE:
- Brief recommendation for next steps
- Specific areas to explore further
- Any special considerations needed

🎯 EVALUATION INSTRUCTIONS:

1. Score each of the 3 criteria (0-10 scale)
2. ENFORCE HARD CAPS: Experience score MUST NOT exceed the resume-based maximum
3. Calculate overall score as the average of all 3 criteria
4. Apply STRICT recommendation framework - do not be lenient
5. Provide recommendation based on overall score AND resume context
6. Give specific, actionable feedback with evidence from both resume and interview
7. Focus on PRE-SCREENING relevance - this is not a final hiring decision
8. Be concise but thorough in your assessments
9. Highlight alignment between resume claims and interview responses
10. Note any red flags or exceptional strengths

🚨 CRITICAL ENFORCEMENT RULES:
- Resume Experience 30% → Interview Experience MAX 4/10 (NO EXCEPTIONS)
- Resume Experience < 40% + Missing Critical Skills → Strong REJECT recommendation
- Do not be influenced by good communication if experience is insufficient
- A well-spoken candidate with limited experience still receives low experience scores

⚡ ANALYSIS PRINCIPLES:

1. EVIDENCE-BASED: Support assessments with specific transcript examples
2. BALANCED: Consider both strengths and concerns
3. CONTEXTUAL: Consider role requirements and experience level
4. ACTIONABLE: Provide useful guidance for next interview rounds
5. FAIR: Avoid bias based on communication style or background
6. FOCUSED: Remember this is INITIAL SCREENING, not final assessment

Remember: This is an INITIAL SCREENING. Focus on basic qualifications, communication ability, and genuine interest rather than deep technical assessment.
"""


@app.post("/evaluate-interview", response_model=EvaluationResponse)
async def evaluate_interview(request: EvaluationRequest):
    """
    Comprehensively evaluate an interview transcript for hiring decisions
    
    Args:
        request: EvaluationRequest containing job description, candidate data, and interview transcript
        
    Returns:
        EvaluationResponse with detailed evaluation results or error message
    """
    try:
        # Validate inputs
        if not request.job_description.strip():
            raise HTTPException(status_code=400, detail="Job description cannot be empty")
        
        if not request.candidate_resume_data.strip():
            raise HTTPException(status_code=400, detail="Candidate resume data cannot be empty")
        
        if not request.interview_transcript.strip():
            raise HTTPException(status_code=400, detail="Interview transcript cannot be empty")
        
        # Create the full evaluation prompt
        # Prepare resume context if available
        resume_context = None
        if any([request.resume_overall_score, request.resume_skills_score, request.resume_experience_score]):
            resume_context = {
                'resume_overall_score': request.resume_overall_score,
                'resume_skills_score': request.resume_skills_score,
                'resume_experience_score': request.resume_experience_score,
                'resume_education_score': request.resume_education_score,
                'matched_skills': request.matched_skills or [],
                'missing_skills': request.missing_skills or [],
                'experience_gap': request.experience_gap or 'N/A'
            }
        
        # Create evaluation prompt with resume context
        full_prompt = create_evaluation_prompt(
            request.job_description, 
            request.candidate_resume_data,
            request.interview_transcript,
            request.interview_duration_minutes,
            resume_context
        )
        
        # Process the evaluation request
        response = structured_evaluator.invoke(full_prompt)
        
        # Return successful response
        return EvaluationResponse(
            success=True,
            data=response,
            error=None
        )
        
    except Exception as e:
        # Handle any errors that occur during processing
        error_message = f"Error processing interview evaluation: {str(e)}"
        return EvaluationResponse(
            success=False,
            data=None,
            error=error_message
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "interview-evaluation-api"}


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Interview Evaluation API",
        "version": "1.0.0",
        "description": "AI-powered interview transcript evaluation for hiring decisions",
        "endpoints": {
            "/evaluate-interview": "POST - Comprehensive interview transcript evaluation",
            "/health": "GET - Health check",
            "/docs": "GET - API documentation"
        }
    }


if __name__ == "__main__":
    # Run the server
    port = int(os.getenv("PORT", 8002))  # Default to port 8002
    uvicorn.run(
        "interview_evaluation_agent:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Enable auto-reload for development
        log_level="info"
    )