# Import required libraries
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv
import os
import json

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Interview Questions Agent", description="Generate tailored interview questions for candidates")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],  # Django server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Google Gemini AI
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.7  # Slightly higher for more creative question generation
)

# Pydantic Models - SIMPLIFIED
class QuestionItem(BaseModel):
    question: str = Field(description="Short, direct interview question (max 25 words)")
    category: str = Field(description="Question category: background_verification, skill_validation, motivation_fit")
    purpose: str = Field(description="Brief reason for asking (max 50 words)")
    priority: str = Field(description="Question priority: high, medium")
    expected_duration: str = Field(description="Expected time: 1-2 min")

class InterviewQuestionsRequest(BaseModel):
    resume_data: str = Field(description="Complete resume text or structured data")
    job_description: str = Field(description="Job description text")
    matching_results: Dict[str, Any] = Field(description="Results from resume matching agent")

class InterviewQuestionsResult(BaseModel):
    questions: List[QuestionItem] = Field(description="3-4 quick screening questions")
    total_questions: int = Field(description="Total questions (3-4 max)")
    estimated_duration: str = Field(description="Quick screening duration: 5-10 minutes")
    complexity_level: str = Field(description="Interview complexity: junior, mid, senior")
    focus_areas: List[str] = Field(description="Key screening focus areas")
    question_distribution: Dict[str, int] = Field(description="Questions per category")

def determine_complexity_and_question_count(resume_data: str, job_description: str, matching_score: float) -> tuple:
    """Determine interview complexity and dynamic question count - SIMPLIFIED"""
    
    # Analyze role level from job description
    jd_lower = job_description.lower()
    role_level = "junior"
    
    if any(word in jd_lower for word in ["senior", "lead", "principal", "architect", "manager"]):
        role_level = "senior"
    elif any(word in jd_lower for word in ["mid", "intermediate", "ii", "2"]):
        role_level = "mid"
    
    # SIMPLIFIED: Always 3-4 questions for efficient screening
    if role_level == "senior":
        complexity = "senior"
        base_questions = 4  # Reduced from 8
    elif role_level == "mid":
        complexity = "mid"  
        base_questions = 4  # Reduced from 6
    else:
        complexity = "junior"
        base_questions = 3  # Reduced from 5
    
    # Adjust based on matching score (minimal adjustment)
    if matching_score >= 80:
        base_questions = min(base_questions + 1, 4)  # Max 4 questions
    elif matching_score < 60:
        base_questions = max(base_questions - 1, 3)  # Min 3 questions
    
    # Ensure within tight limits for quick screening
    total_questions = max(3, min(4, base_questions))
    
    return complexity, total_questions

def create_interview_questions_prompt(resume_data: str, job_description: str, matching_results: Dict, 
                                    complexity_level: str, target_questions: int) -> str:
    """Create SIMPLIFIED prompt for quick screening questions"""
    
    prompt = f"""
You are an expert HR screener. Generate {target_questions} SHORT, focused questions for a 5-10 minute phone screening.

CANDIDATE RESUME (first 800 chars): {resume_data[:800]}

JOB POSITION: {job_description[:500]}

MATCHING ANALYSIS:
- Score: {matching_results.get('overall_score', 'N/A')}%
- Key Skills: {matching_results.get('matched_skills', [])[:5]}
- Missing: {matching_results.get('missing_skills', [])[:3]}

REQUIREMENTS:
Generate EXACTLY {target_questions} questions that are:
1. SHORT and conversational (max 25 words each)
2. Focus on CRITICAL decision points only
3. Quick to answer (1-2 minutes each)
4. Cover: background verification, key skills, motivation

CATEGORIES (balanced distribution):
- background_verification: Verify 1-2 key resume claims
- skill_validation: Test 1-2 most important skills  
- motivation_fit: Assess interest and fit

JSON FORMAT:
{{
    "questions": [
        {{
            "question": "Short, direct question text (max 25 words)",
            "category": "background_verification|skill_validation|motivation_fit",
            "purpose": "Brief reason (max 50 words)",
            "priority": "high|medium",
            "expected_duration": "1-2 min"
        }}
    ],
    "total_questions": {target_questions},
    "estimated_duration": "{5 if target_questions == 3 else 8}-10 minutes",
    "complexity_level": "{complexity_level}",
    "focus_areas": ["Quick Assessment", "Key Skills", "Cultural Fit"],
    "question_distribution": {{
        "background_verification": 1,
        "skill_validation": {max(1, target_questions-2)}, 
        "motivation_fit": 1
    }}
}}

Keep it SIMPLE and FAST for efficient screening!
"""
    
    return prompt

@app.post("/generate-questions", response_model=InterviewQuestionsResult)
async def generate_interview_questions(request: InterviewQuestionsRequest):
    """
    Generate tailored interview questions based on resume and job description
    """
    try:
        print(f"DEBUG QUESTIONS AGENT: Received request to generate interview questions")
        print(f"DEBUG QUESTIONS AGENT: Resume data length: {len(request.resume_data)} chars")
        print(f"DEBUG QUESTIONS AGENT: Job description length: {len(request.job_description)} chars")
        print(f"DEBUG QUESTIONS AGENT: Matching results keys: {list(request.matching_results.keys())}")
        
        # Determine complexity and question count
        matching_score = float(request.matching_results.get('overall_score', 0))
        complexity_level, target_questions = determine_complexity_and_question_count(
            request.resume_data, 
            request.job_description, 
            matching_score
        )
        
        print(f"DEBUG QUESTIONS AGENT: Generating {target_questions} questions for {complexity_level} level candidate")
        print(f"DEBUG QUESTIONS AGENT: Matching score: {matching_score}%")
        
        # Create comprehensive prompt
        prompt = create_interview_questions_prompt(
            request.resume_data,
            request.job_description,
            request.matching_results,
            complexity_level,
            target_questions
        )
        
        # Generate questions using AI
        print("DEBUG QUESTIONS AGENT: Calling AI model to generate questions...")
        response = llm.invoke(prompt)
        
        # Parse AI response
        try:
            # Extract JSON from response
            response_text = response.content
            print(f"DEBUG QUESTIONS AGENT: Raw AI response length: {len(response_text)} characters")
            
            # Find JSON in response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found in AI response")
            
            json_text = response_text[start_idx:end_idx]
            questions_data = json.loads(json_text)
            
            print(f"DEBUG QUESTIONS AGENT: Successfully parsed {questions_data.get('total_questions', 0)} questions")
            
            # Validate and ensure required fields
            if 'questions' not in questions_data:
                raise ValueError("No questions found in AI response")
            
            # Calculate question distribution
            distribution = {
                "background_verification": 0,
                "skill_validation": 0,
                "gap_exploration": 0,
                "motivation_fit": 0
            }
            
            for q in questions_data['questions']:
                category = q.get('category', 'background_verification')
                if category in distribution:
                    distribution[category] += 1
            
            # Build result
            result = InterviewQuestionsResult(
                questions=[
                    QuestionItem(
                        question=q.get('question', ''),
                        category=q.get('category', 'background_verification'),
                        purpose=q.get('purpose', ''),
                        priority=q.get('priority', 'medium'),
                        expected_duration=q.get('expected_duration', '2-3 min')
                    ) for q in questions_data['questions']
                ],
                total_questions=len(questions_data['questions']),
                estimated_duration=questions_data.get('estimated_duration', '15-20 minutes'),
                complexity_level=complexity_level,
                focus_areas=questions_data.get('focus_areas', []),
                question_distribution=distribution
            )
            
            print(f"DEBUG QUESTIONS AGENT: Successfully generated interview questions")
            print(f"DEBUG QUESTIONS AGENT: Distribution: {distribution}")
            
            return result
            
        except (json.JSONDecodeError, KeyError, ValueError) as parse_error:
            print(f"DEBUG QUESTIONS AGENT: Error parsing AI response: {parse_error}")
            print(f"DEBUG QUESTIONS AGENT: Raw response: {response.content[:500]}...")
            
            # Fallback: create basic questions
            fallback_questions = create_fallback_questions(target_questions, complexity_level)
            return fallback_questions
            
    except Exception as e:
        print(f"ERROR QUESTIONS AGENT: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating interview questions: {str(e)}")

def create_fallback_questions(target_questions: int, complexity_level: str) -> InterviewQuestionsResult:
    """Create simplified fallback questions if AI generation fails"""
    
    fallback_questions = [
        {
            "question": "Can you briefly walk me through your current role and main responsibilities?",
            "category": "background_verification",
            "purpose": "Understand current experience and role fit",
            "priority": "high",
            "expected_duration": "1-2 min"
        },
        {
            "question": "What's your strongest technical skill that's relevant to this position?",
            "category": "skill_validation", 
            "purpose": "Validate key technical competency quickly",
            "priority": "high",
            "expected_duration": "1-2 min"
        },
        {
            "question": "Why are you interested in this specific role with our company?",
            "category": "motivation_fit",
            "purpose": "Assess genuine interest and motivation",
            "priority": "medium",
            "expected_duration": "1-2 min"
        },
        {
            "question": "Tell me about a recent project you're proud of and your role in it.",
            "category": "background_verification",
            "purpose": "Quick assessment of hands-on experience",
            "priority": "high",
            "expected_duration": "2 min"
        }
    ]
    
    # Take only the number needed (max 4 for quick screening)
    selected_questions = fallback_questions[:min(target_questions, 4)]
    
    # Calculate distribution
    distribution = {
        "background_verification": len([q for q in selected_questions if q['category'] == 'background_verification']),
        "skill_validation": len([q for q in selected_questions if q['category'] == 'skill_validation']),
        "motivation_fit": len([q for q in selected_questions if q['category'] == 'motivation_fit'])
    }
    
    estimated_time = "5-8 minutes" if len(selected_questions) <= 3 else "8-10 minutes"
    
    return InterviewQuestionsResult(
        questions=[QuestionItem(**q) for q in selected_questions],
        total_questions=len(selected_questions),
        estimated_duration=estimated_time,
        complexity_level=complexity_level,
        focus_areas=["Quick Assessment", "Key Skills", "Cultural Fit"],
        question_distribution=distribution
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Interview Questions Agent"}

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Interview Questions Agent",
        "version": "1.0.0",
        "endpoints": {
            "generate": "/generate-questions",
            "health": "/health",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)