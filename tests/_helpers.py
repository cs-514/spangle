import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from datetime import datetime, timezone, timedelta

NOW = datetime(2026, 10, 15, 20, 0, tzinfo=timezone.utc)


def story(title, hours=1.0, source="Fox News", link=None, **kw):
    d = dict(title=title, link=link or "https://example.com/" + str(abs(hash(title))), desc="", author="",
             cats="", when=(NOW - timedelta(hours=hours)) if hours is not None else None,
             source=source, opinion=False, paywalled=False)
    d.update(kw)
    return d
