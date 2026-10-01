# Spec 22: Service split and Kubernetes

> **Backlog draft.** This was written before the specs were restructured for parallel work, so its spec numbers and "Depends on" line use the old numbering. Before building it, split it into short specs in the current format (see [README.md](README.md)).

- **Phase:** 4 (scale)
- **Status:** Not started
- **Area:** Platform
- **Depends on:** [17](17-platform-forecast-workers-and-observability.md)

## Goal

Split the application into independent services and run them on Kubernetes, once the business has grown enough to justify it.

## When to start

Start only when at least one of these is true:

- Several parts of the app need to scale in different ways.
- Several engineers are deploying independently.
- Compliance rules require network isolation between components.

If none of these is true, postpone this spec.

## Requirements

1. **Split order.** Split out bank sync first, then notifications, then alerts. Forecasting was already separated in [spec 17](17-platform-forecast-workers-and-observability.md). Billing and accounts can stay together in `core`.
2. **What each new service gets:**
   - its own database, or at least its own database schema and credentials
   - its own Dockerfile
   - its own deployment pipeline
3. **Platform.** Use a managed Kubernetes service. The default choice is GKE Autopilot.
4. **Starting configuration.** Begin from the files in `k8s/`, which set up:
   - Deployments and Services for long-running processes
   - autoscaling for workers, with the HorizontalPodAutoscaler or with KEDA based on queue length
   - a CronJob for the nightly sync
   - Gateway API for routing traffic. Don't use ingress-nginx, which is no longer maintained.
   - NetworkPolicies to limit traffic between services. They only take effect if the cluster's network plugin supports them.
   - External Secrets Operator for credentials
   - Argo CD for deployments
5. **Migration without downtime.** Run the old and new setups side by side, move traffic over gradually, and keep a fast way to roll back.
6. **Cluster hygiene:**
   - separate namespaces for staging and production
   - resource requests and limits on every workload
   - containers that don't run as root, with read-only file systems
7. **Cost tracking.** Compare monthly cluster costs with the previous platform's costs.

## Acceptance criteria

- [ ] Each extracted service can be deployed without deploying the others.
- [ ] A NetworkPolicy blocks a test pod from reaching the forecast API.
- [ ] Workers scale up for the nightly load and scale back down afterwards.
- [ ] The migration causes no downtime that customers notice, and no events are lost.
- [ ] Monthly infrastructure costs are tracked against the budget in `project-overview.md`.
