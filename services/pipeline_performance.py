from time import perf_counter


class PipelinePerformance:

    def __init__(self):

        self._start = perf_counter()

    def finish(self):

        return {
            "execution_time_ms": round(
                (
                    perf_counter()
                    - self._start
                )
                * 1000,
                2,
            )
        }