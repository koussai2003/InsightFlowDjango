"""
Session utilities.

invalidate_all_sessions(user) — deletes every active Django session that
belongs to the given user. Used after sensitive account changes so the user
must sign in again on all devices.
"""
import logging

from django.contrib.sessions.models import Session
from django.utils import timezone

logger = logging.getLogger(__name__)


def invalidate_all_sessions(user):
    """
    Remove all active sessions for *user* from the session store.

    Strategy: iterate non-expired sessions and decode each one to check
    whether _auth_user_id matches. This is O(active sessions) but correct
    and avoids a custom mapping table. For large deployments, replace with a
    per-user session index table.
    """
    uid_str = str(user.pk)
    deleted = 0
    for session in Session.objects.filter(expire_date__gt=timezone.now()):
        try:
            data = session.get_decoded()
        except Exception:
            continue
        if data.get("_auth_user_id") == uid_str:
            session.delete()
            deleted += 1
    logger.info("Invalidated %d session(s) for user %s", deleted, user.pk)
