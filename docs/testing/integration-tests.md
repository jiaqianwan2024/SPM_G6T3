# Integration tests

Each service keeps one workflow test in `services/<service>/tests/integration/test_workflow.py`. The test calls that service through its HTTP API and reads the rows back from SQL. Auth and calls to other services stay stubbed, so a failure means this service's route, service code, and database disagree.

The workflow files use a temporary SQLite file. Docker and MySQL can stay stopped for those.

`services/venue-service/tests/integration/test_double_booking_mysql.py` is the exception: it checks the real MySQL overlap triggers. Locally it is skipped when MySQL is down. GitHub Actions starts `infra/docker-compose.yml` and runs `python scripts/migrate.py --no-seed` before `npm run test:integration`, so that file runs on the `test` job.

## Run

From the repository root:

```bash
npm run test:integration
```

`.github/workflows/tests.yml` runs the same command after the unit tests, on pushes to `dev` and `main` and on pull requests into either branch. The job id is `test`. Playwright runs in the separate `e2e` job.

From one service directory:

```bash
cd services/event-service
python -m unittest discover -s tests/integration -p "test_*.py" -t .
```

Use `user-service`, `venue-service`, `equipment-service`, `registration-service`, or `notification-service` the same way.

## Files

| Service | What the workflow checks |
|---|---|
| user-service | An unknown token is refused. A linked account returns its role, and the directory lists that account. |
| event-service | A draft is saved with requirements, a full event is submitted, the Event Coordinator Lead assigns it to a coordinator (SPM-117), that coordinator adds a readiness line, and the submitted event stays off the open-registration list. |
| venue-service | A venue is created and listed. An event with no booking returns an empty public summary. A booking workflow (SPM-61 to SPM-64, SPM-112, SPM-122): a free venue is found and suits an event; requests are stored pending with the event's facts and the venue's occupied window (start minus setup to end plus turnaround); once one is approved, a request whose event times only touch it is refused and one whose window only touches it is approved; a withdrawn request is stored as withdrawn; and after a longer turnaround the two approved bookings are listed as a clash and both stay approved. A hold workflow (SPM-116): a held request stops another event's overlapping request being approved and keeps the venue out of search; once its expiry passes, the other request is approved and the held one is still only pending; and rejecting a held request stores the hold as ended by the rejection. An approval workflow (SPM-8): the pending queue lists requests oldest first with their facts; a maintenance block (recorded through SPM-9) inside the turnaround refuses approval and leaves the row pending with no approver; once the block is removed the approval stores the approver's id, name and time; the approved booking then cannot be approved or rejected again, and an overlapping request is refused and stays pending. A rejection workflow (SPM-10): a blank reason is refused and the request stays pending; a held request is rejected with a reason and a suggested venue, which are stored with who and when; its hold is recorded as ended by the rejection; it leaves the pending queue and cannot then be approved; and an overlapping request that the hold had blocked is approved. |
| equipment-service | A reservation above the stock is refused. A reservation, a shortfall, an adjustment, and a release are stored and appear on the activity log. |
| registration-service | The registration count for an event with no rows is zero, and the caller's list is empty. |
| notification-service | A notification record is stored and listed for the signed-in user. |

`tests/integration/test_workflows.py` runs those six files. It does not call the services over the network.
