import json
from collections.abc import Iterator
from pathlib import Path

from app.crawler.adapters import CrawlerPlatformAdapter
from app.models.crawler_platform import CrawlerResultItem


class CrawlerResultDataError(RuntimeError):
    pass


def iter_normalized_results(
    adapter: CrawlerPlatformAdapter,
    task_dir: Path,
) -> Iterator[CrawlerResultItem]:
    try:
        result_files = adapter.content_result_files(task_dir)
    except ValueError as error:
        raise CrawlerResultDataError(str(error)) from error

    for result_file in result_files:
        with result_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as error:
                    raise CrawlerResultDataError(
                        "Task result contains invalid JSONL"
                    ) from error
                if not isinstance(raw, dict):
                    raise CrawlerResultDataError(
                        "Task result record must be a JSON object"
                    )
                yield adapter.normalize_result(raw)


def count_normalized_results(
    adapter: CrawlerPlatformAdapter,
    task_dir: Path,
    maximum: int,
) -> int:
    count = 0
    for _ in iter_normalized_results(adapter, task_dir):
        count += 1
        if count >= maximum:
            break
    return count


def read_normalized_result_page(
    *,
    adapter: CrawlerPlatformAdapter,
    task_dir: Path,
    offset: int,
    limit: int,
    maximum: int,
) -> tuple[list[CrawlerResultItem], bool]:
    if offset >= maximum:
        return [], False

    records: list[CrawlerResultItem] = []
    for index, result in enumerate(iter_normalized_results(adapter, task_dir)):
        if index >= maximum:
            break
        if index < offset:
            continue
        records.append(result)
        if len(records) > limit:
            break
    return records[:limit], len(records) > limit
