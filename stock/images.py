"""Image helpers: shrink oversized uploads and build small thumbnails."""
import os
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

JPEG_QUALITY = 82


def _open(field_file):
	field_file.open('rb')
	field_file.seek(0)
	img = Image.open(field_file)
	img = ImageOps.exif_transpose(img)
	return img


def _encode(img):
	"""Return (bytes, extension). Keeps transparency as WebP, everything else as JPEG."""
	buf = BytesIO()
	has_alpha = img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info)
	if has_alpha:
		img = img.convert('RGBA')
		img.save(buf, format='WEBP', quality=JPEG_QUALITY, method=4)
		return buf.getvalue(), '.webp'
	img.convert('RGB').save(buf, format='JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True)
	return buf.getvalue(), '.jpg'


def optimise_image(field_file, max_size=1600):
	"""Resize a not-yet-saved upload in place so its longest side is <= max_size.

	Animated or unreadable images are left untouched.
	"""
	try:
		img = _open(field_file)
	except (UnidentifiedImageError, OSError, ValueError):
		return False
	if getattr(img, 'is_animated', False):
		return False
	if max(img.size) <= max_size and field_file.size < 600 * 1024:
		field_file.seek(0)
		return False
	img.thumbnail((max_size, max_size), Image.LANCZOS)
	data, ext = _encode(img)
	base = os.path.splitext(os.path.basename(field_file.name))[0]
	field_file.file = ContentFile(data, name=base + ext)
	field_file.name = base + ext
	field_file._committed = False
	return True


def make_thumbnail(source, target, size=600):
	"""Write a size x size-bounded copy of `source` into the `target` ImageField."""
	try:
		img = _open(source)
	except (UnidentifiedImageError, OSError, ValueError, FileNotFoundError):
		return False
	if getattr(img, 'is_animated', False):
		return False
	img.thumbnail((size, size), Image.LANCZOS)
	data, ext = _encode(img)
	base = os.path.splitext(os.path.basename(source.name))[0]
	if target:
		target.delete(save=False)
	target.save(f'{base}_thumb{ext}', ContentFile(data), save=False)
	return True
