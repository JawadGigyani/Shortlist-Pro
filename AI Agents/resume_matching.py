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
    title="Resume Matching API",
    description="AI-powered resume matching service for job descriptions",
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

class SkillMatch(BaseModel):
    """Individual skill matching analysis"""
    skill_name: str = Field(..., description="Name of the skill being analyzed")
    requirement_level: str = Field(..., description="Must-have/Nice-to-have/Preferred from JD")
    candidate_has_skill: bool = Field(..., description="Evidence of skill in candidate's background")
    proficiency_level: str = Field(..., description="Basic/Intermediate/Advanced/Expert based on evidence")
    evidence_source: str = Field(..., description="Where skill is demonstrated (work/project/education/certification)")
    match_score: int = Field(..., description="Individual skill match score (0-100)")

class ExperienceAnalysis(BaseModel):
    """Experience relevance analysis"""
    total_years_required: int = Field(..., description="Minimum years required from JD")
    candidate_total_years: int = Field(..., description="Candidate's total professional years")
    relevant_years: int = Field(..., description="Years in relevant domain/industry")
    experience_level_match: str = Field(..., description="Exceeds/Meets/Below/Significantly Below")
    industry_relevance: str = Field(..., description="Highly Relevant/Somewhat Relevant/Not Relevant")
    role_progression: str = Field(..., description="Strong Growth/Moderate Growth/Stable/No Clear Progression")
    experience_score: int = Field(..., description="Overall experience match score (0-100)")

class EducationAnalysis(BaseModel):
    """Education and qualifications analysis"""
    degree_requirement_met: bool = Field(..., description="Meets minimum degree requirement")
    field_relevance_score: str = Field(..., description="Perfectly Aligned/Well Aligned/Somewhat Aligned/Not Aligned")
    education_level: str = Field(..., description="High School/Bachelor's/Master's/PhD")
    certifications_relevant: List[str] = Field(default_factory=list, description="Relevant certifications found")
    alternative_learning: List[str] = Field(default_factory=list, description="Bootcamps, online courses, self-learning")
    education_score: int = Field(..., description="Education match score (0-100)")

class ResumeQualityAssessment(BaseModel):
    """Assessment of resume quality and presentation"""
    clarity_and_structure: str = Field(..., description="Excellent/Good/Average/Poor resume organization")
    technical_articulation: str = Field(..., description="Excellent/Good/Average/Poor at explaining tech concepts")
    achievement_presentation: str = Field(..., description="Excellent/Good/Average/Poor at showcasing results")
    professional_presentation: str = Field(..., description="Excellent/Good/Average/Poor overall professionalism")
    quality_score: int = Field(..., description="Resume quality score (0-100)")

class CandidateGaps(BaseModel):
    """Analysis of gaps between candidate and JD requirements"""
    critical_skill_gaps: List[str] = Field(default_factory=list, description="Must-have skills missing")
    experience_gaps: List[str] = Field(default_factory=list, description="Experience requirements not met")
    education_gaps: List[str] = Field(default_factory=list, description="Educational requirements not met")
    nice_to_have_missing: List[str] = Field(default_factory=list, description="Preferred qualifications missing")

class ScoringReasons(BaseModel):
    """Detailed reasoning for the score"""
    top_strengths: List[str] = Field(..., description="Top 5 reasons candidate scores well")
    main_weaknesses: List[str] = Field(..., description="Main areas where candidate falls short")
    standout_qualities: List[str] = Field(..., description="Unique strengths or exceptional qualities")
    risk_factors: List[str] = Field(..., description="Potential concerns or red flags")

class CandidateScoreResult(BaseModel):
    """Complete candidate scoring analysis for JD matching"""
    overall_match_score: int = Field(..., description="Overall match percentage (0-100)")
    ranking_tier: str = Field(..., description="Excellent Fit/Strong Fit/Good Fit/Moderate Fit/Weak Fit")
    
    # Detailed scoring breakdown
    skills_match_score: int = Field(..., description="Skills alignment score (0-100)")
    experience_match_score: int = Field(..., description="Experience relevance score (0-100)")
    education_match_score: int = Field(..., description="Education alignment score (0-100)")
    resume_quality_score: int = Field(..., description="Resume presentation quality (0-100)")
    
    # Detailed analysis
    skill_analysis: List[SkillMatch] = Field(..., description="Individual skill matching breakdown")
    experience_analysis: ExperienceAnalysis = Field(..., description="Experience relevance assessment")
    education_analysis: EducationAnalysis = Field(..., description="Education and qualifications review")
    resume_quality: ResumeQualityAssessment = Field(..., description="Resume quality assessment")
    gap_analysis: CandidateGaps = Field(..., description="Missing requirements analysis")
    scoring_reasoning: ScoringReasons = Field(..., description="Detailed reasoning for score")
    
    # Selection guidance
    interview_recommendation: str = Field(..., description="Highly Recommend/Recommend/Consider/Not Recommended")
    confidence_level: str = Field(..., description="High/Medium/Low confidence in assessment")
    interview_priority: str = Field(..., description="High Priority/Medium Priority/Low Priority/Not Suitable")
    key_interview_topics: List[str] = Field(..., description="Topics to explore if selected for interview")


# Request and Response Models for FastAPI
class MatchingRequest(BaseModel):
    """Request model for resume matching endpoint"""
    job_description: str = Field(..., description="Job description text")
    candidate_resume_json: str = Field(..., description="Parsed resume data in JSON format")

class MatchingResponse(BaseModel):
    """Response model for resume matching endpoint"""
    success: bool = Field(..., description="Whether the matching was successful")
    data: Optional[CandidateScoreResult] = Field(None, description="Matching analysis results")
    error: Optional[str] = Field(None, description="Error message if matching failed")


# Initialize the AI model
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",  # Using Gemini 1.5 Flash for fast analysis
    temperature=0.1,  # Low temperature for consistent, analytical responses
)

structured_matcher = model.with_structured_output(CandidateScoreResult)


def create_matching_prompt(job_description: str, candidate_resume_json: str) -> str:
    """Create the matching prompt with the provided job description and resume data"""
    return f"""
You are an expert talent assessment specialist. Your task is to analyze and score a candidate's resume against a job description to help recruiters rank and prioritize candidates for potential initial interviews.

JOB DESCRIPTION:
{job_description}

CANDIDATE RESUME (Parsed JSON):
{candidate_resume_json}

🎯 CANDIDATE SCORING METHODOLOGY:
Calculate overall_match_score (0-100%) using weighted scoring approach:

ADAPTIVE WEIGHTING BASED ON ROLE LEVEL:
FOR ENTRY-LEVEL ROLES (0-2 years required):
* Skills Alignment: 35% weight
* Education & Certifications: 30% weight  
* Projects & Learning Evidence: 25% weight
* Resume Quality & Communication: 10% weight

FOR MID-LEVEL ROLES (3-7 years required):
* Skills Alignment: 40% weight
* Experience Relevance: 35% weight
* Education & Certifications: 15% weight
* Resume Quality & Communication: 10% weight

FOR SENIOR ROLES (8+ years required):
* Experience Relevance: 45% weight
* Skills Alignment: 35% weight
* Leadership & Results Evidence: 15% weight
* Resume Quality & Communication: 5% weight

📊 DETAILED SCORING CRITERIA:

SKILLS ALIGNMENT SCORING (Primary Component):
- Identify ALL required technical and soft skills from JD
- Categorize as Must-Have/Nice-to-Have/Preferred
- Score each skill individually:
  * Perfect Match with Strong Evidence: 90-100 points
  * Good Match with Clear Evidence: 70-89 points
  * Basic Match or Transferable Skill: 50-69 points
  * Weak Evidence or Related Skill: 30-49 points
  * No Evidence Found: 0-29 points
- Weight Must-Have skills more heavily than Nice-to-Have
- Consider skill combinations and complementary abilities

EXPERIENCE RELEVANCE SCORING:
- Years of experience vs requirement (flexible for strong candidates)
- Industry and domain relevance assessment
- Role responsibility alignment and progression
- Leadership experience for senior positions
- Quality of achievements and measurable results
- Career trajectory and growth evidence

EDUCATION & CERTIFICATION SCORING:
- Degree level and field relevance to role requirements
- Institution quality and academic performance (if available)
- Professional certifications and their relevance
- Continuous learning evidence (courses, bootcamps, self-study)
- Alternative qualifications for non-traditional backgrounds

RESUME QUALITY ASSESSMENT:
- Clarity of professional summary and role descriptions
- Technical concept explanation ability
- Achievement articulation and quantified results
- Professional presentation and attention to detail
- Communication skills evidenced through writing quality

🎯 SCORING TIERS AND RECOMMENDATIONS:

EXCELLENT FIT (85-100%):
- Exceeds most requirements with strong evidence
- Multiple standout qualifications or achievements
- High recommendation for immediate interview consideration
- Likely to be competitive candidate

STRONG FIT (70-84%):
- Meets core requirements with good supporting evidence
- Some standout qualities with minor gaps in nice-to-have areas
- Strong recommendation for interview scheduling
- Good potential for role success

GOOD FIT (55-69%):
- Meets minimum requirements with adequate evidence
- Solid foundation but gaps in some preferred areas
- Recommend for interview if candidate pool allows
- May need additional evaluation or development

MODERATE FIT (40-54%):
- Borderline on key requirements
- Some relevant experience but notable gaps
- Consider only if limited candidate pool
- Would require significant training/development

WEAK FIT (0-39%):
- Missing multiple core requirements
- Limited relevant experience or skills
- Not recommended for this specific role
- Better suited for different position types

🔍 COMPREHENSIVE ANALYSIS REQUIREMENTS:

SKILL-BY-SKILL BREAKDOWN:
- Analyze each technical skill mentioned in JD individually
- Assess proficiency level based on usage context in resume
- Identify transferable skills from related domains
- Note any advanced skills beyond requirements

GAP IDENTIFICATION:
- List critical missing skills that could impact role performance
- Identify experience gaps and their potential impact
- Note educational or certification gaps if relevant
- Distinguish between learnable gaps vs fundamental mismatches

STANDOUT ANALYSIS:
- Highlight unique qualifications or exceptional achievements
- Identify competitive advantages this candidate offers
- Note any special expertise or rare skill combinations
- Assess potential for growth and adaptation

RISK ASSESSMENT:
- Flag potential concerns (overqualification, employment gaps, etc.)
- Assess resume quality issues that might indicate communication problems
- Note any red flags that could impact hiring decision
- Evaluate cultural fit indicators where evident

📋 INTERVIEW GUIDANCE (If Selected):
Based on scoring analysis, provide guidance for potential interviews:

HIGH-PRIORITY EXPLORATION AREAS:
- Technical skills requiring validation
- Experience claims needing verification
- Achievement details requiring elaboration
- Cultural fit and motivation assessment

RECOMMENDED INTERVIEW APPROACH:
- Technical assessment level (basic/intermediate/advanced)
- Behavioral interview focus areas
- Portfolio or work sample review needs
- Reference check priorities

⚡ CRITICAL SCORING PRINCIPLES:
- Be OBJECTIVE and evidence-based in all assessments
- Consider CONTEXT of candidate's career level and trajectory
- Value PRACTICAL APPLICATION over just skill listings
- Account for TRANSFERABLE SKILLS and learning potential
- Assess COMMUNICATION ability through resume quality
- Be FAIR to non-traditional backgrounds and career changers
- Focus on JOB-RELEVANT qualifications rather than perfect matches
- Provide ACTIONABLE insights for recruiting decisions

🎯 FINAL ASSESSMENT OUTPUT:
- Clear numerical score for easy ranking and comparison
- Tier classification for quick filtering (Excellent/Strong/Good/Moderate/Weak)
- Interview recommendation with confidence level
- Priority ranking for interview scheduling
- Key topics to explore if candidate advances

IMPORTANT: This scoring is for candidate ranking and prioritization, not final hiring decisions. Focus on identifying the strongest candidates for interview consideration while providing detailed reasoning to support recruiting team decisions. Be thorough but concise in analysis to enable efficient candidate comparison and selection.
"""


@app.post("/match-resume", response_model=MatchingResponse)
async def match_resume(request: MatchingRequest):
    """
    Match a candidate's resume against a job description using AI analysis
    
    Args:
        request: MatchingRequest containing job_description and candidate_resume_json
        
    Returns:
        MatchingResponse with analysis results or error message
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
    return {"status": "healthy", "service": "resume-matching-api"}


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Resume Matching API",
        "version": "1.0.0",
        "endpoints": {
            "/match-resume": "POST - Match resume against job description",
            "/health": "GET - Health check",
            "/docs": "GET - API documentation"
        }
    }


if __name__ == "__main__":
    # Run the server
    port = int(os.getenv("PORT", 8001))  # Default to port 8001
    uvicorn.run(
        "resume_matching:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Enable auto-reload for development
        log_level="info"
    )