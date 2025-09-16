import requests
import base64
import os
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()  # Load Zoom credentials from .env

class ZoomAPI:
    def __init__(self):
        self.account_id = os.getenv("ZOOM_ACCOUNT_ID")
        self.client_id = os.getenv("ZOOM_CLIENT_ID")
        self.client_secret = os.getenv("ZOOM_CLIENT_SECRET")
        self.access_token = None
        
        if not all([self.account_id, self.client_id, self.client_secret]):
            raise Exception("Missing Zoom API credentials in .env file")

    def get_access_token(self):
        """Fetch a new access token (valid for 1 hour)."""
        url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={self.account_id}"
        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()

        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        try:
            response = requests.post(url, headers=headers, timeout=30)
            if response.status_code != 200:
                raise Exception(f"Error getting Zoom token: {response.status_code} - {response.text}")

            token_data = response.json()
            self.access_token = token_data["access_token"]
            return self.access_token
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error getting Zoom token: {str(e)}")

    def ensure_token(self):
        """Always ensure a valid token is available."""
        if not self.access_token:
            return self.get_access_token()
        return self.access_token

    def create_meeting(self, candidate_name, interview_type, start_time, duration=30):
        """
        Create a Zoom meeting for interview.
        
        Args:
            candidate_name (str): Name of the candidate
            interview_type (str): Type of interview (technical, behavioral, final)
            start_time (str): ISO8601 format datetime string in UTC
            duration (int): Meeting duration in minutes (default: 30)
            
        Returns:
            dict: Meeting details including join_url, meeting_id, etc.
        """
        token = self.ensure_token()

        url = "https://api.zoom.us/v2/users/me/meetings"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Create meaningful topic and agenda
        topic = f"{interview_type.title()} Interview - {candidate_name}"
        agenda = f"{interview_type.title()} interview session with {candidate_name}"

        payload = {
            "topic": topic,
            "type": 2,  # Scheduled meeting
            "start_time": start_time,  # Must be in UTC ISO8601 format
            "duration": duration,
            "timezone": "UTC",
            "agenda": agenda,
            "settings": {
                "join_before_host": True,
                "waiting_room": False,
                "mute_upon_entry": True,
                "auto_recording": "cloud"  # Automatically record to cloud
            }
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code != 201:
                raise Exception(f"Error creating Zoom meeting: {response.status_code} - {response.text}")

            meeting_data = response.json()
            
            # Return essential meeting information
            return {
                "meeting_id": meeting_data["id"],
                "join_url": meeting_data["join_url"],
                "start_url": meeting_data["start_url"],
                "topic": meeting_data["topic"],
                "start_time": meeting_data["start_time"],
                "duration": meeting_data["duration"],
                "password": meeting_data.get("password", ""),
                "agenda": meeting_data.get("agenda", "")
            }
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error creating Zoom meeting: {str(e)}")

    def format_meeting_details(self, meeting_data, interview_date_formatted):
        """
        Format meeting details for email template.
        
        Args:
            meeting_data (dict): Meeting data from create_meeting()
            interview_date_formatted (str): Human-readable date/time string
            
        Returns:
            dict: Formatted meeting details for email template
        """
        return {
            "zoom_link": meeting_data["join_url"],
            "meeting_id": meeting_data["meeting_id"],
            "meeting_password": meeting_data["password"],
            "meeting_topic": meeting_data["topic"],
            "interview_date": interview_date_formatted,
            "meeting_duration": f"{meeting_data['duration']} minutes"
        }

# Test function for debugging
def test_zoom_integration():
    """Test function to verify Zoom API integration works."""
    try:
        zoom = ZoomAPI()
        print("✅ Zoom API initialized successfully")
        
        # Test token generation
        token = zoom.get_access_token()
        print("✅ Access token generated successfully")
        
        # Test meeting creation
        test_start_time = "2025-09-17T14:00:00Z"  # Sample time
        meeting = zoom.create_meeting(
            candidate_name="Test Candidate",
            interview_type="technical",
            start_time=test_start_time,
            duration=30
        )
        print("✅ Test meeting created successfully")
        print(f"Meeting URL: {meeting['join_url']}")
        
        return True
    except Exception as e:
        print(f"❌ Zoom integration test failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_zoom_integration()