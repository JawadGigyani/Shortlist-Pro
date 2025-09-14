"""
Automatic background task to fix failed interview recordings
This can be run as a cron job every few minutes to ensure all interviews are processed
Usage: python manage.py auto_fix_interviews
"""
from django.core.management.base import BaseCommand
from home.services_elevenlabs import fix_failed_recordings
import logging
import time
from datetime import datetime, timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Automatically fix failed interview recordings in the background'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=300,  # 5 minutes
            help='Interval in seconds between checks (default: 300)',
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run once and exit (for cron jobs)',
        )
        parser.add_argument(
            '--max-age',
            type=int,
            default=3600,  # 1 hour
            help='Maximum age of failed recordings to process (in seconds)',
        )

    def handle(self, *args, **options):
        interval = options['interval']
        run_once = options['once']
        max_age_seconds = options['max_age']
        
        logger.info(f"Starting automatic interview fix service")
        logger.info(f"Interval: {interval} seconds, Run once: {run_once}, Max age: {max_age_seconds} seconds")
        
        while True:
            try:
                # Only process recent failed recordings (avoid processing very old ones)
                cutoff_time = timezone.now() - timedelta(seconds=max_age_seconds)
                
                from home.models import InterviewRecording
                recent_failed = InterviewRecording.objects.filter(
                    status__in=['failed', 'processing'],
                    created_at__gte=cutoff_time
                ).count()
                
                if recent_failed > 0:
                    logger.info(f"Found {recent_failed} recent failed recordings, attempting fix...")
                    fixed_count = fix_failed_recordings()
                    
                    if fixed_count > 0:
                        logger.info(f"✅ Auto-fix completed: Fixed {fixed_count} interview recordings")
                    else:
                        logger.info("No recordings were fixed in this cycle")
                else:
                    logger.debug("No recent failed recordings found")
                
            except Exception as e:
                logger.error(f"Error in auto-fix cycle: {e}")
            
            if run_once:
                break
                
            time.sleep(interval)