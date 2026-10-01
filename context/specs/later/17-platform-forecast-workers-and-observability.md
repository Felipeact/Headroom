# Spec 17: Forecast workers, message queue, and observability

> **Backlog draft.** This was written before the specs were restructured for parallel work, so its spec numbers and "Depends on" line use the old numbering. Before building it, split it into short specs in the current format (see [README.md](README.md)).

- **Phase:** 3 (launch and grow)
- **Status:** Not started
- **Area:** Platform
- **Depends on:** 05, and passing the Phase 2 gate in `Roadmap.md`

## Goal

Move forecasting into separate background workers, so heavy nightly calculations can't slow down the app. Make it possible to follow every request and event through the system from start to finish.

## When to start

Start this spec once the Phase 2 gate has passed, and only if forecasting visibly slows down API responses. If it doesn't, postpone this spec.

## Requirements

1. **Message queue.** Replace the in-process event bus with a hosted RabbitMQ service, such as CloudAMQP or Amazon MQ. Keep every event's name and contents exactly the same.
2. **Workers.** Forecast workers run from the same image as the API, started with a different command (`python -m app.worker`), as shown in `docker-compose.yml`. The number of workers scales separately from the API.
3. **Delivery guarantees:**
   - The queue may deliver a message more than once. Every consumer must be idempotent, meaning that processing a message twice has the same effect as processing it once.
   - A message that fails 5 times moves to a dead-letter queue, and the team is alerted.
4. **No lost events.** Write each event to an outbox table in the same database transaction as the data change, and publish it to the queue from there. If the app crashes between saving the data and publishing the event, the event is still published later.
5. **Cache.** Redis caches the latest forecast and the dashboard response. The cache for a business is cleared whenever a `forecast.updated` event arrives for it.
6. **Tracing and monitoring:**
   - OpenTelemetry traces every HTTP request and every event. The trace ID travels in each message's headers.
   - Dashboards show API response times, queue length, how long syncs take, and how long forecasts take.
   - Every log line includes the trace ID.
7. **Hosting.** Everything still runs on Cloud Run or ECS Fargate. There is no Kubernetes yet.

## Acceptance criteria

- [ ] If a worker is stopped partway through a forecast, the message is delivered again and the forecast is saved exactly once (tested).
- [ ] A message that always fails ends up in the dead-letter queue, and the team is alerted.
- [ ] A single trace follows one nightly sync through the forecast and the alert, all the way to the email.
- [ ] During the nightly run, the 95th-percentile API response time stays within 20% of its daytime level.
- [ ] Contract tests confirm that no event name or payload shape changed.
