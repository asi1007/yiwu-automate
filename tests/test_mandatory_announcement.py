import asyncio

import pytest


class _AnnouncementButtons:
    def __init__(self, page):
        self._page = page

    async def count(self):
        return self._page.pending

    @property
    def first(self):
        return self

    async def click(self):
        self._page.clicked += 1
        if self._page.closeable:
            self._page.pending -= 1


class _AnnouncementPage:
    def __init__(self, pending, closeable=True):
        self.pending = pending
        self.closeable = closeable
        self.clicked = 0
        self.selectors = []

    def locator(self, selector):
        self.selectors.append(selector)
        return _AnnouncementButtons(self)


def _dismiss(page):
    from yiwu_scraper import BuyerCentralScraper
    return asyncio.run(BuyerCentralScraper.dismiss_mandatory_announcements(page))


class TestDismissMandatoryAnnouncements:
    def test_必読お知らせが出ていれば既読にして閉じる(self):
        from yiwu_scraper import ANNOUNCEMENT_BUTTON_SELECTOR
        page = _AnnouncementPage(pending=1)
        assert _dismiss(page) == 1
        assert page.pending == 0
        assert page.selectors[0] == ANNOUNCEMENT_BUTTON_SELECTOR

    def test_お知らせが複数あれば全て閉じる(self):
        page = _AnnouncementPage(pending=3)
        assert _dismiss(page) == 3
        assert page.pending == 0

    def test_お知らせが無ければ何もクリックしない(self):
        page = _AnnouncementPage(pending=0)
        assert _dismiss(page) == 0
        assert page.clicked == 0

    def test_閉じられなくても無限ループしない(self):
        from yiwu_scraper import MAX_ANNOUNCEMENT_DISMISSALS
        page = _AnnouncementPage(pending=1, closeable=False)
        _dismiss(page)
        assert page.clicked == MAX_ANNOUNCEMENT_DISMISSALS
