# OpenHands (OpenDevin): AgentNexus Integration Guide

This guide covers configuring **OpenHands** (open-source autonomous coding worker) to run **AgentNexus** missions using repository microagents.

---

## 1. OpenHands Microagents (`.openhands/microagents/`)

OpenHands automatically loads repository instructions and specialized trigger microagents from `.openhands/microagents/`.

Install the AgentNexus microagent:
```bash
mkdir -p .openhands/microagents
cp implementing/openhands/microagent_nexus.md .openhands/microagents/repo.md
```

---

## 2. Running OpenHands with Free Models

Launch OpenHands via Docker pointed at your local repository and a free LLM API (e.g. Gemini 2.0 Flash or DeepSeek):

```bash
docker run -it --rm --pull=always \
  -e SANDBOX_RUNTIME_CONTAINER_IMAGE=docker.all-hands.dev/all-hands-ai/runtime:0.28-nikolaik \
  -e WORKSPACE_MOUNT_PATH=$(pwd) \
  -v $(pwd):/opt/workspace_base \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -p 3000:3000 \
  docker.all-hands.dev/all-hands-ai/openhands:0.28
```
Configure `gemini/gemini-2.0-flash` in the OpenHands settings UI with your free Google AI Studio key.
