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

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def get_candidate_data(candidate_ids: List[int]):
    """Fetch candidate data from database using Django table names"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            mr.id,
            r.candidate_name,
            r.email,
            jd.title as position,
            jd.department as company
        FROM home_matchingresult mr
        JOIN home_resume r ON mr.resume_id = r.id
        JOIN home_jobdescription jd ON mr.job_description_id = jd.id
        WHERE mr.id = ANY(%s)
        """
        
        cursor.execute(query, (candidate_ids,))
        candidates = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return candidates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

def create_selection_email(candidate_name: str, position: str, company: str, hr_user_id: int):
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
                    <a href="http://localhost:8000/interview/{hr_user_id}/" 
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
    """Send emails to selected candidates"""
    try:
        # Get candidate data
        candidates = get_candidate_data(request.candidate_ids)
        
        if not candidates:
            raise HTTPException(status_code=404, detail="No candidates found")
        
        success_count = 0
        failed_emails = []
        
        for candidate in candidates:
            candidate_name = candidate['candidate_name'] or "Candidate"
            position = candidate['position'] or "Position"
            company = candidate['company'] or "Our Company"
            email = candidate['email']
            matching_result_id = candidate['id']  # Get the matching result ID
            
            if not email:
                failed_emails.append(f"{candidate_name} (no email)")
                continue
            
            # Create email based on type
            if request.email_type == "selection":
                subject, body = create_selection_email(candidate_name, position, company, request.hr_user_id)
            elif request.email_type == "rejection":
                subject, body = create_rejection_email(candidate_name, position, company)
            else:
                raise HTTPException(status_code=400, detail="Invalid email type. Use 'selection' or 'rejection'")
            
            # Send email
            if send_email(email, subject, body):
                success_count += 1
                # Update email status in database
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE home_matchingresult 
                        SET email_status = %s
                        WHERE id = %s
                    """, (
                        'selection_sent' if request.email_type == 'selection' else 'rejection_sent',
                        matching_result_id
                    ))
                    conn.commit()
                    cursor.close()
                    conn.close()
                except Exception as db_error:
                    print(f"Warning: Failed to update email status for candidate {matching_result_id}: {db_error}")
            else:
                failed_emails.append(f"{candidate_name} ({email})")
        
        return {
            "success": True,
            "message": f"Successfully sent {success_count} emails",
            "sent_count": success_count,
            "failed_count": len(failed_emails),
            "failed_emails": failed_emails
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Email Service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)


