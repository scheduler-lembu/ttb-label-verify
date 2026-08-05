"""Extraction package — "AI reads" half of "AI reads, code judges".

Single responsibility: mark ``app.extraction`` as a package. Everything here
ONLY transcribes a label image into structured fields; nothing here makes a
compliance judgment. All concrete extractors implement the ``Extractor``
interface in ``base.py`` and are selected/chained by ``router.py``.

No business logic in this scaffold pass.
"""
