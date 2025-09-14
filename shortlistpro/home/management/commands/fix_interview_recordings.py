"""
Management command to fix failed interview recordings
Usage: python manage.py fix_interview_recordings
"""
from django.core.management.base import BaseCommand
from home.services_elevenlabs import fix_failed_recordings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix failed interview recordings by attempting to re-fetch data from ElevenLabs API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )
        parser.add_argument(
            '--auto',
            action='store_true',
            help='Run in automatic mode (used by background processes)',
        )

    def handle(self, *args, **options):
        if options['auto']:
            # Automatic mode - less verbose, just log results
            try:
                fixed_count = fix_failed_recordings()
                if fixed_count > 0:
                    logger.info(f'Auto-fix: Successfully fixed {fixed_count} interview recordings')
                return
            except Exception as e:
                logger.error(f'Auto-fix error: {e}')
                return
        
        # Manual mode - more verbose output
        self.stdout.write('Starting interview recordings fix...')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
        
        try:
            if not options['dry_run']:
                fixed_count = fix_failed_recordings()
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully fixed {fixed_count} interview recordings')
                )
            else:
                from home.models import InterviewRecording
                failed_count = InterviewRecording.objects.filter(status='failed').count()
                processing_count = InterviewRecording.objects.filter(status='processing').count()
                self.stdout.write(
                    self.style.WARNING(f'Would attempt to fix {failed_count} failed and {processing_count} processing recordings')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error fixing interview recordings: {e}')
            )