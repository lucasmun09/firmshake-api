import os

import firebase_admin
from firebase_admin import credentials, firestore

from config import FIREBASE_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS

_db = None


def get_db():
    global _db
    if _db is not None:
        return _db

    if not firebase_admin._apps:
        if GOOGLE_APPLICATION_CREDENTIALS and os.path.isfile(
            GOOGLE_APPLICATION_CREDENTIALS
        ):
            cred = credentials.Certificate(GOOGLE_APPLICATION_CREDENTIALS)
            firebase_admin.initialize_app(cred, {"projectId": FIREBASE_PROJECT_ID})
        else:
            # Cloud Run: Application Default Credentials from the service account.
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {"projectId": FIREBASE_PROJECT_ID})

    _db = firestore.client()
    return _db
