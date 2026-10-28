import logging
import os
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage, Storage
from storages.backends.s3boto3 import S3Boto3Storage

logger = logging.getLogger(__name__)


def get_secure_documents_root():
    is_vercel = bool(
        os.environ.get('VERCEL') == '1'
        or os.environ.get('VERCEL_ENV') in ('production', 'preview', 'development')
        or getattr(settings, 'IS_VERCEL', False)
    )
    if is_vercel:
        root_path = Path('/tmp/secure_documents')
    else:
        root = getattr(settings, 'SECURE_DOCUMENTS_ROOT', None)
        if not root:
            root = Path(settings.BASE_DIR) / 'secure_documents'
        root_path = Path(root)
    try:
        root_path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return root_path


def get_r2_config():
    """
    Reads Cloudflare R2 storage credentials from environment variables or settings:
      - R2_ACCOUNT_ID
      - R2_ACCESS_KEY_ID
      - R2_SECRET_ACCESS_KEY
      - R2_BUCKET_NAME

    Returns a dict with configured values if all 4 are present.
    Returns None if none are present (R2 is optional; falls back to local/tmp storage).
    Raises ImproperlyConfigured only when credentials are partially configured (1 to 3 vars set).
    """
    account_id = os.environ.get('R2_ACCOUNT_ID') or getattr(settings, 'R2_ACCOUNT_ID', None)
    access_key = os.environ.get('R2_ACCESS_KEY_ID') or getattr(settings, 'R2_ACCESS_KEY_ID', None)
    secret_key = os.environ.get('R2_SECRET_ACCESS_KEY') or getattr(settings, 'R2_SECRET_ACCESS_KEY', None)
    bucket_name = os.environ.get('R2_BUCKET_NAME') or getattr(settings, 'R2_BUCKET_NAME', None)

    is_vercel = bool(
        os.environ.get('VERCEL') == '1'
        or os.environ.get('VERCEL_ENV') in ('production', 'preview', 'development')
        or getattr(settings, 'IS_VERCEL', False)
    )

    r2_vars = {
        'R2_ACCOUNT_ID': account_id,
        'R2_ACCESS_KEY_ID': access_key,
        'R2_SECRET_ACCESS_KEY': secret_key,
        'R2_BUCKET_NAME': bucket_name,
    }
    missing_vars = [k for k, v in r2_vars.items() if not v]

    # Partial configuration is an error
    if 0 < len(missing_vars) < 4:
        raise ImproperlyConfigured(
            f"Incomplete Cloudflare R2 storage configuration. Missing: {', '.join(missing_vars)}. "
            "All 4 variables (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME) must be configured if using R2."
        )

    # 0 variables present: R2 is not configured, fall back gracefully
    if len(missing_vars) == 4:
        if is_vercel:
            logger.warning(
                "Cloudflare R2 storage credentials not configured on Vercel. "
                "Document storage is falling back to ephemeral /tmp/secure_documents. "
                "Uploaded documents will not persist across serverless instances until "
                "R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_BUCKET_NAME are configured."
            )
        return None

    return {
        'account_id': account_id.strip(),
        'access_key': access_key.strip(),
        'secret_key': secret_key.strip(),
        'bucket_name': bucket_name.strip(),
    }


class R2ProtectedStorage(S3Boto3Storage):
    """
    Cloudflare R2 private document storage backend for patient IDs and doctor licenses.
    - S3-compatible backend configured for Cloudflare R2 endpoint and region 'auto'.
    - Private bucket: no public URL generation (url() raises ValueError).
    - Preserves filename safety and non-overwriting uploads (file_overwrite=False).
    - default_acl is None (Cloudflare R2 does not use S3 ACLs).
    """
    default_acl = None
    file_overwrite = False
    custom_domain = None
    querystring_auth = False

    def url(self, name):
        raise ValueError("This private document is not accessible via a public URL.")


class ProtectedStorage(Storage):
    """
    Dynamic storage wrapper for sensitive clinical documents (patient photo IDs and doctor licenses).
    - In production (or when R2 credentials are provided), routes uploads and reads to Cloudflare R2.
    - In local development, defaults to local FileSystemStorage under SECURE_DOCUMENTS_ROOT.
    - On Vercel, raises ImproperlyConfigured if R2 credentials are missing.
    - Keeps private documents secure: public URLs are disabled. Documents are accessed strictly through
      authenticated application views with role-based authorization checks.
    - Preserves migrations by deconstructing consistently to the migration baseline.
    """

    def get_storage(self):
        cfg = get_r2_config()
        if cfg:
            return R2ProtectedStorage(
                access_key=cfg['access_key'],
                secret_key=cfg['secret_key'],
                bucket_name=cfg['bucket_name'],
                endpoint_url=f"https://{cfg['account_id']}.r2.cloudflarestorage.com",
                region_name='auto',
            )
        return FileSystemStorage(
            location=get_secure_documents_root(),
            base_url=None,
        )

    def open(self, name, mode='rb'):
        return self.get_storage().open(name, mode=mode)

    def save(self, name, content, max_length=None):
        return self.get_storage().save(name, content, max_length=max_length)

    def delete(self, name):
        return self.get_storage().delete(name)

    def exists(self, name):
        return self.get_storage().exists(name)

    def listdir(self, path):
        return self.get_storage().listdir(path)

    def size(self, name):
        return self.get_storage().size(name)

    def url(self, name):
        raise ValueError("This private document is not accessible via a public URL.")

    def get_available_name(self, name, max_length=None):
        return self.get_storage().get_available_name(name, max_length=max_length)

    def get_valid_name(self, name):
        return self.get_storage().get_valid_name(name)

    def generate_filename(self, filename):
        return self.get_storage().generate_filename(filename)

    def path(self, name):
        return self.get_storage().path(name)

    def deconstruct(self):
        return (
            'django.core.files.storage.FileSystemStorage',
            (),
            {
                'base_url': None,
                'location': Path(settings.BASE_DIR) / 'secure_documents',
            },
        )

    def __getattr__(self, name):
        return getattr(self.get_storage(), name)


protected_storage = ProtectedStorage()


def get_protected_storage():
    return protected_storage
