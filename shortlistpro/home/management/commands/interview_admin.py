"""
Unified Interview Administration Command
Handles all ElevenLabs interview data operations in one place
"""
from django.core.management.base import BaseCommand, CommandError
from home.models import InterviewRecording, InterviewMessage, MatchingResult
from home.services_elevenlabs import ElevenLabsAPIService
import logging
import json

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Unified interview administration tool for ElevenLabs data management'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            required=True,
            choices=['list', 'retry-failed', 'retry-conversation', 'fix-transcripts', 'fetch-conversation', 'status'],
            help='Action to perform'
        )
        
        parser.add_argument(
            '--conversation-id',
            type=str,
            help='Specific conversation ID to work with'
        )
        
        parser.add_argument(
            '--matching-result-id',
            type=int,
            help='MatchingResult ID to associate with fetched data'
        )
        
        parser.add_argument(
            '--max-attempts',
            type=int,
            default=3,
            help='Maximum retry attempts (default: 3)'
        )
        
        parser.add_argument(
            '--all',
            action='store_true',
            help='Apply action to all applicable records'
        )

    def handle(self, *args, **options):
        action = options['action']
        
        try:
            if action == 'list':
                self.list_recordings()
            elif action == 'retry-failed':
                self.retry_failed_recordings(options.get('max_attempts', 3))
            elif action == 'retry-conversation':
                if not options.get('conversation_id'):
                    raise CommandError('--conversation-id is required for retry-conversation')
                self.retry_specific_conversation(
                    options['conversation_id'], 
                    options.get('max_attempts', 3)
                )
            elif action == 'fix-transcripts':
                self.fix_empty_transcripts()
            elif action == 'fetch-conversation':
                if not options.get('conversation_id'):
                    raise CommandError('--conversation-id is required for fetch-conversation')
                self.fetch_conversation_data(
                    options['conversation_id'],
                    options.get('matching_result_id')
                )
            elif action == 'status':
                self.show_status()
                
        except Exception as e:
            logger.error(f"Command failed: {e}")
            raise CommandError(f"Operation failed: {e}")

    def list_recordings(self):
        """List all interview recordings"""
        recordings = InterviewRecording.objects.all().order_by('-created_at')
        
        self.stdout.write(self.style.SUCCESS(f"\n📋 Found {recordings.count()} interview recordings:\n"))
        
        for recording in recordings:
            status_color = {
                'completed': self.style.SUCCESS,
                'processing': self.style.WARNING, 
                'failed': self.style.ERROR,
                'pending': self.style.NOTICE
            }.get(recording.status, self.style.NOTICE)
            
            has_audio = "✅ Audio" if recording.audio_file else "❌ No Audio"
            has_transcript = "✅ Transcript" if recording.transcript_file else "❌ No Transcript"
            message_count = recording.messages.count()
            
            self.stdout.write(
                f"  ID: {recording.id} | "
                f"{status_color(recording.status.upper())} | "
                f"{recording.candidate_name} | "
                f"Messages: {message_count} | "
                f"{has_audio} | {has_transcript} | "
                f"Conv: {recording.conversation_id[:20]}..."
            )

    def retry_failed_recordings(self, max_attempts):
        """Retry all failed interview recordings"""
        failed_recordings = InterviewRecording.objects.filter(
            status__in=['failed', 'processing', 'pending']
        )
        
        if not failed_recordings.exists():
            self.stdout.write(self.style.SUCCESS("✅ No failed recordings to retry!"))
            return
            
        self.stdout.write(
            self.style.WARNING(f"🔄 Retrying {failed_recordings.count()} failed recordings...")
        )
        
        success_count = 0
        for recording in failed_recordings:
            if self._retry_recording(recording, max_attempts):
                success_count += 1
                
        self.stdout.write(
            self.style.SUCCESS(f"✅ Successfully retried {success_count}/{failed_recordings.count()} recordings")
        )

    def retry_specific_conversation(self, conversation_id, max_attempts):
        """Retry a specific conversation"""
        try:
            recording = InterviewRecording.objects.get(conversation_id=conversation_id)
            if self._retry_recording(recording, max_attempts):
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Successfully retried conversation {conversation_id}")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ Failed to retry conversation {conversation_id}")
                )
        except InterviewRecording.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"❌ No recording found for conversation {conversation_id}")
            )

    def _retry_recording(self, recording, max_attempts):
        """Helper method to retry a single recording"""
        api_service = ElevenLabsAPIService()
        
        for attempt in range(max_attempts):
            try:
                self.stdout.write(f"  🔄 Attempt {attempt + 1}/{max_attempts} for {recording.conversation_id}")
                
                # Fetch conversation details
                conversation_data = api_service.get_conversation_details(recording.conversation_id)
                
                if conversation_data:
                    # Update recording with new data
                    recording.status = 'completed'
                    recording.conversation_data = conversation_data
                    recording.save()
                    
                    # Create/update messages if transcript exists
                    if 'transcript' in conversation_data:
                        self._process_transcript(recording, conversation_data['transcript'])
                    
                    # Try to fetch audio
                    try:
                        audio_data = api_service.get_conversation_audio(recording.conversation_id)
                        if audio_data:
                            from django.core.files.base import ContentFile
                            audio_filename = f"interview_{recording.conversation_id}.mp3"
                            recording.audio_file.save(audio_filename, ContentFile(audio_data), save=True)
                    except Exception as e:
                        logger.warning(f"Could not fetch audio for {recording.conversation_id}: {e}")
                    
                    return True
                    
            except Exception as e:
                logger.error(f"Retry attempt {attempt + 1} failed for {recording.conversation_id}: {e}")
                
        recording.status = 'failed'
        recording.save()
        return False

    def fix_empty_transcripts(self):
        """Fix empty message_content by extracting from raw_message_data"""
        empty_messages = InterviewMessage.objects.filter(
            message_content='',
            raw_message_data__isnull=False
        )
        
        if not empty_messages.exists():
            self.stdout.write(self.style.SUCCESS("✅ No empty transcripts to fix!"))
            return
            
        self.stdout.write(
            self.style.WARNING(f"🔧 Fixing {empty_messages.count()} empty transcript messages...")
        )
        
        updated_count = 0
        for message in empty_messages:
            try:
                raw_data = message.raw_message_data
                if isinstance(raw_data, dict) and 'message' in raw_data:
                    content = raw_data.get('message', '')
                    if content:
                        message.message_content = content
                        message.save(update_fields=['message_content'])
                        updated_count += 1
                        
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error processing message {message.id}: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Successfully fixed {updated_count} transcript messages')
        )

    def fetch_conversation_data(self, conversation_id, matching_result_id=None):
        """Manually fetch conversation data from ElevenLabs"""
        api_service = ElevenLabsAPIService()
        
        try:
            self.stdout.write(f"🔍 Fetching data for conversation: {conversation_id}")
            
            # Get conversation details
            conversation_data = api_service.get_conversation_details(conversation_id)
            if not conversation_data:
                raise CommandError("Could not fetch conversation data")
                
            # Find or create recording
            recording, created = InterviewRecording.objects.get_or_create(
                conversation_id=conversation_id,
                defaults={
                    'status': 'processing',
                    'conversation_data': conversation_data,
                    'candidate_name': 'Manual Fetch',
                    'job_title': 'Unknown Position'
                }
            )
            
            # Link to MatchingResult if provided
            if matching_result_id:
                try:
                    matching_result = MatchingResult.objects.get(id=matching_result_id)
                    recording.matching_result = matching_result
                    recording.candidate_name = matching_result.resume.candidate_name or 'Unknown'
                    recording.job_title = matching_result.job_description.title
                    recording.save()
                except MatchingResult.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"⚠️ MatchingResult {matching_result_id} not found"))
            
            # Process transcript
            if 'transcript' in conversation_data:
                self._process_transcript(recording, conversation_data['transcript'])
            
            # Fetch audio
            try:
                audio_data = api_service.get_conversation_audio(conversation_id)
                if audio_data:
                    from django.core.files.base import ContentFile
                    audio_filename = f"interview_{conversation_id}.mp3"
                    recording.audio_file.save(audio_filename, ContentFile(audio_data), save=True)
                    self.stdout.write("✅ Audio downloaded successfully")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠️ Could not fetch audio: {e}"))
            
            recording.status = 'completed'
            recording.save()
            
            self.stdout.write(
                self.style.SUCCESS(f"✅ Successfully fetched data for conversation {conversation_id}")
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Failed to fetch conversation data: {e}")
            )
            raise

    def _process_transcript(self, recording, transcript):
        """Process transcript messages"""
        # Clear existing messages
        recording.messages.all().delete()
        
        from django.utils import timezone
        for idx, message in enumerate(transcript):
            InterviewMessage.objects.create(
                interview_recording=recording,
                speaker=message.get('role', 'user'),
                message_content=message.get('message', ''),  # Use 'message' not 'content'
                timestamp=timezone.now(),
                sequence_number=idx + 1,
                duration_ms=message.get('duration_ms'),
                raw_message_data=message
            )

    def show_status(self):
        """Show overall system status"""
        total_recordings = InterviewRecording.objects.count()
        completed_recordings = InterviewRecording.objects.filter(status='completed').count()
        failed_recordings = InterviewRecording.objects.filter(status='failed').count()
        processing_recordings = InterviewRecording.objects.filter(status='processing').count()
        
        recordings_with_audio = InterviewRecording.objects.exclude(audio_file='').count()
        recordings_with_transcript = InterviewRecording.objects.exclude(transcript_file='').count()
        total_messages = InterviewMessage.objects.count()
        empty_messages = InterviewMessage.objects.filter(message_content='').count()
        
        self.stdout.write(self.style.SUCCESS("\n📊 INTERVIEW SYSTEM STATUS\n"))
        self.stdout.write(f"Total Recordings: {total_recordings}")
        self.stdout.write(f"  ✅ Completed: {completed_recordings}")
        self.stdout.write(f"  ❌ Failed: {failed_recordings}")
        self.stdout.write(f"  🔄 Processing: {processing_recordings}")
        self.stdout.write(f"")
        self.stdout.write(f"Files:")
        self.stdout.write(f"  🎵 With Audio: {recordings_with_audio}")
        self.stdout.write(f"  📝 With Transcript: {recordings_with_transcript}")
        self.stdout.write(f"")
        self.stdout.write(f"Messages:")
        self.stdout.write(f"  Total Messages: {total_messages}")
        self.stdout.write(f"  Empty Messages: {empty_messages}")
        
        if failed_recordings > 0:
            self.stdout.write(self.style.WARNING(f"\n⚠️ {failed_recordings} failed recordings need attention!"))
        if empty_messages > 0:
            self.stdout.write(self.style.WARNING(f"⚠️ {empty_messages} messages have empty content!"))
        
        if failed_recordings == 0 and empty_messages == 0:
            self.stdout.write(self.style.SUCCESS("\n🎉 All systems healthy!"))