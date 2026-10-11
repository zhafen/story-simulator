# Literature review: LLM-engine simulators

First pass (2026-10). Based on search summaries and abstracts, not full texts.
Figures should be re-checked before anyone relies on them.

## 1. Current status of event-based simulations

- **Classic discrete-event simulation (DES) is mature and stable.**
  SimPy is the default choice in Python; commercial tools include FlexSim
  and SimEvents.
  - [Wikipedia: list of DES software](https://en.wikipedia.org/wiki/List_of_discrete_event_simulation_software)
  - [Intro to DES with SimPy (arXiv:2405.01562)](https://arxiv.org/pdf/2405.01562)
  - SerializableSimpy keeps SimPy's API but adds checkpoint/restart and
    parallel runs, which comes close to the "pause, persist, resume"
    pattern story-sim needs. [JOSS paper](https://joss.theoj.org/papers/10.21105/joss.08502.pdf)
- **LLMs are being used to *write* DES models, not to *run* them.**
  - [SimLLM (arXiv:2601.06543)](https://arxiv.org/html/2601.06543)
  - [Image → verifiable queueing model (arXiv:2607.24259)](https://arxiv.org/pdf/2607.24259)
  - [llm_simpy (code)](https://github.com/pythonhealthdatascience/llm_simpy)
- **LLM agent simulations mostly use fixed time steps.** Event-driven or
  out-of-order scheduling shows up mainly as a way to cut the number of
  LLM calls and run them in parallel.
  - AI Metropolis tracks the real dependencies between agents and gets
    1.3–4.15× speedups. [MLSys 2025](https://proceedings.mlsys.org/paper_files/paper/2025/file/4f31327e046913c7238d5b671f5d820e-Paper-Conference.pdf)
  - MobileCity gives each agent its own clock and batches LLM calls.
    [arXiv:2504.16946](https://arxiv.org/pdf/2504.16946)
  - [Scheduler-theoretic framework for agent execution (arXiv:2604.11378)](https://arxiv.org/html/2604.11378v1)
  - [AsyncLLM (arXiv:2609.35427)](https://arxiv.org/html/2609.35427v1)
- **Correction to an earlier claim:** Concordia's main branch (code
  newer than its 2.4.0 release) has an interrupt-driven Game Master (GM).
  It keeps a sorted queue of timestamped events and timers, and each entity
  filters which events reach it with an interrupt mask
  (`components/game_master/interrupt_scheduling.py`,
  `interrupt_time_model.py`). That is an event queue with LLM resolution,
  close to story-sim's `pop_event` → resolve → plan loop. So the pattern
  isn't unique to story-sim, but it is still very new.

## 2. Using LLMs to predict outcomes

- **Forecasting real-world events: roughly at superforecaster level now.**
  - ForecastBench originally showed a gap (Brier score 0.096 for
    superforecasters vs. 0.122 for the best LLM).
    [ForecastBench (arXiv:2409.19839)](https://www.alphaxiv.org/abs/2409.19839)
  - The Forecasting Research Institute now reports statistical parity on
    its July 2026 leaderboard, though that relies on extrapolating from
    2024 human forecasts.
    [FRI post](https://forecastingresearch.substack.com/p/ai-models-have-likely-reached-parity)
  - [AIA Forecaster (arXiv:2511.07678)](https://arxiv.org/pdf/2511.07678)
  - [LLMs vs. expert forecasters (arXiv:2507.04562)](https://arxiv.org/pdf/2507.04562)
  - Agents still don't beat markets: none of four beat the bookmaker on
    World Cup matches. [arXiv:2607.17765](https://arxiv.org/pdf/2607.17765)
  - Methods survey: [arXiv:2608.23058](https://arxiv.org/pdf/2608.23058)
- **Predicting experiment and survey results ("silicon samples").**
  - LLMs do well on *aggregate* effects: Hewitt et al. report r≈0.91
    against the real treatment effects of 70 pre-registered experiments.
  - They do poorly on *individuals* and identity-sensitive subgroups, and
    are sensitive to how the prompt is worded.
    - [Evaluating silicon sampling](https://openaccess.cms-conferences.org/publications/book/978-1-964867-73-1/article/978-1-964867-73-1_45)
    - [Silicon sampling via cross-survey transfer (arXiv:2607.03091)](https://arxiv.org/pdf/2607.03091)
    - [Identifying non-replicable studies (arXiv:2503.10671)](https://arxiv.org/pdf/2503.10671)
    - [Evaluating LLMs as survey respondents (arXiv:2509.26080)](https://arxiv.org/pdf/2509.26080)
- **LLMs as world simulators: unreliable step by step, and errors
  compound.**
  - GPT-4 gets 59.9% of non-trivial text-game state transitions right, and
    only 49.7% of the changes the environment itself drives.
    [ACL 2024](https://aclanthology.org/2024.acl-short.1/)
  - RLVR-World trains models on this task with reinforcement learning.
    [arXiv:2505.13934](https://arxiv.org/pdf/2505.13934)
  - LLMs struggle to simulate how people update their beliefs.
    [arXiv:2607.28347](https://arxiv.org/pdf/2607.28347)
- **Policy, crisis and wargame simulation: rich behavior, but not
  validated.**
  - LLMs escalate even in neutral scenarios.
    [arXiv:2401.03408](https://arxiv.org/pdf/2401.03408)
  - Compared with 214 human experts, LLM teams play differently.
    [arXiv:2403.03407](https://arxiv.org/pdf/2403.03407)
  - Frontier models attempt deception in a simulated nuclear crisis.
    [arXiv:2602.14740](https://arxiv.org/pdf/2602.14740)
  - No LLM wargame should inform policy without an auditable safety case.
    [arXiv:2609.16189](https://arxiv.org/pdf/2609.16189)
  - Robustness audits are needed before drawing scientific claims from
    LLM social simulations.
    [arXiv:2605.18890](https://arxiv.org/pdf/2605.18890)
- **Takeaway for policy_sim:** treat LLM outputs as plausible scenarios,
  not predictions. Report results across many runs and prompt variations,
  and check them against the real outcomes of past policies wherever
  possible.

## 3. Simulations that use LLMs as an engine

| System | What it is | Code / paper |
|---|---|---|
| Concordia (DeepMind) | Generative agent-based models (ABMs) built from **entities and components**, with a tabletop-style Game Master that resolves actions. Apache-2.0, ~1.8k stars. Closest to story-sim in concept. | [code](https://github.com/google-deepmind/concordia), arXiv:2312.03664, game-engine follow-up arXiv:2507.08892 |
| TinyTroupe (Microsoft) | Simulates personas for business and market insight. ~7.5k stars. | [code](https://github.com/microsoft/TinyTroupe) |
| AgentSociety (Tsinghua) | Large-scale urban and social simulation for social-science research. ~1.3k stars. | [code](https://github.com/tsinghua-fib-lab/agentsociety/), arXiv:2502.08691 |
| OASIS (CAMEL-AI) | Social media simulation with up to 1M agents. | [fork](https://github.com/nikolaef43/oasis) (official repo: camel-ai/oasis) |
| YuLan-OneSim | Builds scenarios from natural language; runs distributed. | [arXiv:2505.07581](https://arxiv.org/abs/2505.07581) |
| EconAgent | LLM agents simulate macroeconomies to test policies (ACL 2024). | [arXiv:2310.10436](https://arxiv.org/pdf/2310.10436) |
| EconSimulacra, Eco3S, EconGym | Testbeds and digital twins of socio-economic systems. | [2606.26883](https://arxiv.org/pdf/2606.26883), [2607.26588](https://arxiv.org/pdf/2607.26588), [2506.12110](https://arxiv.org/pdf/2506.12110) |
| GenWorld | Empirically grounded urban simulation infrastructure. | [arXiv:2606.27650](https://arxiv.org/pdf/2606.27650) |
| LLM wargaming | Wargame harness. | [code](https://github.com/ancorso/LLMWargaming) |
| Game-master work | Proposes a canonical, validated world object owned by a GM agent (closest in argument to story-sim + emc2p). Separate work compares static vs. agentic GMs, including an "Archivist" agent that records state changes. | Orchestrated Reality [arXiv:2606.16014](https://arxiv.org/pdf/2606.16014); [arXiv:2502.19519](https://arxiv.org/pdf/2502.19519); [RPGGO text-to-game engine](https://arxiv.org/pdf/2407.08195) |

Surveys and method papers:
- [LLMs in agent-based social simulation (arXiv:2507.19364)](https://arxiv.org/pdf/2507.19364)
- [LLMs and games survey (arXiv:2402.18659)](https://arxiv.org/pdf/2402.18659)
- [EASE: reproducible LLM social simulations (arXiv:2605.30258)](https://arxiv.org/pdf/2605.30258)

**Takeaway for the decision:** several mature, permissively licensed
frameworks already exist. Concordia in particular overlaps with ideas in
story-sim and emc2p: entities and components, and a Game Master that
resolves actions. What story-sim adds that I didn't find elsewhere:
- world state that persists in a database, with full history
- an MCP tool surface, so any connected agent can act as the engine

Any option we're weighing should be compared against "build on
Concordia" as a baseline.
