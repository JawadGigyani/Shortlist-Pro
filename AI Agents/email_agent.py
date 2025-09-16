import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from zoom_integration import ZoomAPI

# Load credentials from .env
load_dotenv()
SENDER_EMAIL = os.getenv("EMAIL_ADDRESS")
APP_PASSWORD = os.getenv("APP_PASSWORD")

# Database configuration (same as Django settings.py)
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'shortlistpro_db',
    'user': 'postgres',
    'password': 'root'
}

app = FastAPI(title="Email Service", description="Simple email service for ShortlistPro")

# Add CORS middleware to allow requests from Django frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],  # Django server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class EmailRequest(BaseModel):
    candidate_ids: List[int]
    email_type: str  # "selection" or "rejection"
    hr_user_id: int  # ID of the HR user sending emails
    interview_round: str = "initial"  # For selection emails: "technical", "behavioral", "final"
    
    # New interview scheduling fields
    interviewType: str = None  # "onsite" or "online"
    interviewDateTime: str = None  # ISO format datetime string
    interviewLocation: str = None  # Address for onsite or "default_office_address"

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def get_candidate_data(interview_recording_ids: List[int]):
    """Fetch candidate data from database using Django table names via InterviewRecording"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            ir.id as interview_recording_id,
            mr.id as matching_result_id,
            r.candidate_name,
            r.email,
            jd.title as position,
            jd.id as jd_id,
            p.company_name as company
        FROM home_interviewrecording ir
        JOIN home_matchingresult mr ON ir.matching_result_id = mr.id
        JOIN home_resume r ON mr.resume_id = r.id
        JOIN home_jobdescription jd ON mr.job_description_id = jd.id
        JOIN auth_user u ON jd.user_id = u.id
        JOIN home_profile p ON u.id = p.user_id
        WHERE ir.id = ANY(%s)
        """
        
        cursor.execute(query, (interview_recording_ids,))
        candidates = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return candidates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

def get_hr_user_profile(hr_user_id: int):
    """Get HR user's profile information including office address"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user profile information
        cursor.execute("""
            SELECT p.office_address, p.company_name
            FROM home_profile p
            WHERE p.user_id = %s
        """, (hr_user_id,))
        
        profile = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return profile
    except Exception as e:
        return {'office_address': '', 'company_name': 'Company'}

def format_interview_datetime(iso_datetime_str: str):
    """Format ISO datetime string to human-readable format"""
    try:
        dt = datetime.fromisoformat(iso_datetime_str.replace('Z', '+00:00'))
        return {
            'formatted_date': dt.strftime('%B %d, %Y'),  # January 15, 2024
            'formatted_time': dt.strftime('%I:%M %p'),   # 2:30 PM
            'utc_datetime': iso_datetime_str
        }
    except Exception as e:
        return {
            'formatted_date': 'TBD',
            'formatted_time': 'TBD',
            'utc_datetime': iso_datetime_str
        }

def create_zoom_meeting(candidate_name: str, interview_type: str, start_time: str):
    """Create Zoom meeting and return meeting details"""
    try:
        zoom = ZoomAPI()
        meeting_data = zoom.create_meeting(
            candidate_name=candidate_name,
            interview_type=interview_type,
            start_time=start_time,
            duration=30
        )
        return meeting_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create Zoom meeting: {str(e)}")

def update_interview_recording_with_meeting_data(recording_id: int, interview_data: dict):
    """Update InterviewRecording with meeting details and schedule information"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update the interview recording with meeting details
        cursor.execute("""
            UPDATE home_interviewrecording 
            SET interview_type = %s, 
                interview_date = %s, 
                interview_location = %s,
                meeting_link = %s,
                meeting_id = %s,
                meeting_password = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            interview_data.get('interview_type'),
            interview_data.get('interview_date'),
            interview_data.get('interview_location'),
            interview_data.get('meeting_link'),
            interview_data.get('meeting_id'),
            interview_data.get('meeting_password'),
            recording_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update interview recording: {str(e)}")

def create_selection_email(candidate_name: str, position: str, company: str, hr_user_id: int, jd_id: int):
    """Create beautiful selection email template"""
    subject = f"🎉 Interview Invitation - {position} at {company}"
    
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interview Invitation</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f8fafc; line-height: 1.6;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        
        <!-- Header with Gradient -->
        <div style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 50%, #3b82f6 100%); padding: 40px 30px; text-align: center; border-radius: 12px 12px 0 0;">
            <div style="background-color: rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px); padding: 20px; border-radius: 12px; display: inline-block;">
                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.025em;">
                    🎉 Congratulations!
                </h1>
                <p style="color: rgba(255, 255, 255, 0.9); margin: 10px 0 0 0; font-size: 16px;">
                    Your application has been selected
                </p>
            </div>
        </div>
        
        <!-- Main Content -->
        <div style="padding: 40px 30px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <div style="background-color: #f0f9ff; border: 2px solid #3b82f6; border-radius: 50%; width: 80px; height: 80px; margin: 0 auto 20px; line-height: 76px; text-align: center; vertical-align: middle;">
                    <span style="font-size: 32px; display: inline-block; vertical-align: middle; line-height: normal;">✅</span>
                </div>
                <h2 style="color: #1f2937; margin: 0; font-size: 24px; font-weight: 600;">
                    Interview Invitation
                </h2>
            </div>
            
            <div style="background-color: #f9fafb; border-left: 4px solid #10b981; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
                <p style="color: #374151; margin: 0; font-size: 16px;">
                    Dear <strong>{candidate_name}</strong>,
                </p>
            </div>
            
            <div style="margin-bottom: 30px;">
                <p style="color: #4b5563; margin: 0 0 15px 0; font-size: 16px;">
                    We are pleased to inform you that your application for the <strong style="color: #3b82f6;">{position}</strong> position at <strong style="color: #3b82f6;">{company}</strong> has been selected for the next stage.
                </p>
                
                <p style="color: #4b5563; margin: 0 0 15px 0; font-size: 16px;">
                    We would like to invite you for a brief <strong>5-minute initial interview</strong> to discuss your background and the role in more detail.
                </p>
                
                <p style="color: #4b5563; margin: 0; font-size: 16px;">
                    Our team will contact you shortly to schedule this interview at your convenience.
                </p>
            </div>
            
            <!-- Key Details Card -->
            <div style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); border-radius: 12px; padding: 25px; margin-bottom: 30px;">
                <h3 style="color: #ffffff; margin: 0 0 15px 0; font-size: 18px; font-weight: 600;">
                    📋 Position Details
                </h3>
                <div style="background-color: rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 15px;">
                    <p style="color: rgba(255, 255, 255, 0.9); margin: 0 0 8px 0; font-size: 14px;">
                        <strong>Position:</strong> {position}
                    </p>
                    <p style="color: rgba(255, 255, 255, 0.9); margin: 0; font-size: 14px;">
                        <strong>Company:</strong> {company}
                    </p>
                </div>
            </div>
            
            <!-- Next Steps -->
            <div style="background-color: #f0f9ff; border: 1px solid #e0f2fe; border-radius: 8px; padding: 20px; margin-bottom: 30px;">
                <h3 style="color: #1e40af; margin: 0 0 15px 0; font-size: 18px; font-weight: 600;">
                    � Start Your Interview
                </h3>
                <p style="color: #475569; margin: 0 0 15px 0; font-size: 15px;">
                    You can now access your AI-powered initial interview. Click the button below to begin:
                </p>
                
                <!-- Interview Button -->
                <div style="text-align: center; margin: 20px 0;">
                    <a href="http://localhost:8000/interview/{hr_user_id}/{jd_id}/" 
                       style="display: inline-block; background: linear-gradient(135deg, #10b981 0%, #3b82f6 100%); color: #ffffff; padding: 15px 30px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                        🎯 Access Interview Portal
                    </a>
                </div>
                
                <p style="color: #6b7280; margin: 0; font-size: 14px; text-align: center;">
                    <em>Use your email address to access the interview</em>
                </p>
            </div>
            
            <!-- Additional Information -->
            <div style="background-color: #fef3f2; border: 1px solid #fecaca; border-radius: 8px; padding: 20px; margin-bottom: 30px;">
                <h3 style="color: #dc2626; margin: 0 0 15px 0; font-size: 18px; font-weight: 600;">
                    📞 Alternative: Phone Interview
                </h3>
                <ul style="color: #7f1d1d; margin: 0; padding-left: 20px; font-size: 15px;">
                    <li style="margin-bottom: 8px;">If you prefer, our HR team will also contact you within 2-3 business days</li>
                    <li style="margin-bottom: 8px;">We'll schedule a convenient time for a phone interview</li>
                    <li style="margin-bottom: 0;">Please keep your phone accessible for our call</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin-bottom: 20px;">
                <p style="color: #6b7280; margin: 0; font-size: 15px;">
                    Thank you for your interest in joining <strong>{company}</strong>
                </p>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="background-color: #f9fafb; padding: 30px; text-align: center; border-top: 1px solid #e5e7eb;">
            <p style="color: #374151; margin: 0 0 10px 0; font-size: 16px; font-weight: 600;">
                Best regards,
            </p>
            <p style="color: #6b7280; margin: 0 0 20px 0; font-size: 15px;">
                {company} Recruitment Team
            </p>
            
            <!-- Brand Footer -->
            <div style="border-top: 1px solid #e5e7eb; padding-top: 20px; margin-top: 20px;">
                <div style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-size: 18px; font-weight: 700; margin-bottom: 5px;">
                    ShortlistPro
                </div>
                <p style="color: #9ca3af; margin: 0; font-size: 12px;">
                    AI-Powered Recruitment Platform
                </p>
            </div>
        </div>
    </div>
</body>
</html>"""

    return subject, body

def create_rejection_email(candidate_name: str, position: str, company: str):
    """Create beautiful rejection email template"""
    subject = f"Application Update - {position} at {company}"
    
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Application Update</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f8fafc; line-height: 1.6;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        
        <!-- Header with Gradient -->
        <div style="background: linear-gradient(135deg, #6b7280 0%, #4b5563 50%, #6b7280 100%); padding: 40px 30px; text-align: center; border-radius: 12px 12px 0 0;">
            <div style="background-color: rgba(255, 255, 255, 0.15); backdrop-filter: blur(10px); padding: 20px; border-radius: 12px; display: inline-block;">
                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.025em;">
                    Thank You
                </h1>
                <p style="color: rgba(255, 255, 255, 0.9); margin: 10px 0 0 0; font-size: 16px;">
                    Application Update
                </p>
            </div>
        </div>
        
        <!-- Main Content -->
        <div style="padding: 40px 30px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <div style="background-color: #fef3f2; border: 2px solid #f87171; border-radius: 50%; width: 80px; height: 80px; margin: 0 auto 20px; line-height: 76px; text-align: center; vertical-align: middle;">
                    <span style="font-size: 32px; display: inline-block; vertical-align: middle; line-height: normal;">📧</span>
                </div>
                <h2 style="color: #1f2937; margin: 0; font-size: 24px; font-weight: 600;">
                    Application Status Update
                </h2>
            </div>
            
            <div style="background-color: #f9fafb; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
                <p style="color: #374151; margin: 0; font-size: 16px;">
                    Dear <strong>{candidate_name}</strong>,
                </p>
            </div>
            
            <div style="margin-bottom: 30px;">
                <p style="color: #4b5563; margin: 0 0 15px 0; font-size: 16px;">
                    Thank you for your interest in the <strong style="color: #6b7280;">{position}</strong> position at <strong style="color: #6b7280;">{company}</strong> and for taking the time to apply.
                </p>
                
                <p style="color: #4b5563; margin: 0 0 15px 0; font-size: 16px;">
                    After careful consideration of your application, we have decided to move forward with other candidates whose qualifications more closely match our current needs.
                </p>
                
                <p style="color: #4b5563; margin: 0; font-size: 16px;">
                    We appreciate the time and effort you invested in your application.
                </p>
            </div>
            
            <!-- Position Details Card -->
            <div style="background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%); border-radius: 12px; padding: 25px; margin-bottom: 30px;">
                <h3 style="color: #ffffff; margin: 0 0 15px 0; font-size: 18px; font-weight: 600;">
                    📋 Application Details
                </h3>
                <div style="background-color: rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 15px;">
                    <p style="color: rgba(255, 255, 255, 0.9); margin: 0 0 8px 0; font-size: 14px;">
                        <strong>Position:</strong> {position}
                    </p>
                    <p style="color: rgba(255, 255, 255, 0.9); margin: 0; font-size: 14px;">
                        <strong>Company:</strong> {company}
                    </p>
                </div>
            </div>
            
            <!-- Future Opportunities -->
            <div style="background-color: #f0f9ff; border: 1px solid #e0f2fe; border-radius: 8px; padding: 20px; margin-bottom: 30px;">
                <h3 style="color: #1e40af; margin: 0 0 15px 0; font-size: 18px; font-weight: 600;">
                    🚀 Future Opportunities
                </h3>
                <p style="color: #475569; margin: 0; font-size: 15px;">
                    We encourage you to apply for future opportunities that match your skills and experience. Your profile will remain in our database for future consideration.
                </p>
            </div>
            
            <!-- Professional Development Tips -->
            <div style="background-color: #fefce8; border: 1px solid #fde047; border-radius: 8px; padding: 20px; margin-bottom: 30px;">
                <h3 style="color: #ca8a04; margin: 0 0 15px 0; font-size: 18px; font-weight: 600;">
                    💡 Keep Growing
                </h3>
                <ul style="color: #713f12; margin: 0; padding-left: 20px; font-size: 15px;">
                    <li style="margin-bottom: 8px;">Continue building relevant skills in your field</li>
                    <li style="margin-bottom: 8px;">Consider networking with professionals in the industry</li>
                    <li style="margin-bottom: 0;">Stay updated with industry trends and technologies</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin-bottom: 20px;">
                <p style="color: #6b7280; margin: 0; font-size: 15px;">
                    Thank you again for considering <strong>{company}</strong> as a potential employer
                </p>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="background-color: #f9fafb; padding: 30px; text-align: center; border-top: 1px solid #e5e7eb;">
            <p style="color: #374151; margin: 0 0 10px 0; font-size: 16px; font-weight: 600;">
                Best regards,
            </p>
            <p style="color: #6b7280; margin: 0 0 20px 0; font-size: 15px;">
                {company} Recruitment Team
            </p>
            
            <!-- Brand Footer -->
            <div style="border-top: 1px solid #e5e7eb; padding-top: 20px; margin-top: 20px;">
                <div style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-size: 18px; font-weight: 700; margin-bottom: 5px;">
                    ShortlistPro
                </div>
                <p style="color: #9ca3af; margin: 0; font-size: 12px;">
                    AI-Powered Recruitment Platform
                </p>
            </div>
        </div>
    </div>
</body>
</html>"""

    return subject, body

def send_email(to_email: str, subject: str, body: str):
    """Send HTML email using SMTP"""
    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = SENDER_EMAIL
        message["To"] = to_email
        
        # Create HTML part
        html_part = MIMEText(body, "html")
        message.attach(html_part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, message.as_string())
        
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {str(e)}")
        return False

@app.post("/send-emails")
async def send_candidate_emails(request: EmailRequest):
    """Send emails to selected candidates with enhanced interview scheduling"""
    try:
        # Get candidate data
        candidates = get_candidate_data(request.candidate_ids)
        
        if not candidates:
            raise HTTPException(status_code=404, detail="No candidates found")
        
        # Get HR user profile information for office address
        hr_profile = get_hr_user_profile(request.hr_user_id)
        
        success_count = 0
        failed_emails = []
        
        # Process interview scheduling data if provided
        interview_details = None
        if request.interviewDateTime and request.interviewType:
            datetime_info = format_interview_datetime(request.interviewDateTime)
            
            # Handle interview location
            interview_location = ""
            if request.interviewType == "onsite":
                if request.interviewLocation == "default_office_address":
                    interview_location = hr_profile.get('office_address', 'Office address not configured') if hr_profile else 'Office address not configured'
                else:
                    interview_location = request.interviewLocation
            
            interview_details = {
                'interview_type': request.interviewType,
                'interview_date': request.interviewDateTime,
                'location': interview_location,
                **datetime_info
            }
        
        for candidate in candidates:
            candidate_name = candidate['candidate_name'] or "Candidate"
            position = candidate['position'] or "Position"
            company = candidate['company'] or hr_profile.get('company_name', 'Our Company') if hr_profile else 'Our Company'
            email = candidate['email']
            jd_id = candidate['jd_id']
            matching_result_id = candidate['matching_result_id']
            interview_recording_id = candidate['interview_recording_id']
            
            print(f"DEBUG EMAIL AGENT: Processing candidate {candidate_name} (email: {email})")
            print(f"DEBUG EMAIL AGENT: Interview type: {request.interviewType}, DateTime: {request.interviewDateTime}")
            
            if not email:
                failed_emails.append(f"{candidate_name} (no email)")
                continue
            
            # Create Zoom meeting if this is an online interview
            candidate_interview_details = interview_details.copy() if interview_details else None
            
            if (candidate_interview_details and 
                candidate_interview_details['interview_type'] == 'online' and 
                request.email_type == 'selection' and 
                request.interview_round != 'initial'):
                
                try:
                    print(f"DEBUG EMAIL AGENT: Creating Zoom meeting for {candidate_name}")
                    zoom_meeting = create_zoom_meeting(
                        candidate_name=candidate_name,
                        interview_type=request.interview_round,
                        start_time=candidate_interview_details['utc_datetime']
                    )
                    
                    # Add Zoom details to interview details
                    candidate_interview_details.update({
                        'zoom_link': zoom_meeting['join_url'],
                        'meeting_id': str(zoom_meeting['meeting_id']),
                        'meeting_password': zoom_meeting.get('password', ''),
                        'meeting_link': zoom_meeting['join_url']
                    })
                    
                    print(f"DEBUG EMAIL AGENT: Zoom meeting created successfully: {zoom_meeting['join_url']}")
                    
                except Exception as zoom_error:
                    print(f"ERROR EMAIL AGENT: Failed to create Zoom meeting for {candidate_name}: {zoom_error}")
                    failed_emails.append(f"{candidate_name} (Zoom creation failed)")
                    continue
            
            # Create email based on type and interview round
            try:
                if request.email_type == "selection":
                    if request.interview_round == "initial":
                        subject, body = create_selection_email(candidate_name, position, company, request.hr_user_id, jd_id)
                    elif request.interview_round == "technical":
                        subject, body = create_technical_interview_email(candidate_name, position, company, candidate_interview_details)
                    elif request.interview_round == "behavioral":
                        subject, body = create_behavioral_interview_email(candidate_name, position, company, candidate_interview_details)
                    elif request.interview_round == "final":
                        subject, body = create_final_interview_email(candidate_name, position, company, candidate_interview_details)
                    else:
                        # Default to initial interview
                        subject, body = create_selection_email(candidate_name, position, company, request.hr_user_id, jd_id)
                elif request.email_type == "rejection":
                    subject, body = create_rejection_email(candidate_name, position, company)
                else:
                    raise HTTPException(status_code=400, detail="Invalid email type. Use 'selection' or 'rejection'")
                
                print(f"DEBUG EMAIL AGENT: Created {request.interview_round} {request.email_type} email for {candidate_name}")
                
            except Exception as email_creation_error:
                print(f"ERROR EMAIL AGENT: Failed to create email for {candidate_name}: {email_creation_error}")
                failed_emails.append(f"{candidate_name} (email creation failed)")
                continue
            
            # Send email
            if send_email(email, subject, body):
                success_count += 1
                print(f"DEBUG EMAIL AGENT: Successfully sent email to {email} for candidate {candidate_name}")
                
                # Update database with email status and interview details
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    if request.email_type == 'selection':
                        # Update MatchingResult
                        cursor.execute("""
                            UPDATE home_matchingresult 
                            SET email_status = %s, status = %s
                            WHERE id = %s
                        """, ('selection_sent', 'shortlisted', matching_result_id))
                        
                        # Update InterviewRecording with email status and meeting details
                        if candidate_interview_details:
                            cursor.execute("""
                                UPDATE home_interviewrecording 
                                SET email_sent = %s, 
                                    email_type = %s, 
                                    interview_round = %s, 
                                    email_sent_at = NOW(),
                                    interview_type = %s,
                                    interview_date = %s,
                                    interview_location = %s,
                                    meeting_link = %s,
                                    meeting_id = %s,
                                    meeting_password = %s
                                WHERE id = %s
                            """, (
                                True, 'selection', request.interview_round,
                                candidate_interview_details.get('interview_type'),
                                candidate_interview_details.get('interview_date'),
                                candidate_interview_details.get('location'),
                                candidate_interview_details.get('meeting_link'),
                                candidate_interview_details.get('meeting_id'),
                                candidate_interview_details.get('meeting_password'),
                                interview_recording_id
                            ))
                        else:
                            cursor.execute("""
                                UPDATE home_interviewrecording 
                                SET email_sent = %s, email_type = %s, interview_round = %s, email_sent_at = NOW()
                                WHERE id = %s
                            """, (True, 'selection', request.interview_round, interview_recording_id))
                    else:
                        # Rejection email
                        cursor.execute("""
                            UPDATE home_matchingresult 
                            SET email_status = %s
                            WHERE id = %s
                        """, ('rejection_sent', matching_result_id))
                        
                        cursor.execute("""
                            UPDATE home_interviewrecording 
                            SET email_sent = %s, email_type = %s, email_sent_at = NOW()
                            WHERE id = %s
                        """, (True, 'rejection', interview_recording_id))
                    
                    conn.commit()
                    cursor.close()
                    conn.close()
                    print(f"DEBUG EMAIL AGENT: Database update successful for candidate {candidate_name}")
                    
                except Exception as db_error:
                    print(f"WARNING EMAIL AGENT: Failed to update database for candidate {candidate_name}: {db_error}")
            else:
                print(f"DEBUG EMAIL AGENT: Failed to send email to {email} for candidate {candidate_name}")
                failed_emails.append(f"{candidate_name} ({email})")
        
        return {
            "success": True,
            "message": f"Successfully sent {success_count} emails",
            "success_count": success_count,
            "failed_count": len(failed_emails),
            "failed_emails": failed_emails
        }
        
    except Exception as e:
        print(f"CRITICAL ERROR EMAIL AGENT: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def create_technical_interview_email(candidate_name: str, position: str, company: str, interview_data: dict = None):
    """Create technical interview invitation email template with scheduling details"""
    subject = f"Technical Interview Scheduled - {position} at {company}"
    
    # Extract interview details if provided
    interview_type = interview_data.get('interview_type', 'online') if interview_data else 'online'
    interview_date = interview_data.get('formatted_date', 'TBD') if interview_data else 'TBD'
    interview_time = interview_data.get('formatted_time', 'TBD') if interview_data else 'TBD'
    
    # Location/Meeting details based on type
    location_html = ""
    if interview_type == 'onsite' and interview_data:
        location_html = f"""
            <div style="background-color: #f0fdf4; border: 2px solid #16a34a; border-radius: 12px; padding: 20px; margin: 20px 0; text-align: center;">
                <div style="margin-bottom: 15px;">
                    <span style="background-color: #16a34a; color: white; padding: 8px 16px; border-radius: 20px; font-weight: 600; font-size: 14px;">
                        📍 IN-PERSON INTERVIEW
                    </span>
                </div>
                <div style="color: #166534; font-weight: 600; margin-bottom: 10px;">Interview Location:</div>
                <div style="color: #15803d; white-space: pre-line; font-size: 15px; line-height: 1.5;">
                    {interview_data.get('location', 'Address will be provided')}
                </div>
            </div>
        """
    elif interview_type == 'online' and interview_data:
        zoom_link = interview_data.get('zoom_link', '#')
        meeting_id = interview_data.get('meeting_id', 'N/A')
        meeting_password = interview_data.get('meeting_password', 'N/A')
        
        location_html = f"""
            <div style="background-color: #f0f9ff; border: 2px solid #3b82f6; border-radius: 12px; padding: 20px; margin: 20px 0; text-align: center;">
                <div style="margin-bottom: 15px;">
                    <span style="background-color: #3b82f6; color: white; padding: 8px 16px; border-radius: 20px; font-weight: 600; font-size: 14px;">
                        💻 VIRTUAL INTERVIEW
                    </span>
                </div>
                <div style="color: #1e40af; font-weight: 600; margin-bottom: 15px;">Join Zoom Meeting:</div>
                <a href="{zoom_link}" style="display: inline-block; background-color: #3b82f6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; margin-bottom: 15px;">
                    Join Meeting
                </a>
                <div style="color: #1e40af; font-size: 14px; margin-top: 10px;">
                    <strong>Meeting ID:</strong> {meeting_id}<br>
                    {"<strong>Password:</strong> " + meeting_password if meeting_password != 'N/A' else ""}
                </div>
            </div>
        """
    
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Technical Interview Invitation</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f8fafc; line-height: 1.6;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        
        <!-- Header with Gradient -->
        <div style="background: linear-gradient(135deg, #7c3aed 0%, #3b82f6 50%, #06b6d4 100%); padding: 40px 30px; text-align: center; border-radius: 12px 12px 0 0;">
            <div style="background-color: rgba(255, 255, 255, 0.15); backdrop-filter: blur(10px); padding: 20px; border-radius: 12px; display: inline-block;">
                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.025em;">
                    Technical Interview
                </h1>
                <p style="color: rgba(255, 255, 255, 0.9); margin: 10px 0 0 0; font-size: 16px;">
                    {interview_date} at {interview_time}
                </p>
            </div>
        </div>
        
        <!-- Main Content -->
        <div style="padding: 40px 30px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <div style="background-color: #faf5ff; border: 2px solid #7c3aed; border-radius: 50%; width: 80px; height: 80px; margin: 0 auto 20px; line-height: 76px; text-align: center; vertical-align: middle;">
                    <span style="font-size: 32px; display: inline-block; vertical-align: middle; line-height: normal;">💻</span>
                </div>
                <h2 style="color: #1f2937; margin: 0; font-size: 24px; font-weight: 600;">
                    Technical Assessment Invitation
                </h2>
            </div>
            
            <div style="background-color: #f0f9ff; border-left: 4px solid #7c3aed; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
                <p style="color: #374151; margin: 0; font-size: 16px;">
                    Dear <strong>{candidate_name}</strong>,
                </p>
            </div>
            
            <div style="margin-bottom: 30px;">
                <p style="color: #4b5563; margin: 0 0 15px 0; font-size: 16px;">
                    Congratulations! Based on your initial interview performance, we would like to invite you to the <strong style="color: #7c3aed;">technical assessment round</strong> for the <strong style="color: #3b82f6;">{position}</strong> position.
                </p>
                
                <p style="color: #4b5563; margin: 0 0 15px 0; font-size: 16px;">
                    This technical interview will focus on evaluating your problem-solving skills, technical knowledge, and hands-on experience relevant to the role.
                </p>
            </div>
            
            <!-- Interview Details -->
            <div style="background-color: #fafafa; border: 1px solid #e5e7eb; border-radius: 12px; padding: 25px; margin: 25px 0;">
                <h3 style="color: #374151; margin: 0 0 20px 0; font-size: 20px; font-weight: 600; text-align: center;">
                    📅 Interview Details
                </h3>
                <div style="display: grid; gap: 15px;">
                    <div style="display: flex; align-items: center;">
                        <div style="background-color: #7c3aed; color: white; border-radius: 50%; width: 32px; height: 32px; line-height: 32px; text-align: center; margin-right: 15px; font-size: 14px;">
                            📅
                        </div>
                        <div>
                            <div style="font-weight: 600; color: #374151;">Date & Time</div>
                            <div style="color: #6b7280;">{interview_date} at {interview_time}</div>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <div style="background-color: #7c3aed; color: white; border-radius: 50%; width: 32px; height: 32px; line-height: 32px; text-align: center; margin-right: 15px; font-size: 14px;">
                            ⏱️
                        </div>
                        <div>
                            <div style="font-weight: 600; color: #374151;">Duration</div>
                            <div style="color: #6b7280;">30 minutes</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Location/Meeting Details -->
            {location_html}
            
            <!-- Technical Interview Details -->
            <div style="background: linear-gradient(135deg, #7c3aed 0%, #3b82f6 100%); border-radius: 12px; padding: 25px; margin-bottom: 30px;">
                <h3 style="color: #ffffff; margin: 0 0 15px 0; font-size: 18px; font-weight: 600;">
                    🚀 What to Expect
                </h3>
                <div style="background-color: rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 15px;">
                    <ul style="color: rgba(255, 255, 255, 0.9); margin: 0; padding-left: 20px; font-size: 14px;">
                        <li style="margin-bottom: 8px;">Technical problem-solving questions</li>
                        <li style="margin-bottom: 8px;">Code review and discussion</li>
                        <li style="margin-bottom: 8px;">System design concepts (if applicable)</li>
                        <li style="margin-bottom: 0;">Hands-on coding exercises</li>
                    </ul>
                </div>
            </div>
            
            <div style="text-align: center; margin-bottom: 20px;">
                <p style="color: #6b7280; margin: 0; font-size: 15px;">
                    We're excited to see your technical skills in action!
                </p>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="background-color: #f9fafb; padding: 30px; text-align: center; border-top: 1px solid #e5e7eb;">
            <p style="color: #374151; margin: 0 0 10px 0; font-size: 16px; font-weight: 600;">
                Best regards,
            </p>
            <p style="color: #6b7280; margin: 0 0 20px 0; font-size: 15px;">
                {company} Technical Team
            </p>
            
            <!-- Brand Footer -->
            <div style="border-top: 1px solid #e5e7eb; padding-top: 20px; margin-top: 20px;">
                <div style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-size: 18px; font-weight: 700; margin-bottom: 5px;">
                    ShortlistPro
                </div>
                <p style="color: #9ca3af; margin: 0; font-size: 12px;">
                    AI-Powered Recruitment Platform
                </p>
            </div>
        </div>
    </div>
</body>
</html>"""

    return subject, body

def create_behavioral_interview_email(candidate_name: str, position: str, company: str, interview_data: dict = None):
    """Create behavioral interview invitation email template with scheduling details"""
    subject = f"Behavioral Interview Scheduled - {position} at {company}"
    
    # Extract interview details if provided
    interview_type = interview_data.get('interview_type', 'online') if interview_data else 'online'
    interview_date = interview_data.get('formatted_date', 'TBD') if interview_data else 'TBD'
    interview_time = interview_data.get('formatted_time', 'TBD') if interview_data else 'TBD'
    
    # Location/Meeting details based on type
    location_html = ""
    if interview_type == 'onsite' and interview_data:
        location_html = f"""
            <div style="background-color: #f0fdf4; border: 2px solid #16a34a; border-radius: 12px; padding: 20px; margin: 20px 0; text-align: center;">
                <div style="margin-bottom: 15px;">
                    <span style="background-color: #16a34a; color: white; padding: 8px 16px; border-radius: 20px; font-weight: 600; font-size: 14px;">
                        📍 IN-PERSON INTERVIEW
                    </span>
                </div>
                <div style="color: #166534; font-weight: 600; margin-bottom: 10px;">Interview Location:</div>
                <div style="color: #15803d; white-space: pre-line; font-size: 15px; line-height: 1.5;">
                    {interview_data.get('location', 'Address will be provided')}
                </div>
            </div>
        """
    elif interview_type == 'online' and interview_data:
        zoom_link = interview_data.get('zoom_link', '#')
        meeting_id = interview_data.get('meeting_id', 'N/A')
        meeting_password = interview_data.get('meeting_password', 'N/A')
        
        location_html = f"""
            <div style="background-color: #f0f9ff; border: 2px solid #3b82f6; border-radius: 12px; padding: 20px; margin: 20px 0; text-align: center;">
                <div style="margin-bottom: 15px;">
                    <span style="background-color: #3b82f6; color: white; padding: 8px 16px; border-radius: 20px; font-weight: 600; font-size: 14px;">
                        💻 VIRTUAL INTERVIEW
                    </span>
                </div>
                <div style="color: #1e40af; font-weight: 600; margin-bottom: 15px;">Join Zoom Meeting:</div>
                <a href="{zoom_link}" style="display: inline-block; background-color: #3b82f6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; margin-bottom: 15px;">
                    Join Meeting
                </a>
                <div style="color: #1e40af; font-size: 14px; margin-top: 10px;">
                    <strong>Meeting ID:</strong> {meeting_id}<br>
                    {"<strong>Password:</strong> " + meeting_password if meeting_password != 'N/A' else ""}
                </div>
            </div>
        """
    
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Behavioral Interview Invitation</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f8fafc; line-height: 1.6;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        
        <!-- Header with Gradient -->
        <div style="background: linear-gradient(135deg, #f59e0b 0%, #ef4444 50%, #ec4899 100%); padding: 40px 30px; text-align: center; border-radius: 12px 12px 0 0;">
            <div style="background-color: rgba(255, 255, 255, 0.15); backdrop-filter: blur(10px); padding: 20px; border-radius: 12px; display: inline-block;">
                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.025em;">
                    Behavioral Interview
                </h1>
                <p style="color: rgba(255, 255, 255, 0.9); margin: 10px 0 0 0; font-size: 16px;">
                    {interview_date} at {interview_time}
                </p>
            </div>
        </div>
        
        <!-- Main Content -->
        <div style="padding: 40px 30px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <div style="background-color: #fef3f2; border: 2px solid #f59e0b; border-radius: 50%; width: 80px; height: 80px; margin: 0 auto 20px; line-height: 76px; text-align: center; vertical-align: middle;">
                    <span style="font-size: 32px; display: inline-block; vertical-align: middle; line-height: normal;">🤝</span>
                </div>
                <h2 style="color: #1f2937; margin: 0; font-size: 24px; font-weight: 600;">
                    Behavioral Assessment Invitation
                </h2>
            </div>
            
            <div style="background-color: #fef7ed; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
                <p style="color: #374151; margin: 0; font-size: 16px;">
                    Dear <strong>{candidate_name}</strong>,
                </p>
            </div>
            
            <div style="margin-bottom: 30px;">
                <p style="color: #4b5563; margin: 0 0 15px 0; font-size: 16px;">
                    We're pleased to invite you to the <strong style="color: #f59e0b;">behavioral interview round</strong> for the <strong style="color: #ef4444;">{position}</strong> position at <strong style="color: #ec4899;">{company}</strong>.
                </p>
                
                <p style="color: #4b5563; margin: 0 0 15px 0; font-size: 16px;">
                    This interview will focus on understanding your work style, values, and how you approach challenges in a professional environment.
                </p>
            </div>
            
            <!-- Interview Details -->
            <div style="background-color: #fafafa; border: 1px solid #e5e7eb; border-radius: 12px; padding: 25px; margin: 25px 0;">
                <h3 style="color: #374151; margin: 0 0 20px 0; font-size: 20px; font-weight: 600; text-align: center;">
                    📅 Interview Details
                </h3>
                <div style="display: grid; gap: 15px;">
                    <div style="display: flex; align-items: center;">
                        <div style="background-color: #f59e0b; color: white; border-radius: 50%; width: 32px; height: 32px; line-height: 32px; text-align: center; margin-right: 15px; font-size: 14px;">
                            📅
                        </div>
                        <div>
                            <div style="font-weight: 600; color: #374151;">Date & Time</div>
                            <div style="color: #6b7280;">{interview_date} at {interview_time}</div>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <div style="background-color: #f59e0b; color: white; border-radius: 50%; width: 32px; height: 32px; line-height: 32px; text-align: center; margin-right: 15px; font-size: 14px;">
                            ⏱️
                        </div>
                        <div>
                            <div style="font-weight: 600; color: #374151;">Duration</div>
                            <div style="color: #6b7280;">30 minutes</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Location/Meeting Details -->
            {location_html}
            
            <!-- Behavioral Interview Details -->
            <div style="background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%); border-radius: 12px; padding: 25px; margin-bottom: 30px;">
                <h3 style="color: #ffffff; margin: 0 0 15px 0; font-size: 18px; font-weight: 600;">
                    🎯 Interview Focus Areas
                </h3>
                <div style="background-color: rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 15px;">
                    <ul style="color: rgba(255, 255, 255, 0.9); margin: 0; padding-left: 20px; font-size: 14px;">
                        <li style="margin-bottom: 8px;">Leadership and teamwork experiences</li>
                        <li style="margin-bottom: 8px;">Problem-solving approaches</li>
                        <li style="margin-bottom: 8px;">Communication and conflict resolution</li>
                        <li style="margin-bottom: 0;">Career goals and motivations</li>
                    </ul>
                </div>
            </div>
            
            <div style="text-align: center; margin-bottom: 20px;">
                <p style="color: #6b7280; margin: 0; font-size: 15px;">
                    We're looking forward to learning more about you as a person and professional!
                </p>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="background-color: #f9fafb; padding: 30px; text-align: center; border-top: 1px solid #e5e7eb;">
            <p style="color: #374151; margin: 0 0 10px 0; font-size: 16px; font-weight: 600;">
                Best regards,
            </p>
            <p style="color: #6b7280; margin: 0 0 20px 0; font-size: 15px;">
                {company} HR Team
            </p>
            
            <!-- Brand Footer -->
            <div style="border-top: 1px solid #e5e7eb; padding-top: 20px; margin-top: 20px;">
                <div style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-size: 18px; font-weight: 700; margin-bottom: 5px;">
                    ShortlistPro
                </div>
                <p style="color: #9ca3af; margin: 0; font-size: 12px;">
                    AI-Powered Recruitment Platform
                </p>
            </div>
        </div>
    </div>
</body>
</html>"""

    return subject, body

def create_final_interview_email(candidate_name: str, position: str, company: str, interview_data: dict = None):
    """Create final interview invitation email template with scheduling details"""
    subject = f"Final Interview Scheduled - {position} at {company}"
    
    # Extract interview details if provided
    interview_type = interview_data.get('interview_type', 'online') if interview_data else 'online'
    interview_date = interview_data.get('formatted_date', 'TBD') if interview_data else 'TBD'
    interview_time = interview_data.get('formatted_time', 'TBD') if interview_data else 'TBD'
    
    # Location/Meeting details based on type
    location_html = ""
    if interview_type == 'onsite' and interview_data:
        location_html = f"""
            <div style="background-color: #f0fdf4; border: 2px solid #16a34a; border-radius: 12px; padding: 20px; margin: 20px 0; text-align: center;">
                <div style="margin-bottom: 15px;">
                    <span style="background-color: #16a34a; color: white; padding: 8px 16px; border-radius: 20px; font-weight: 600; font-size: 14px;">
                        📍 IN-PERSON INTERVIEW
                    </span>
                </div>
                <div style="color: #166534; font-weight: 600; margin-bottom: 10px;">Interview Location:</div>
                <div style="color: #15803d; white-space: pre-line; font-size: 15px; line-height: 1.5;">
                    {interview_data.get('location', 'Address will be provided')}
                </div>
            </div>
        """
    elif interview_type == 'online' and interview_data:
        zoom_link = interview_data.get('zoom_link', '#')
        meeting_id = interview_data.get('meeting_id', 'N/A')
        meeting_password = interview_data.get('meeting_password', 'N/A')
        
        location_html = f"""
            <div style="background-color: #f0f9ff; border: 2px solid #3b82f6; border-radius: 12px; padding: 20px; margin: 20px 0; text-align: center;">
                <div style="margin-bottom: 15px;">
                    <span style="background-color: #3b82f6; color: white; padding: 8px 16px; border-radius: 20px; font-weight: 600; font-size: 14px;">
                        💻 VIRTUAL INTERVIEW
                    </span>
                </div>
                <div style="color: #1e40af; font-weight: 600; margin-bottom: 15px;">Join Zoom Meeting:</div>
                <a href="{zoom_link}" style="display: inline-block; background-color: #3b82f6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; margin-bottom: 15px;">
                    Join Meeting
                </a>
                <div style="color: #1e40af; font-size: 14px; margin-top: 10px;">
                    <strong>Meeting ID:</strong> {meeting_id}<br>
                    {"<strong>Password:</strong> " + meeting_password if meeting_password != 'N/A' else ""}
                </div>
            </div>
        """
    
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Final Interview Invitation</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f8fafc; line-height: 1.6;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        
        <!-- Header with Gradient -->
        <div style="background: linear-gradient(135deg, #10b981 0%, #3b82f6 50%, #8b5cf6 100%); padding: 40px 30px; text-align: center; border-radius: 12px 12px 0 0;">
            <div style="background-color: rgba(255, 255, 255, 0.15); backdrop-filter: blur(10px); padding: 20px; border-radius: 12px; display: inline-block;">
                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.025em;">
                    Final Interview
                </h1>
                <p style="color: rgba(255, 255, 255, 0.9); margin: 10px 0 0 0; font-size: 16px;">
                    {interview_date} at {interview_time}
                </p>
            </div>
        </div>
        
        <!-- Main Content -->
        <div style="padding: 40px 30px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <div style="background-color: #ecfdf5; border: 2px solid #10b981; border-radius: 50%; width: 80px; height: 80px; margin: 0 auto 20px; line-height: 76px; text-align: center; vertical-align: middle;">
                    <span style="font-size: 32px; display: inline-block; vertical-align: middle; line-height: normal;">🎉</span>
                </div>
                <h2 style="color: #1f2937; margin: 0; font-size: 24px; font-weight: 600;">
                    Final Round Invitation
                </h2>
            </div>
            
            <div style="background-color: #ecfdf5; border-left: 4px solid #10b981; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
                <p style="color: #374151; margin: 0; font-size: 16px;">
                    Dear <strong>{candidate_name}</strong>,
                </p>
            </div>
            
            <div style="margin-bottom: 30px;">
                <p style="color: #4b5563; margin: 0 0 15px 0; font-size: 16px;">
                    Congratulations! We're excited to invite you to the <strong style="color: #10b981;">final interview round</strong> for the <strong style="color: #3b82f6;">{position}</strong> position at <strong style="color: #8b5cf6;">{company}</strong>.
                </p>
                
                <p style="color: #4b5563; margin: 0 0 15px 0; font-size: 16px;">
                    This final discussion will involve senior leadership and will cover role expectations, compensation, and next steps in your journey with us.
                </p>
            </div>
            
            <!-- Interview Details -->
            <div style="background-color: #fafafa; border: 1px solid #e5e7eb; border-radius: 12px; padding: 25px; margin: 25px 0;">
                <h3 style="color: #374151; margin: 0 0 20px 0; font-size: 20px; font-weight: 600; text-align: center;">
                    📅 Interview Details
                </h3>
                <div style="display: grid; gap: 15px;">
                    <div style="display: flex; align-items: center;">
                        <div style="background-color: #10b981; color: white; border-radius: 50%; width: 32px; height: 32px; line-height: 32px; text-align: center; margin-right: 15px; font-size: 14px;">
                            📅
                        </div>
                        <div>
                            <div style="font-weight: 600; color: #374151;">Date & Time</div>
                            <div style="color: #6b7280;">{interview_date} at {interview_time}</div>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <div style="background-color: #10b981; color: white; border-radius: 50%; width: 32px; height: 32px; line-height: 32px; text-align: center; margin-right: 15px; font-size: 14px;">
                            ⏱️
                        </div>
                        <div>
                            <div style="font-weight: 600; color: #374151;">Duration</div>
                            <div style="color: #6b7280;">30 minutes</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Location/Meeting Details -->
            {location_html}
            
            <!-- Final Interview Details -->
            <div style="background: linear-gradient(135deg, #10b981 0%, #3b82f6 100%); border-radius: 12px; padding: 25px; margin-bottom: 30px;">
                <h3 style="color: #ffffff; margin: 0 0 15px 0; font-size: 18px; font-weight: 600;">
                    🌟 Final Round Topics
                </h3>
                <div style="background-color: rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 15px;">
                    <ul style="color: rgba(255, 255, 255, 0.9); margin: 0; padding-left: 20px; font-size: 14px;">
                        <li style="margin-bottom: 8px;">Role expectations and responsibilities</li>
                        <li style="margin-bottom: 8px;">Team integration and collaboration</li>
                        <li style="margin-bottom: 8px;">Career development opportunities</li>
                        <li style="margin-bottom: 0;">Compensation and benefits discussion</li>
                    </ul>
                </div>
            </div>
            
            <div style="text-align: center; margin-bottom: 20px;">
                <p style="color: #6b7280; margin: 0; font-size: 15px;">
                    You've made it to the final round - we're impressed with your performance so far!
                </p>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="background-color: #f9fafb; padding: 30px; text-align: center; border-top: 1px solid #e5e7eb;">
            <p style="color: #374151; margin: 0 0 10px 0; font-size: 16px; font-weight: 600;">
                Best regards,
            </p>
            <p style="color: #6b7280; margin: 0 0 20px 0; font-size: 15px;">
                {company} Leadership Team
            </p>
            
            <!-- Brand Footer -->
            <div style="border-top: 1px solid #e5e7eb; padding-top: 20px; margin-top: 20px;">
                <div style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-size: 18px; font-weight: 700; margin-bottom: 5px;">
                    ShortlistPro
                </div>
                <p style="color: #9ca3af; margin: 0; font-size: 12px;">
                    AI-Powered Recruitment Platform
                </p>
            </div>
        </div>
    </div>
</body>
</html>"""

    return subject, body

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Email Service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)


