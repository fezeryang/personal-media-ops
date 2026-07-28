from collections.abc import Iterable

from app.crawler.adapters import (
    BilibiliAdapter,
    CrawlerPlatformAdapter,
    DouyinAdapter,
    KuaishouAdapter,
    TiebaAdapter,
    WeiboAdapter,
    XiaohongshuAdapter,
    ZhihuAdapter,
)
from app.models.crawler_platform import CrawlerPlatformCapability


class UnsupportedPlatformError(ValueError):
    pass


class PlatformDisabledError(ValueError):
    pass


class CrawlerPlatformRegistry:
    def __init__(self, adapters: Iterable[CrawlerPlatformAdapter]) -> None:
        ordered = tuple(adapters)
        by_platform = {adapter.platform: adapter for adapter in ordered}
        if len(ordered) != len(by_platform):
            raise ValueError("crawler adapter platform keys must be unique")
        self._ordered = ordered
        self._by_platform = by_platform

    def get(self, platform: str) -> CrawlerPlatformAdapter:
        adapter = self._by_platform.get(platform)
        if adapter is None:
            raise UnsupportedPlatformError(f"unsupported crawler platform: {platform}")
        return adapter

    def require_enabled(
        self,
        platform: str,
        enabled_platforms: Iterable[str],
    ) -> CrawlerPlatformAdapter:
        adapter = self.get(platform)
        enabled = frozenset(enabled_platforms)
        self._validate_enabled(enabled)
        if platform not in enabled:
            raise PlatformDisabledError(f"crawler platform is not enabled: {platform}")
        return adapter

    def list_capabilities(
        self,
        enabled_platforms: Iterable[str],
    ) -> list[CrawlerPlatformCapability]:
        enabled = frozenset(enabled_platforms)
        self._validate_enabled(enabled)
        return [
            adapter.capability(adapter.platform in enabled) for adapter in self._ordered
        ]

    def _validate_enabled(self, enabled: frozenset[str]) -> None:
        unknown = sorted(enabled.difference(self._by_platform))
        if unknown:
            raise UnsupportedPlatformError(
                "MEDIAOPS_ENABLED_PLATFORMS contains unsupported values: "
                + ", ".join(unknown)
            )


platform_registry = CrawlerPlatformRegistry(
    (
        BilibiliAdapter(),
        XiaohongshuAdapter(),
        DouyinAdapter(),
        ZhihuAdapter(),
        WeiboAdapter(),
        TiebaAdapter(),
        KuaishouAdapter(),
    )
)
