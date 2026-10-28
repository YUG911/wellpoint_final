import os
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError
import pypdf  # strict PDF structure validation

ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
MAX_DOCUMENT_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_document_file(uploaded_file):
    """
    Validates uploaded document files (patient photo ID and doctor medical license).

    Rules:
    - Allowed formats: JPG, JPEG, PNG, and PDF
    - Maximum file size: 5 MB
    - Rejects empty files (0 bytes)
    - Rejects unsupported extensions
    - For images: opens and verifies the entire image with Pillow, ensures the
      detected image format matches the declared extension, and rejects corrupted or
      mismatched files.
    - For PDFs: parses the document using pypdf with strict parsing, ensuring the
      document structure and pages are valid and readable.
    - Upload stream is guaranteed to be reset to position 0 after validation so
      Django can save the file correctly.
    """
    if not uploaded_file:
        return uploaded_file

    try:
        file_size = getattr(uploaded_file, 'size', None)
        if file_size is None:
            uploaded_file.seek(0, os.SEEK_END)
            file_size = uploaded_file.tell()
            uploaded_file.seek(0)

        if file_size > MAX_DOCUMENT_SIZE:
            raise ValidationError("File exceeds the 5MB size limit. Maximum allowed size is 5 MB.")

        if file_size == 0:
            raise ValidationError("The uploaded file is empty.")

        name = (getattr(uploaded_file, 'name', '') or '').strip()
        ext = os.path.splitext(name)[1].lower()

        if not ext or ext not in ALLOWED_DOCUMENT_EXTENSIONS:
            raise ValidationError(f"Unsupported file format '{ext}'. Allowed formats: JPG, JPEG, PNG, and PDF.")

        # Read header for initial magic byte inspection
        header = uploaded_file.read(1024)
        uploaded_file.seek(0)

        if not header:
            raise ValidationError("The uploaded file is empty.")

        if ext == '.pdf':
            # Check magic bytes first
            if not (header.startswith(b'%PDF-') or header.lstrip().startswith(b'%PDF-')):
                raise ValidationError("Invalid PDF file content. The uploaded file is not a valid PDF document.")

            # Validate complete PDF content with pypdf
            try:
                reader = pypdf.PdfReader(uploaded_file, strict=True)
                if len(reader.pages) == 0:
                    raise ValidationError("Invalid or empty PDF document. The PDF contains no readable pages.")
            except (pypdf.errors.PdfReadError, pypdf.errors.PdfStreamError, pypdf.errors.EmptyFileError) as e:
                raise ValidationError(f"Invalid or corrupted PDF document: {e}")
            except Exception:
                raise ValidationError("Invalid or corrupted PDF document. Could not parse document content.")

        elif ext in ('.jpg', '.jpeg', '.png'):
            # Check magic bytes first
            if ext == '.png' and not header.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValidationError("Invalid PNG image content. The uploaded file is not a valid PNG image.")
            elif ext in ('.jpg', '.jpeg') and not header.startswith(b'\xff\xd8\xff'):
                raise ValidationError("Invalid JPEG image content. The uploaded file is not a valid JPEG image.")

            # Validate complete image content with Pillow
            try:
                img = Image.open(uploaded_file)
                img.verify()
                img_format = (img.format or '').upper()

                # Ensure image format matches extension
                if ext == '.png' and img_format != 'PNG':
                    raise ValidationError(f"Image format mismatch: file has '{ext}' extension but contains {img_format} data.")
                elif ext in ('.jpg', '.jpeg') and img_format != 'JPEG':
                    raise ValidationError(f"Image format mismatch: file has '{ext}' extension but contains {img_format} data.")
            except (UnidentifiedImageError, OSError, SyntaxError) as e:
                raise ValidationError("Invalid or corrupted image content. The file could not be decoded.")
            except ValidationError:
                raise
            except Exception:
                raise ValidationError("Invalid or corrupted image file.")

        return uploaded_file

    finally:
        # Guarantee upload stream is always reset to position 0
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
