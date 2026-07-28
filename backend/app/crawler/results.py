import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from app.crawler.adapters import CrawlerPlatformAdapter, RawResult
from app.models.crawler_platform import CrawlerResultItem, TaskMode
from app.models.library import (
    NormalizedComment,
    NormalizedContent,
    NormalizedCreator,
)


class CrawlerResultDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class TaskEntityBatch:
    contents: list[NormalizedContent]
    creators: list[NormalizedCreator]
    comments: list[NormalizedComment]
    actual_count: int
    legal_empty: bool = False


NormalizedT = TypeVar(
    "NormalizedT",
    NormalizedContent,
    NormalizedCreator,
    NormalizedComment,
)


def _iter_jsonl(paths: list[Path]) -> Iterator[RawResult]:
    for result_file in paths:
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
                yield raw


def _normalize_records(
    paths: list[Path],
    normalizer: Callable[[RawResult], NormalizedT],
    *,
    maximum: int,
) -> list[NormalizedT]:
    records: list[NormalizedT] = []
    for raw in _iter_jsonl(paths):
        try:
            record = normalizer(raw)
        except ValueError as error:
            raise CrawlerResultDataError(str(error)) from error
        records.append(record)
        if len(records) >= maximum:
            break
    return records


def iter_normalized_results(
    adapter: CrawlerPlatformAdapter,
    task_dir: Path,
) -> Iterator[CrawlerResultItem]:
    try:
        result_files = adapter.discover_content_files(task_dir)
    except ValueError as error:
        raise CrawlerResultDataError(str(error)) from error

    for raw in _iter_jsonl(result_files):
        try:
            yield adapter.normalize_result(raw)
        except ValueError as error:
            raise CrawlerResultDataError(str(error)) from error


def parse_task_entities(
    *,
    adapter: CrawlerPlatformAdapter,
    task_dir: Path,
    mode: TaskMode,
    requested_count: int,
    requested_comment_count: int,
    requested_sub_comment_count: int,
) -> TaskEntityBatch:
    try:
        content_files = adapter.discover_content_files(task_dir)
        creator_files = adapter.discover_creator_files(task_dir)
        comment_files = adapter.discover_comment_files(task_dir)
    except ValueError as error:
        raise CrawlerResultDataError(str(error)) from error

    contents = _normalize_records(
        content_files,
        adapter.normalize_content,
        maximum=max(requested_count, 1),
    )
    creators = _normalize_records(
        creator_files,
        adapter.normalize_creator,
        maximum=max(requested_count, 1),
    )
    comment_limit = (
        requested_sub_comment_count
        if mode == "sub_comments"
        else requested_comment_count
    )
    comments = _normalize_records(
        comment_files,
        adapter.normalize_comment,
        maximum=max(comment_limit, 1),
    )

    legal_empty = False
    if mode in {"search", "detail"}:
        actual_count = len(contents)
        if actual_count == 0:
            raise CrawlerResultDataError(
                f"{mode} task produced no normalized content"
            )
    elif mode == "creator":
        actual_count = len(creators)
        if actual_count == 0:
            raise CrawlerResultDataError(
                "creator task produced no normalized creator"
            )
    elif mode == "comments":
        actual_count = len(comments)
        legal_empty = bool(contents) and all(
            item.comment_count == 0 for item in contents
        )
        if actual_count == 0 and not legal_empty:
            raise CrawlerResultDataError(
                "comments task produced no comments and no verified empty result"
            )
    else:
        actual_count = len(comments)
        if actual_count == 0:
            raise CrawlerResultDataError(
                "sub_comments task produced no normalized replies"
            )

    return TaskEntityBatch(
        contents=contents,
        creators=creators,
        comments=comments,
        actual_count=actual_count,
        legal_empty=legal_empty,
    )


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
