# Concept

optagent is a foundation for preserving the process of optimization and problem-solving as a "readable-after-the-fact structure."

Rather than looking only at the final result, it leaves the following information within a run:

- What goal prompted the work
- What state was the starting point, and what was the intention
- What was predicted before execution
- What actually happened
- Which attempts or results were invalidated
- From which point alternative explorations began

## Core Idea

What optagent builds is an append-only history graph for the optimization process.

`RunGraph` is the DAG for the entire run. `Node` represents a state at a point in time. `InputTransition` represents "what to try from this state." `OutputTransition` represents "what result was reached from that attempt."

Meaningful information is not embedded directly in graph records but attached as payloads.

- `PlanPayload`: what was intended to be tried
- `PredictionPayload`: what was expected before execution
- `ResultPayload`: what actually happened
- `NotePayload`: memos about a state
- `CutPayload`: invalidation of mistaken attempts or results

This separation allows optagent to handle the structure of trial and error, not just logs.

## The Role of the CLI

The CLI is a thin interface for manipulating `RunGraph`.

`init` creates a run, `plan` adds the next attempt, `predict` leaves expected results, and `observe` saves measured results. `trace` and `show` are used to read back the preserved structure.

The basic flow is:

```text
init
  -> plan
  -> predict
  -> execute outside optagent
  -> observe
  -> trace / show
```

optagent does not perform optimization. It serves as a shareable state graph for the decisions and results made by external humans, LLMs, scripts, benchmark runners, and executors.

## What It Is Good For

optagent is suited for work where the intermediate process has value:

- Code optimization
- Kernel optimization
- Benchmark experiments
- Investigation and hypothesis verification
- Problem-solving loops where LLMs / scripts / executors are mixed in

It is especially valuable when multiple attempts share the same goal and predictions need to be matched against observations.

## What It Is Not

optagent is not, at this time:

- A general-purpose chatbot framework
- A LangChain-style general agent framework
- A code generator with built-in benchmarks
- An auto-optimization tool with a built-in executor
- A tool that automatically writes generated code back to source files

Execution, evaluation, code generation, and benchmarking are the responsibility of external systems. optagent's role is to structurally preserve the plans, predictions, and results they produce.
