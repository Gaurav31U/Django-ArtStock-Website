from django.core.management.base import BaseCommand

from stock.images import make_thumbnail
from stock.models import Art


class Command(BaseCommand):
    help = 'Create (or rebuild with --force) the small thumbnails used on gallery cards.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Rebuild thumbnails that already exist.')

    def handle(self, *args, **options):
        done = skipped = 0
        for art in Art.objects.all():
            if art.thumbnail and not options['force']:
                skipped += 1
                continue
            if make_thumbnail(art.image, art.thumbnail, size=600):
                art.save(update_fields=['thumbnail'])
                done += 1
                self.stdout.write(f'  thumbnail: {art.name}')
            else:
                self.stderr.write(f'  could not read image for: {art.name}')
        self.stdout.write(self.style.SUCCESS(f'{done} thumbnails created, {skipped} already present.'))
