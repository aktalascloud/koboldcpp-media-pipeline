# Honor the Native readiness deadline

The portable launcher waits for the configured Native readiness period plus the same grace period as the supervisor. A monotonic timer prevents an early startup error while weights are still loading.
