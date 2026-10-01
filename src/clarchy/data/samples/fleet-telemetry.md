# Fleet telemetry platform

We track 8,000 delivery vans. Each van sends GPS and engine telemetry every 10 seconds (about 800 events per second in total) and we need real-time tracking on an operations dashboard.

- The platform team runs everything on Kubernetes and deploys with GitOps (Argo CD); event-driven workers should scale with KEDA based on queue length.
- Raw telemetry lands in a data lake; nightly jobs aggregate it for fuel and maintenance reports in our BI tool.
- Alerts (harsh braking, engine faults) are published as events so the maintenance system can subscribe.
- Roughly 5 TB of new data per month. Raw telemetry stays hot for 90 days and is then archived for 2 years for warranty claims.
- Region: Germany (Frankfurt). 99.9% availability. 10 developers on the platform team.
