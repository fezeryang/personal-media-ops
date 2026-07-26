from concurrent.futures import ThreadPoolExecutor

from app.repositories.crawler_tasks import CrawlerTaskRepository


def seed_task(repository: CrawlerTaskRepository, keywords: str) -> dict[str, object]:
    return repository.create(
        platform="bili",
        crawler_type="search",
        keywords=keywords,
        login_type="qrcode",
        requested_count=1,
        output_dir=f"/output/{keywords}",
        log_path=f"/logs/{keywords}.log",
        qrcode_path=f"/qrcodes/{keywords}.png",
    )


def test_only_one_pending_task_can_be_claimed(
    repository: CrawlerTaskRepository,
) -> None:
    first = seed_task(repository, "first")
    seed_task(repository, "second")

    claimed = repository.claim_next()
    blocked = repository.claim_next()

    assert claimed is not None
    assert claimed["id"] == first["id"]
    assert claimed["status"] == "running"
    assert blocked is None


def test_interrupted_active_tasks_are_failed(
    repository: CrawlerTaskRepository,
) -> None:
    task = seed_task(repository, "stale")
    repository.claim_next()

    recovered = repository.fail_interrupted_tasks()

    assert recovered == 1
    stored = repository.get(str(task["id"]))
    assert stored is not None
    assert stored["status"] == "failed"
    assert stored["finished_at"] is not None
    assert "interrupted" in str(stored["error_message"]).lower()


def test_concurrent_claimers_cannot_start_two_tasks(
    repository: CrawlerTaskRepository,
) -> None:
    seed_task(repository, "first")
    seed_task(repository, "second")

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed = list(executor.map(lambda _: repository.claim_next(), range(2)))

    assert sum(task is not None for task in claimed) == 1
    assert len([task for task in repository.list() if task["status"] == "running"]) == 1
