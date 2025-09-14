"""
ElevenLabs API Service for managing interviews and fetching conversation data
Unified service handling both session management and data fetching
"""
import requests
import json
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from .models import InterviewRecording, InterviewMessage, MatchingResult, InterviewSession

logger = logging.getLogger(__name__)

class ElevenLabsAPIService:
    """Unified service for ElevenLabs Conversational AI - handles sessions and data fetching"""
    
    BASE_URL = "https://api.elevenlabs.io/v1"
    
    def __init__(self, api_key=None):
        self.api_key = api_key or getattr(settings, 'ELEVENLABS_API_KEY', None)
        if not self.api_key:
            raise ValueError("ElevenLabs API key is required")
        
        self.headers = {
            "Accept": "application/json",
            "xi-api-key": self.api_key
        }
        
        # Agent ID for interview sessions
        self.agent_id = getattr(settings, 'ELEVENLABS_AGENT_ID', None)
    
    # ===========================================
    # SESSION MANAGEMENT METHODS
    # ===========================================
    
    def can_start_interview(self, matching_result_id=None):
        """Check if an interview can be started"""
        try:
            # Clean up old stuck sessions first
            self.cleanup_stuck_sessions()
            
            if matching_result_id:
                # Check if this specific matching result already has an active session
                active_session = InterviewSession.objects.filter(
                    matching_result_id=matching_result_id,
                    status__in=['ready', 'in_progress']
                ).first()
                return active_session is None
            else:
                # General check - allow if system is not overloaded
                active_sessions = InterviewSession.objects.filter(
                    status__in=['ready', 'in_progress']
                ).count()
                # Allow up to 5 concurrent sessions
                return active_sessions < 5
        except Exception as e:
            logger.error(f"Error checking interview availability: {str(e)}")
            return False
    
    def cleanup_stuck_sessions(self):
        """Clean up sessions that have been stuck in 'ready' state for too long"""
        try:
            # Mark sessions as timed out if they've been in 'ready' state for more than 30 minutes
            timeout_threshold = timezone.now() - timedelta(minutes=30)
            
            stuck_sessions = InterviewSession.objects.filter(
                status='ready',
                started_at__lt=timeout_threshold
            )
            
            count = 0
            if stuck_sessions.exists():
                count = stuck_sessions.count()
                stuck_sessions.update(
                    status='completed',
                    completion_reason='timeout',
                    ended_at=timezone.now()
                )
                logger.info(f"🧹 Cleaned up {count} stuck interview sessions")
                return f"Cleaned up {count} stuck sessions"
            else:
                logger.info("🧹 No stuck sessions found to clean up")
                return "No stuck sessions found"
                
        except Exception as e:
            logger.error(f"Error cleaning up stuck sessions: {str(e)}")
            return f"Error during cleanup: {str(e)}"
    
    def get_candidate_data(self, matching_result_id):
        """Fetch all interview data from database"""
        try:
            matching_result = MatchingResult.objects.select_related(
                'resume', 'job_description', 'interview_questions'
            ).get(id=matching_result_id)
            
            # Get interview questions
            interview_questions = matching_result.interview_questions
            if not interview_questions or not interview_questions.questions:
                raise ValueError("No interview questions found for this candidate")
            
            # Format questions for the agent
            questions_formatted = self.format_questions_for_agent(interview_questions.questions)
            
            # Get company name with better fallbacks
            company_name = "Our Company"  # Default fallback
            
            # Try to get company name from multiple sources
            if hasattr(matching_result.user, 'profile') and matching_result.user.profile:
                company_name = getattr(matching_result.user.profile, 'company_name', None)
                if not company_name or company_name.strip() == '':
                    company_name = "Our Company"
            
            # If still default, try job description department
            if company_name == "Our Company" and matching_result.job_description.department:
                company_name = matching_result.job_description.department
            
            candidate_data = {
                "matching_result_id": matching_result_id,
                "candidate_name": matching_result.resume.candidate_name or "Test Candidate",
                "candidate_email": matching_result.resume.email or "test@example.com",
                "position": matching_result.job_description.title or "Test Position",
                "company": company_name,
                "questions": questions_formatted,
                "session_id": f"interview_{matching_result_id}_{int(timezone.now().timestamp())}"
            }
            
            # Debug logging
            logger.info(f"Candidate data prepared: {candidate_data}")
            
            return candidate_data
            
        except MatchingResult.DoesNotExist:
            logger.error(f"Matching result {matching_result_id} not found")
            raise ValueError(f"Candidate with ID {matching_result_id} not found")
        except Exception as e:
            logger.error(f"Error fetching candidate data: {str(e)}")
            raise
    
    def format_questions_for_agent(self, questions_list):
        """Convert questions to agent-readable format"""
        if not questions_list:
            return "No questions available."
        
        formatted = []
        for i, question in enumerate(questions_list, 1):
            if isinstance(question, dict):
                question_text = question.get('question', 'No question text')
            else:
                question_text = str(question)
            formatted.append(f"{i}. {question_text}")
        
        return "\n".join(formatted)
    
    def create_interview_session(self, candidate_data):
        """Create local interview session record"""
        try:
            interview_session = InterviewSession.objects.create(
                matching_result_id=candidate_data["matching_result_id"],
                status='ready',
                total_questions_planned=len(candidate_data["questions"].split('\n')),
                started_at=timezone.now(),
                session_id=candidate_data["session_id"],
                conversation_transcript=[],
                elevenlabs_session_id=candidate_data["session_id"]
            )
            
            logger.info(f"📝 Interview session created: {interview_session.id}")
            return interview_session
            
        except Exception as e:
            logger.error(f"Error creating interview session: {str(e)}")
            raise
    
    def start_interview(self, matching_result_id):
        """Main method to start an interview"""
        try:
            # Check if interview can be started for this specific candidate
            if not self.can_start_interview(matching_result_id):
                # Try cleanup and check again
                self.cleanup_stuck_sessions()
                if not self.can_start_interview(matching_result_id):
                    return {
                        "status": "error",
                        "message": "An interview is already in progress for this candidate.",
                        "can_retry": True
                    }
            
            # Get candidate data
            candidate_data = self.get_candidate_data(matching_result_id)
            logger.info(f"🎤 Starting interview for {candidate_data['candidate_name']}")
            
            # Create local interview session
            interview_session = self.create_interview_session(candidate_data)
            
            return {
                "status": "success",
                "session_id": interview_session.id,
                "candidate_name": candidate_data["candidate_name"],
                "position": candidate_data["position"],
                "company": candidate_data["company"],
                "agent_id": self.agent_id,
                "elevenlabs_session_id": candidate_data["session_id"],
                "total_questions": len(candidate_data["questions"].split('\n')),
                "interview_questions": candidate_data["questions"]
            }
            
        except ValueError as ve:
            logger.error(f"Validation error starting interview: {str(ve)}")
            return {
                "status": "error", 
                "message": str(ve),
                "can_retry": False
            }
        except Exception as e:
            logger.error(f"Error starting interview: {str(e)}")
            return {
                "status": "error", 
                "message": f"Failed to start interview: {str(e)}",
                "can_retry": False
            }
    
    def complete_interview(self, session_id, completion_reason='completed', duration_seconds=0):
        """Complete interview session by session ID"""
        try:
            interview_session = InterviewSession.objects.get(id=session_id)
            
            interview_session.status = 'completed'
            interview_session.ended_at = timezone.now()
            interview_session.completion_reason = completion_reason
            interview_session.duration_seconds = duration_seconds
            interview_session.save()
            
            logger.info(f"✅ Interview session {session_id} completed with reason: {completion_reason}")
            return {
                "status": "success", 
                "message": f"Interview session {session_id} completed successfully"
            }
            
        except InterviewSession.DoesNotExist:
            logger.error(f"Interview session {session_id} not found")
            return {"status": "error", "message": "Interview session not found"}
        except Exception as e:
            logger.error(f"Error completing interview {session_id}: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    # ===========================================
    # DATA FETCHING METHODS (Original functionality)
    # ===========================================
    
    def get_conversation_details(self, conversation_id):
        """
        Fetch conversation details from ElevenLabs API
        
        Returns:
        {
            "conversation_id": "string",
            "agent_id": "string",
            "user_id": "string",
            "status": "string",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "started_at": "2024-01-01T00:00:00Z",
            "ended_at": "2024-01-01T00:00:00Z",
            "transcript": [
                {
                    "role": "user|assistant|system",
                    "content": "string",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "duration_ms": 1000
                }
            ],
            "metadata": {
                "duration_seconds": 180,
                "turn_count": 10
            }
        }
        """
        url = f"{self.BASE_URL}/convai/conversations/{conversation_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch conversation details for {conversation_id}: {e}")
            raise
    
    def get_conversation_audio(self, conversation_id):
        """
        Fetch conversation audio from ElevenLabs API
        
        Returns:
        Binary audio data (typically MP3)
        """
        url = f"{self.BASE_URL}/convai/conversations/{conversation_id}/audio"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch conversation audio for {conversation_id}: {e}")
            raise
    
    def create_interview_recording(self, conversation_id, matching_result_id=None):
        """
        Create InterviewRecording from ElevenLabs conversation
        
        Args:
            conversation_id (str): ElevenLabs conversation ID
            matching_result_id (int, optional): ID of related MatchingResult
        
        Returns:
            InterviewRecording: Created interview recording object
        """
        try:
            # Check if interview recording already exists
            existing_recording = InterviewRecording.objects.filter(
                conversation_id=conversation_id
            ).first()
            
            if existing_recording:
                logger.info(f"Interview recording already exists for conversation {conversation_id}")
                # If it's failed or processing, try to complete it
                if existing_recording.status in ['failed', 'processing']:
                    logger.info(f"Existing recording has status '{existing_recording.status}', attempting to complete it")
                    try:
                        # Try to fetch missing audio/transcript
                        self._complete_existing_recording(existing_recording, conversation_data)
                        return existing_recording
                    except Exception as e:
                        logger.error(f"Failed to complete existing recording: {e}")
                        # Return the existing record even if completion failed
                        return existing_recording
                else:
                    # Recording is already completed or pending
                    return existing_recording
            
            # Get matching result if provided
            matching_result = None
            if matching_result_id:
                try:
                    matching_result = MatchingResult.objects.get(id=matching_result_id)
                except MatchingResult.DoesNotExist:
                    logger.warning(f"MatchingResult {matching_result_id} not found")
            
            # Fetch conversation details
            logger.info(f"Fetching conversation details for {conversation_id}")
            conversation_data = self.get_conversation_details(conversation_id)
            
            # Debug: Log the structure of the conversation data
            logger.info(f"Conversation data keys: {list(conversation_data.keys()) if conversation_data else 'None'}")
            if conversation_data and 'transcript' in conversation_data:
                transcript = conversation_data['transcript']
                if transcript:
                    logger.info(f"First transcript message keys: {list(transcript[0].keys()) if transcript else 'Empty transcript'}")
                    logger.info(f"Sample message content: {transcript[0] if transcript else 'No messages'}")
            
            # Parse timestamps
            started_at = None
            ended_at = None
            duration_seconds = 0
            
            if conversation_data.get('started_at'):
                started_at = datetime.fromisoformat(
                    conversation_data['started_at'].replace('Z', '+00:00')
                )
            
            if conversation_data.get('ended_at'):
                ended_at = datetime.fromisoformat(
                    conversation_data['ended_at'].replace('Z', '+00:00')
                )
            
            if conversation_data.get('metadata', {}).get('duration_seconds'):
                duration_seconds = conversation_data['metadata']['duration_seconds']
            
            # Create InterviewRecording
            interview_recording = InterviewRecording.objects.create(
                conversation_id=conversation_id,
                matching_result=matching_result,
                status='processing',
                duration_seconds=duration_seconds,
                started_at=started_at,
                ended_at=ended_at,
                conversation_data=conversation_data
            )
            
            # Process transcript messages - filter out system messages with null content
            transcript = conversation_data.get('transcript', [])
            saved_messages = 0
            for idx, message in enumerate(transcript):
                # Skip system messages with null content (tool calls, tool results, etc.)
                if message.get('message') is None or message.get('message') == '':
                    logger.info(f"Skipping system message at index {idx}: role={message.get('role', 'unknown')}, has_tool_calls={bool(message.get('tool_calls'))}, has_tool_results={bool(message.get('tool_results'))}")
                    continue
                
                timestamp = timezone.now()
                if message.get('timestamp'):
                    try:
                        timestamp = datetime.fromisoformat(
                            message['timestamp'].replace('Z', '+00:00')
                        )
                    except:
                        # If timestamp parsing fails, use current time
                        pass
                
                # Ensure we have content before creating the message
                content = message.get('message', '').strip()
                if not content:
                    logger.warning(f"Empty content for message at index {idx}, skipping")
                    continue
                
                InterviewMessage.objects.create(
                    interview_recording=interview_recording,
                    speaker=message.get('role', 'user'),
                    message_content=content,
                    timestamp=timestamp,
                    sequence_number=saved_messages + 1,  # Use saved_messages count for sequence
                    duration_ms=message.get('duration_ms'),
                    raw_message_data=message
                )
                saved_messages += 1
            
            logger.info(f"Saved {saved_messages} actual conversation messages out of {len(transcript)} total transcript entries")
            
            # Fetch and save audio
            try:
                logger.info(f"Fetching audio for conversation {conversation_id}")
                audio_data = self.get_conversation_audio(conversation_id)
                
                # Save audio file
                audio_filename = f"interview_{conversation_id}.mp3"
                interview_recording.audio_file.save(
                    audio_filename,
                    ContentFile(audio_data),
                    save=False
                )
                
                logger.info(f"Audio saved for conversation {conversation_id}")
                
            except Exception as e:
                logger.error(f"Failed to fetch audio for {conversation_id}: {e}")
                # Continue without audio - we still have transcript
            
            # Generate transcript file
            try:
                transcript_content = self._generate_transcript_text(transcript)
                transcript_filename = f"interview_{conversation_id}_transcript.txt"
                interview_recording.transcript_file.save(
                    transcript_filename,
                    ContentFile(transcript_content.encode('utf-8')),
                    save=False
                )
                
                logger.info(f"Transcript file saved for conversation {conversation_id}")
                
            except Exception as e:
                logger.error(f"Failed to generate transcript file for {conversation_id}: {e}")
            
            # Update status to completed
            interview_recording.status = 'completed'
            interview_recording.save()
            
            logger.info(f"Successfully created interview recording for {conversation_id}")
            return interview_recording
            
        except Exception as e:
            logger.error(f"Failed to create interview recording for {conversation_id}: {e}")
            
            # Update status to failed if record was created
            if 'interview_recording' in locals():
                interview_recording.status = 'failed'
                interview_recording.save()
            
            raise
    
    def _complete_existing_recording(self, existing_recording, conversation_data=None):
        """Complete an existing interview recording that failed or is processing"""
        conversation_id = existing_recording.conversation_id
        
        # Fetch fresh conversation data if not provided
        if not conversation_data:
            logger.info(f"Fetching fresh conversation data for {conversation_id}")
            conversation_data = self.get_conversation_details(conversation_id)
        
        # Update the existing record with fresh data
        if conversation_data:
            existing_recording.conversation_data = conversation_data
            
            # Update metadata if available
            if conversation_data.get('metadata', {}).get('call_duration_secs'):
                existing_recording.duration_seconds = conversation_data['metadata']['call_duration_secs']
            
            # Update timestamps if available
            if conversation_data.get('metadata', {}).get('start_time_unix_secs'):
                try:
                    start_timestamp = datetime.fromtimestamp(
                        conversation_data['metadata']['start_time_unix_secs'],
                        tz=timezone.utc
                    )
                    existing_recording.started_at = start_timestamp
                    
                    # Calculate end time if we have duration
                    if existing_recording.duration_seconds:
                        existing_recording.ended_at = start_timestamp + timedelta(
                            seconds=existing_recording.duration_seconds
                        )
                except Exception as e:
                    logger.error(f"Error parsing timestamps: {e}")
            
            existing_recording.save()
        
        # Process messages if missing
        if not existing_recording.messages.exists() and conversation_data:
            transcript = conversation_data.get('transcript', [])
            saved_messages = 0
            for idx, message in enumerate(transcript):
                # Skip system messages with null content
                if message.get('message') is None or message.get('message') == '':
                    continue
                
                content = message.get('message', '').strip()
                if not content:
                    continue
                
                timestamp = timezone.now()
                if message.get('timestamp'):
                    try:
                        timestamp = datetime.fromisoformat(
                            message['timestamp'].replace('Z', '+00:00')
                        )
                    except:
                        pass
                
                InterviewMessage.objects.create(
                    interview_recording=existing_recording,
                    speaker=message.get('role', 'user'),
                    message_content=content,
                    timestamp=timestamp,
                    sequence_number=saved_messages + 1,
                    duration_ms=message.get('duration_ms'),
                    raw_message_data=message
                )
                saved_messages += 1
            
            logger.info(f"Added {saved_messages} messages to existing recording")
        
        # Try to fetch audio if missing
        if not existing_recording.audio_file:
            try:
                logger.info(f"Fetching missing audio for {conversation_id}")
                audio_data = self.get_conversation_audio(conversation_id)
                audio_filename = f"interview_{conversation_id}.mp3"
                existing_recording.audio_file.save(
                    audio_filename,
                    ContentFile(audio_data),
                    save=False
                )
                logger.info(f"Added missing audio file for {conversation_id}")
            except Exception as e:
                logger.error(f"Failed to fetch audio for existing recording: {e}")
        
        # Try to generate transcript file if missing
        if not existing_recording.transcript_file and conversation_data:
            try:
                transcript = conversation_data.get('transcript', [])
                transcript_content = self._generate_transcript_text(transcript)
                transcript_filename = f"interview_{conversation_id}_transcript.txt"
                existing_recording.transcript_file.save(
                    transcript_filename,
                    ContentFile(transcript_content.encode('utf-8')),
                    save=False
                )
                logger.info(f"Added missing transcript file for {conversation_id}")
            except Exception as e:
                logger.error(f"Failed to generate transcript file: {e}")
        
        # Update status if we have messages or conversation data
        if existing_recording.messages.exists() or conversation_data:
            existing_recording.status = 'completed'
            existing_recording.save()
            logger.info(f"Successfully completed existing recording for {conversation_id}")
        
        return existing_recording
    
    def _generate_transcript_text(self, transcript):
        """Generate a readable transcript text from conversation data"""
        transcript_lines = []
        transcript_lines.append("INTERVIEW TRANSCRIPT")
        transcript_lines.append("=" * 50)
        transcript_lines.append("")
        
        for message in transcript:
            # Skip system messages with null content
            content = message.get('message')
            if content is None or content.strip() == '':
                continue
                
            speaker = message.get('role', 'unknown').upper()
            timestamp = message.get('timestamp', '')
            
            if speaker == 'USER':
                speaker = 'CANDIDATE'
            elif speaker == 'ASSISTANT':
                speaker = 'INTERVIEWER'
            
            transcript_lines.append(f"[{timestamp}] {speaker}: {content}")
            transcript_lines.append("")
        
        return "\n".join(transcript_lines)
    
    def retry_failed_recordings(self):
        """Retry processing failed interview recordings"""
        failed_recordings = InterviewRecording.objects.filter(status='failed')
        
        for recording in failed_recordings:
            try:
                logger.info(f"Retrying failed recording: {recording.conversation_id}")
                
                # Try to fetch audio again if missing
                if not recording.audio_file:
                    try:
                        audio_data = self.get_conversation_audio(recording.conversation_id)
                        audio_filename = f"interview_{recording.conversation_id}.mp3"
                        recording.audio_file.save(
                            audio_filename,
                            ContentFile(audio_data),
                            save=False
                        )
                    except Exception as e:
                        logger.error(f"Failed to fetch audio on retry: {e}")
                
                # Try to generate transcript file if missing
                if not recording.transcript_file and recording.conversation_data:
                    try:
                        transcript = recording.conversation_data.get('transcript', [])
                        transcript_content = self._generate_transcript_text(transcript)
                        transcript_filename = f"interview_{recording.conversation_id}_transcript.txt"
                        recording.transcript_file.save(
                            transcript_filename,
                            ContentFile(transcript_content.encode('utf-8')),
                            save=False
                        )
                    except Exception as e:
                        logger.error(f"Failed to generate transcript on retry: {e}")
                
                # Update status if we have at least transcript data
                if recording.conversation_data and recording.messages.exists():
                    recording.status = 'completed'
                    recording.save()
                    logger.info(f"Successfully retried recording: {recording.conversation_id}")
                
            except Exception as e:
                logger.error(f"Retry failed for recording {recording.conversation_id}: {e}")
    
    def get_interview_summary(self, conversation_id):
        """Generate summary statistics for an interview"""
        try:
            recording = InterviewRecording.objects.get(conversation_id=conversation_id)
            
            messages = recording.messages.all()
            candidate_messages = messages.filter(speaker='user')
            interviewer_messages = messages.filter(speaker='assistant')
            
            summary = {
                'conversation_id': conversation_id,
                'candidate_name': recording.candidate_name,
                'job_title': recording.job_title,
                'duration_seconds': recording.duration_seconds,
                'total_messages': messages.count(),
                'candidate_messages': candidate_messages.count(),
                'interviewer_messages': interviewer_messages.count(),
                'status': recording.status,
                'started_at': recording.started_at,
                'ended_at': recording.ended_at,
                'has_audio': bool(recording.audio_file),
                'has_transcript': bool(recording.transcript_file),
            }
            
            return summary
            
        except InterviewRecording.DoesNotExist:
            logger.error(f"Interview recording not found for conversation {conversation_id}")
            return None


# Helper function for easy access
def fetch_interview_data(conversation_id, matching_result_id=None):
    """
    Convenience function to fetch interview data
    
    Args:
        conversation_id (str): ElevenLabs conversation ID
        matching_result_id (int, optional): Related MatchingResult ID
    
    Returns:
        InterviewRecording: Created or existing interview recording
    """
    try:
        service = ElevenLabsAPIService()
        return service.create_interview_recording(conversation_id, matching_result_id)
    except Exception as e:
        logger.error(f"Failed to fetch interview data: {e}")
        raise


def fix_failed_recordings():
    """
    Utility function to fix existing failed or processing interview recordings
    This can be run manually or as a management command
    """
    from .models import InterviewRecording
    
    service = ElevenLabsAPIService()
    
    # Get both failed and processing recordings (processing might be stuck)
    problematic_recordings = InterviewRecording.objects.filter(
        status__in=['failed', 'processing']
    )
    
    logger.info(f"Found {problematic_recordings.count()} problematic recordings to fix")
    
    fixed_count = 0
    for recording in problematic_recordings:
        try:
            logger.info(f"Attempting to fix recording: {recording.conversation_id} (status: {recording.status})")
            
            # Skip manual/fallback records
            if recording.conversation_id.startswith('manual_'):
                logger.info(f"Skipping manual record: {recording.conversation_id}")
                continue
            
            # Use the new _complete_existing_recording method
            completed_recording = service._complete_existing_recording(recording)
            
            if completed_recording.status == 'completed':
                fixed_count += 1
                logger.info(f"Successfully fixed recording: {recording.conversation_id}")
            else:
                logger.warning(f"Recording still not completed: {recording.conversation_id} (status: {completed_recording.status})")
                
        except Exception as e:
            logger.error(f"Failed to fix recording {recording.conversation_id}: {e}")
    
    logger.info(f"Fixed {fixed_count} out of {problematic_recordings.count()} problematic recordings")
    return fixed_count