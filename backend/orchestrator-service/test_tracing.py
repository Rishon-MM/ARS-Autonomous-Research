import asyncio
import time
from observability.tracing import setup_tracing, get_tracer

async def main():
    setup_tracing()
    tracer = get_tracer()
    print("Tracer type:", type(tracer))
    with tracer.start_as_current_span("test_manual_span") as span:
        print("Span active!")
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
    print("Flushing...")
    time.sleep(2)
