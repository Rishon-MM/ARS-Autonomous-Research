"""
graph/engine.py — Graph Execution Engine.

The heart of the orchestrator.  Replaces the sequential generate()
function with a DAG-based execution model supporting:
- Dependency-driven scheduling
- Parallel execution of independent nodes
- Checkpointing after every node
- Retry with exponential backoff
- Dead-letter queue for permanent failures
- SSE event streaming to the frontend
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import random
import traceback
from datetime import datetime, timedelta
from typing import AsyncGenerator

from .node import GraphNode
from .execution_graph import ExecutionGraph
from models.task_state import TaskState, TaskStatus, NodeStatus
from models.execution import ExecutionEvent, EventType, ErrorEvent
from state.state_manager import StateManager
from tools.registry import ToolRegistry
from workers.base import WorkerResult
from workers.planner import PlannerWorker
from workers.researcher import ResearcherWorker
from workers.verification import VerificationWorker
from workers.outliner import OutlinerWorker
from workers.section_writer import SectionWriterWorker
from workers.editor import EditorWorker
from workers.reflection import ReflectionWorker

log = logging.getLogger("ars.graph.engine")


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _sse_done() -> str:
    return "data: [DONE]\n\n"


class GraphEngine:
    """
    Execute a research task as a directed acyclic graph of worker nodes.

    The engine:
    1. Builds the initial DAG (planner → research → verify → write → reflect)
    2. After the planner runs, dynamically inserts parallel research nodes
    3. Executes nodes in dependency order, parallelizing where possible
    4. Checkpoints state after every node
    5. Retries failed nodes up to the configured limit
    6. Streams SSE events throughout execution
    """

    def __init__(
        self,
        state_manager: StateManager,
        tool_registry: ToolRegistry,
        max_parallel: int = 3,
        checkpoint_enabled: bool = True,
    ):
        self.state_manager = state_manager
        self.tools = tool_registry
        self.max_parallel = max_parallel
        self.checkpoint_enabled = checkpoint_enabled

    # ── Public API ────────────────────────────────────────────────

    async def execute(self, task_id: str) -> AsyncGenerator[str, None]:
        """
        Run the full graph for a task, yielding SSE events.

        This is the main entrypoint called by the API endpoint.
        """
        state = await self.state_manager.load_task(task_id)
        state.mark_started()
        await self.state_manager.save_task(state)

        yield _sse({
            "type": "task_started",
            "task_id": state.task_id,
            "query": state.query,
        })

        try:
            # Phase 1: Build initial graph and run planner
            graph = self._build_initial_graph()
            completed: set[str] = set()

            # Execute the planner first (it produces sub-tasks)
            planner_node = graph.get_node("planner")
            async for event in self._execute_node(planner_node, state):
                yield event

            if planner_node.status == NodeStatus.COMPLETED:
                completed.add("planner")
                state = await self.state_manager.load_task(task_id)

                # Phase 2: Dynamically add research nodes based on planner output
                self._add_research_nodes(graph, state)

                # Phase 3: Execute remaining graph
                async for event in self._execute_remaining(graph, state, completed):
                    yield event

                # Reload final state
                state = await self.state_manager.load_task(task_id)
            else:
                state.mark_failed("Planner failed")
                await self.state_manager.save_task(state)

            # Phase 4: Final completion event
            state.mark_completed()
            await self.state_manager.save_task(state)

            yield _sse({
                "type": "agent_completion",
                "report": state.final_report,
                "title": state.report_title,
                "sources": [
                    {
                        "title": c.title,
                        "url": c.url,
                        "source_type": "paper",
                        "key_points": [],
                        "citation": c.apa_text,
                    }
                    for c in state.citations
                ],
                "metrics": state.metrics.model_dump(mode="json") if state.metrics else {},
                "reflection": state.reflection.model_dump(mode="json") if state.reflection else {},
            })

        except Exception as e:
            log.exception("Task execution failed: %s", e)
            state.mark_failed(str(e))
            await self.state_manager.save_task(state)
            yield _sse({"type": "error", "error": str(e)})

        yield _sse_done()

    # ── Graph Construction ────────────────────────────────────────

    def _build_initial_graph(self) -> ExecutionGraph:
        """Build the initial DAG with placeholder research nodes."""
        graph = ExecutionGraph()

        # Planner → runs first, no dependencies
        graph.add_node(GraphNode(
            node_id="planner",
            worker=PlannerWorker(),
        ))

        # Verification → depends on research nodes (added dynamically)
        graph.add_node(GraphNode(
            node_id="verification",
            worker=VerificationWorker(),
            dependencies=[],  # filled after research nodes are added
        ))

        # Outliner → depends on verification
        graph.add_node(GraphNode(
            node_id="outliner",
            worker=OutlinerWorker(),
            dependencies=["verification"],
            timeout=timedelta(minutes=5),
        ))

        return graph

    def _add_research_nodes(
        self, graph: ExecutionGraph, state: TaskState
    ) -> None:
        """
        Dynamically add parallel research nodes based on planner output.

        Each sub-task from the plan gets its own research node.
        All research nodes depend on 'planner' and feed into 'verification'.
        """
        sub_tasks = []
        if state.plan and state.plan.sub_tasks:
            sub_tasks = state.plan.sub_tasks
        else:
            # Fallback: use the main query as a single sub-task
            sub_tasks = [state.query]

        verification_node = graph.get_node("verification")

        for i, sub_task in enumerate(sub_tasks):
            node_id = f"research_{i}"
            graph.add_node(GraphNode(
                node_id=node_id,
                worker=ResearcherWorker(sub_task=sub_task, sub_task_index=i),
                dependencies=["planner"],
            ))
            verification_node.dependencies.append(node_id)

        log.info(
            "Added %d research nodes: %s",
            len(sub_tasks),
            [f"research_{i}" for i in range(len(sub_tasks))],
        )

    def _add_section_nodes(
        self, graph: ExecutionGraph, state: TaskState
    ) -> None:
        """Dynamically add parallel section writer nodes based on outline."""
        sections = []
        if state.report_outline and state.report_outline.sections:
            sections = state.report_outline.sections

        section_node_ids = []
        for i, sec in enumerate(sections):
            node_id = f"section_writer_{i}"
            section_node_ids.append(node_id)
            graph.add_node(GraphNode(
                node_id=node_id,
                worker=SectionWriterWorker(section_name=sec.section_name, section_index=i, total_sections=len(sections)),
                dependencies=["outliner"],
                timeout=timedelta(minutes=10),
            ))

        # Add Editor depending on all section writers
        graph.add_node(GraphNode(
            node_id="editor",
            worker=EditorWorker(),
            dependencies=section_node_ids if section_node_ids else ["outliner"],
            timeout=timedelta(minutes=10),
        ))

        # Add Reflection depending on editor
        graph.add_node(GraphNode(
            node_id="reflection",
            worker=ReflectionWorker(),
            dependencies=["editor"],
        ))

        log.info("Added %d section writer nodes + editor + reflection", len(section_node_ids))

    # ── Execution Loop ────────────────────────────────────────────

    async def _execute_remaining(
        self,
        graph: ExecutionGraph,
        state: TaskState,
        completed: set[str],
    ) -> AsyncGenerator[str, None]:
        """Execute all remaining nodes in dependency order."""

        while True:
            ready = graph.get_ready_nodes(completed)
            if not ready:
                # Check if all nodes are done
                all_done = all(
                    n.status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED)
                    for n in graph.nodes.values()
                )
                if all_done:
                    break

                # Check for stuck state (all pending but none ready = cycle)
                pending = [
                    n for n in graph.nodes.values()
                    if n.status == NodeStatus.PENDING
                ]
                if pending:
                    failed = [
                        n for n in graph.nodes.values()
                        if n.status == NodeStatus.FAILED
                    ]
                    if failed:
                        log.error("Nodes failed, blocking progress: %s", [n.node_id for n in failed])
                        break
                    else:
                        raise RuntimeError(f"Deadlock: {len(pending)} pending nodes, none ready")
                break

            # Execute ready nodes in parallel (up to max_parallel)
            batch = ready[:self.max_parallel]

            if len(batch) == 1:
                # Single node — execute directly
                node = batch[0]
                state = await self.state_manager.load_task(state.task_id)
                async for event in self._execute_node(node, state):
                    yield event
                if node.status == NodeStatus.COMPLETED:
                    completed.add(node.node_id)
                    if node.node_id == "outliner":
                        state = await self.state_manager.load_task(state.task_id)
                        self._add_section_nodes(graph, state)
            else:
                # Multiple nodes — execute in parallel
                async for msg_type, payload in self._execute_parallel(batch, state.task_id):
                    if msg_type == "event":
                        yield payload
                    elif msg_type == "done":
                        if payload.status == NodeStatus.COMPLETED:
                            completed.add(payload.node_id)
                            if payload.node_id == "outliner":
                                state = await self.state_manager.load_task(state.task_id)
                                self._add_section_nodes(graph, state)

    async def _execute_node(
        self, node: GraphNode, state: TaskState
    ) -> AsyncGenerator[str, None]:
        """
        Execute a single node with retry support.

        Yields SSE events as the worker produces them.
        """
        node.mark_running()
        state.node_statuses[node.node_id] = NodeStatus.RUNNING.value
        start_time = time.monotonic()
        started_at = datetime.utcnow()

        log.info("Executing node: %s (worker: %s)", node.node_id, node.worker.name)

        worker_result: WorkerResult | None = None
        last_error = ""

        for attempt in range(node.retry_policy.max_retries + 1):
            try:
                if attempt > 0:
                    delay = node.retry_policy.delay_for_attempt(attempt - 1)
                    log.info("Retrying node %s (attempt %d, delay %.1fs)", node.node_id, attempt + 1, delay)
                    node.mark_retrying()
                    yield _sse({
                        "type": "agent_status",
                        "agent": node.worker.name.title(),
                        "state": "retrying",
                        "statusText": f"Retrying (attempt {attempt + 1})...",
                        "subText": f"Waiting {delay:.0f}s",
                    })
                    await asyncio.sleep(delay)
                    # Reload state in case it was updated
                    state = await self.state_manager.load_task(state.task_id)

                # Execute with timeout
                worker_result = await asyncio.wait_for(
                    node.worker.execute(state, self.tools),
                    timeout=node.timeout.total_seconds(),
                )

                if worker_result.success:
                    break  # success — exit retry loop
                else:
                    last_error = worker_result.error
                    log.warning(
                        "Node %s returned failure: %s",
                        node.node_id,
                        last_error[:200],
                    )

            except asyncio.TimeoutError:
                last_error = f"Timeout after {node.timeout.total_seconds():.0f}s"
                log.error("Node %s timed out", node.node_id)
            except Exception as e:
                last_error = str(e)
                log.exception("Node %s crashed: %s", node.node_id, e)

        duration_ms = int((time.monotonic() - start_time) * 1000)

        if worker_result and worker_result.success:
            # ── Success ──
            node.mark_completed(duration_ms)

            # Apply state updates
            # Apply state mutations and save with optimistic locking retry
            max_save_retries = 5
            for save_attempt in range(max_save_retries):
                try:
                    if save_attempt > 0:
                        state = await self.state_manager.load_task(state.task_id)

                    for key, value in worker_result.state_updates.items():
                        if key in ("findings", "evidence", "citations") and isinstance(value, list):
                            # Merge lists (parallel research nodes append)
                            existing = getattr(state, key, [])
                            setattr(state, key, existing + value)
                        elif key == "report_sections" and isinstance(value, dict):
                            # Merge dictionaries (parallel section writer nodes)
                            existing = getattr(state, key, {})
                            # Create a new dict to ensure Pydantic sees the mutation
                            new_dict = existing.copy()
                            new_dict.update(value)
                            setattr(state, key, new_dict)
                        else:
                            setattr(state, key, value)

                    # Record execution event
                    state.execution_log.append(ExecutionEvent(
                        event_type=EventType.NODE_COMPLETED,
                        node_id=node.node_id,
                        worker_name=node.worker.name,
                        duration_ms=duration_ms,
                        tokens_used=worker_result.tokens_used,
                    ))
                    state.node_statuses[node.node_id] = NodeStatus.COMPLETED.value

                    # Persist state
                    await self.state_manager.save_task(state)
                    break
                except RuntimeError as re:
                    if "Optimistic lock conflict" in str(re) and save_attempt < max_save_retries - 1:
                        await asyncio.sleep(random.uniform(0.05, 0.2))
                        continue
                    raise

            # Checkpoint
            if self.checkpoint_enabled:
                await self.state_manager.checkpoint(state, node.node_id)

            # Emit worker events
            for event in worker_result.events:
                yield _sse(event)

            # Record in execution history
            await self.state_manager.record_execution(
                task_id=state.task_id,
                node_id=node.node_id,
                worker_name=node.worker.name,
                status="completed",
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration_ms=duration_ms,
                tokens_used=worker_result.tokens_used,
                tool_calls=worker_result.tool_calls,
                retry_count=node.retry_count,
            )

        else:
            # ── Failure ──
            node.mark_failed(last_error)

            state.execution_log.append(ExecutionEvent(
                event_type=EventType.NODE_FAILED,
                node_id=node.node_id,
                worker_name=node.worker.name,
                duration_ms=duration_ms,
                message=last_error,
            ))
            state.error_log.append(ErrorEvent(
                node_id=node.node_id,
                worker_name=node.worker.name,
                error_type=type(Exception).__name__,
                error_message=last_error,
                retry_count=node.retry_count,
                recoverable=False,
            ))
            state.node_statuses[node.node_id] = NodeStatus.FAILED.value
            await self.state_manager.save_task(state)

            # Dead letter queue
            await self.state_manager.enqueue_dead_letter(
                task_id=state.task_id,
                node_id=node.node_id,
                worker_name=node.worker.name,
                error=last_error,
                state=state,
            )

            await self.state_manager.record_execution(
                task_id=state.task_id,
                node_id=node.node_id,
                worker_name=node.worker.name,
                status="failed",
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration_ms=duration_ms,
                error=last_error,
                retry_count=node.retry_count,
            )

            # Emit failure events
            if worker_result and worker_result.events:
                for event in worker_result.events:
                    yield _sse(event)

            yield _sse({
                "type": "agent_status",
                "agent": node.worker.name.title(),
                "state": "failed",
                "statusText": f"{node.worker.name} failed",
                "subText": last_error[:200],
            })

    async def _execute_parallel(
        self,
        nodes: list[GraphNode],
        state_task_id: str,
    ) -> AsyncGenerator[tuple[str, GraphNode | str], None]:
        """
        Execute multiple nodes in parallel using asyncio.Queue for real-time streaming.

        Yields tuples of ("event", sse_string) or ("done", node_object).
        """
        queue = asyncio.Queue()
        active_workers = len(nodes)

        async def run_one(node: GraphNode):
            try:
                # Reload state for each parallel worker to minimize race conditions
                state = await self.state_manager.load_task(state_task_id)
                async for event in self._execute_node(node, state):
                    await queue.put(("event", event))
            except Exception as e:
                node.mark_failed(str(e))
                await queue.put(("event", _sse({
                    "type": "agent_status",
                    "agent": node.worker.name.title(),
                    "state": "failed",
                    "statusText": f"{node.worker.name} crashed",
                    "subText": str(e)[:200],
                })))
            finally:
                await queue.put(("done", node))

        # Start concurrent tasks
        tasks = []
        for n in nodes:
            tasks.append(asyncio.create_task(run_one(n)))

        try:
            # Consume queue until all workers are done
            while active_workers > 0:
                msg_type, payload = await queue.get()
                if msg_type == "done":
                    active_workers -= 1
                    yield ("done", payload)
                else:
                    yield ("event", payload)
        finally:
            # Clean up tasks if the generator is closed early (e.g., client disconnect)
            for t in tasks:
                if not t.done():
                    t.cancel()
