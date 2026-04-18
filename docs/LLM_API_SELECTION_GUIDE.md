# LLM API Selection Guide: Named Provider Routes

## Overview

Aily now treats each provider as an explicit route.

Current production route:

1. **`zhipu`**: BigModel standard chat route at `https://open.bigmodel.cn/api/paas/v4`

Optional secondary family:

2. **Coding Plan** (fixed monthly): ByteDance Ark, Aliyun Bailian, Zhipu coding endpoints

If Aily supports another platform later, that platform should get its own dedicated route in code first. We should not hide providers behind a vague generic base URL.

## Current Lock

The live app is currently locked to **Zhipu BigModel** through:

- [`aily/llm/provider_routes.py`](/Users/luzi/code/aily/aily/llm/provider_routes.py)
- [`aily/config.py`](/Users/luzi/code/aily/aily/config.py)
- [`aily/main.py`](/Users/luzi/code/aily/aily/main.py)

That makes provenance explicit: when DIKIWI or the app-wide `llm_client` runs, it is using the Zhipu route unless we deliberately add and select another named provider route.

## BigModel Standard API

Official docs:

- Quick start: [https://docs.bigmodel.cn/cn/guide/start/quick-start](https://docs.bigmodel.cn/cn/guide/start/quick-start)
- Platform overview: [https://docs.bigmodel.cn/](https://docs.bigmodel.cn/)

The standard chat endpoint is:

`https://open.bigmodel.cn/api/paas/v4/chat/completions`

Authentication is:

- `Authorization: Bearer <API_KEY>`

This is the route Aily now uses for its primary LLM path.

## Quick Decision Matrix

| Factor | Standard API | Coding Plan |
|--------|--------------|-------------|
| **Pricing** | Per token (~¥0.01-0.03/1K tokens) | Fixed monthly (¥40-200) |
| **Best for** | Batch processing, data extraction | Interactive coding, real-time assistance |
| **Context length** | Up to 128k tokens | Varies by provider (usually 32k-128k) |
| **Rate limits** | Higher for batch processing | May limit non-interactive use |
| **API format** | OpenAI-compatible | Anthropic-compatible |

## When to Use Standard API (Kimi)

### Use for DIKIWI Data Processing

```python
from aily.llm.llm_router import LLMRouter, LLMConfig

config = LLMConfig(
    standard_api_key=os.environ["KIMI_API_KEY"],
    standard_model="kimi-k2.5",
)

# DATA stage: Extract facts from large content
llm = LLMRouter.for_task("data_extraction", config)

# INFORMATION stage: Classify and tag
llm = LLMRouter.for_task("classification", config)

# KNOWLEDGE stage: Determine relationships
llm = LLMRouter.for_task("relationship_detection", config)
```

**Why Standard API?**
- Batch processing 10 Monica conversations = ~500K tokens
- At ¥0.015/1K tokens = ¥7.5 total
- Coding Plan ¥40/month would be overkill

### Tasks Suited for Standard API

| Task | Tokens/Run | Cost (Standard) | Cost (Coding Plan) |
|------|------------|-----------------|-------------------|
| Extract data points from 1 URL | ~5K | ¥0.075 | Included in ¥40/mo |
| Batch process 100 messages | ~200K | ¥3 | Included in ¥40/mo |
| Daily DIKIWI pipeline | ~50K | ¥0.75 | Included in ¥40/mo |
| Classify information nodes | ~2K | ¥0.03 | Included in ¥40/mo |

**Break-even point**: If you process >2.6M tokens/month, Coding Plan is cheaper.

## When to Use Coding Plan

### Use for Interactive Development

```python
from aily.llm.llm_router import LLMRouter, LLMConfig

config = LLMConfig(
    coding_plan_api_key="sk-sp-xxxxx",  # Coding Plan key
    coding_plan_provider="ark",  # ByteDance Ark
    coding_plan_model="kimi-k2.5",
)

# Code generation and review
llm = LLMRouter.for_task("code_generation", config)

# Architecture discussions
llm = LLMRouter.for_task("architecture_design", config)

# Or get coding-optimized LLM directly
llm = LLMRouter.coding_plan_ark(
    api_key="sk-sp-xxxxx",
    model="kimi-k2.5"
)
```

**Why Coding Plan?**
- Fixed cost regardless of usage
- Optimized for Claude Code integration
- Better for iterative coding workflows

### Tasks Suited for Coding Plan

| Task | Interactive? | Best API |
|------|--------------|----------|
| Write new feature code | Yes | Coding Plan |
| Code review and refactor | Yes | Coding Plan |
| Debug errors interactively | Yes | Coding Plan |
| Generate unit tests | Batch | Standard API |
| Process user messages | Batch | Standard API |

## Provider Comparison

### ByteDance Ark (火山方舟)

```python
from aily.llm.llm_router import LLMRouter

client = LLMRouter.coding_plan_ark(
    api_key="sk-sp-xxxxx",
    model="kimi-k2.5"  # or "glm-4.7", "deepseek-v3.2"
)
```

**Pros:**
- Most model options (Kimi, GLM, DeepSeek, MiniMax, Doubao)
- Competitive pricing (Lite ¥40/mo, Pro ¥200/mo)
- Ark-code-latest for dynamic model switching

**Cons:**
- Requires Chinese phone number for signup
- Documentation primarily in Chinese

**Models Available:**
- `kimi-k2.5` - Best overall performance
- `glm-4.7` - Strong reasoning
- `deepseek-v3.2` - Good for coding
- `doubao-seed-2.0-code` - Code-optimized

### Aliyun Bailian (百炼)

```python
from aily.llm.llm_router import LLMRouter

client = LLMRouter.coding_plan_bailian(
    api_key="sk-sp-xxxxx",
    model="qwen3.5-plus"  # or "kimi-k2.5"
)
```

**Pros:**
- Qwen models excel at Chinese
- Image understanding support
- Well-integrated with Alibaba Cloud

**Cons:**
- Lite plan often sold out (9:30 AM daily restock)
- Fewer model options than Ark

**Models Available:**
- `qwen3.5-plus` - Best for Chinese, image understanding
- `kimi-k2.5` - Same as Ark
- `glm-5` - GLM's latest

### Zhipu AI (智谱)

```python
from aily.llm.llm_router import LLMRouter

client = LLMRouter.coding_plan_zhipu(
    api_key="your-zhipu-key",
    model="glm-4.7"
)
```

**Pros:**
- GLM models strong in Chinese
- Also offers OpenAI-compatible endpoint
- Good academic background

**Cons:**
- Smaller ecosystem
- Fewer integrations

## Configuration Examples

### Scenario 1: Heavy Batch Processing

You process 1000+ messages daily through DIKIWI.

```python
# config.py
LLM_CONFIG = LLMConfig(
    # Standard API for all DIKIWI processing
    standard_api_key=os.environ["KIMI_API_KEY"],
    standard_model="kimi-k2.5",  # 256k context for large conversations

    # No Coding Plan needed
    coding_plan_api_key="",
)

# Estimated cost: ~¥30-50/month for 2M tokens/day
```

### Scenario 2: Mixed Use

You do both DIKIWI processing and interactive coding.

```python
# config.py
LLM_CONFIG = LLMConfig(
    # Standard API for DIKIWI
    standard_api_key=os.environ["KIMI_API_KEY"],
    standard_model="kimi-k2.5",

    # Coding Plan for Claude Code integration
    coding_plan_api_key="sk-sp-xxxxx",
    coding_plan_provider="ark",
    coding_plan_model="kimi-k2.5",
)

# DIKIWI uses Standard API automatically
from aily.llm.llm_router import get_llm_for_data_extraction
llm = get_llm_for_data_extraction(LLM_CONFIG)

# Coding tasks use Coding Plan automatically
from aily.llm.llm_router import get_llm_for_coding
llm = get_llm_for_coding(LLM_CONFIG)
```

### Scenario 3: Interactive-Only

You primarily use Claude Code for development.

```python
# config.py
LLM_CONFIG = LLMConfig(
    # No Standard API
    standard_api_key="",

    # Coding Plan for everything
    coding_plan_api_key="sk-sp-xxxxx",
    coding_plan_provider="ark",
    coding_plan_model="kimi-k2.5",
)

# Force DIKIWI to use Coding Plan
from aily.llm.llm_router import LLMRouter
mind = LLMRouter.create_dikiwi_mind(
    config=LLM_CONFIG,
    graph_db=graph_db,
    use_coding_plan=True,
)
```

## Claude Code Configuration

To use Coding Plan with Claude Code CLI:

### ByteDance Ark

```bash
# ~/.claude/settings.json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "sk-sp-xxxxx",
    "ANTHROPIC_BASE_URL": "https://ark.cn-beijing.volces.com/api/coding",
    "ANTHROPIC_MODEL": "kimi-k2.5"
  }
}
```

### Aliyun Bailian

```bash
# ~/.claude/settings.json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "sk-sp-xxxxx",
    "ANTHROPIC_BASE_URL": "https://coding.dashscope.aliyuncs.com/apps/anthropic",
    "ANTHROPIC_MODEL": "qwen3.5-plus"
  }
}
```

```bash
# ~/.claude.json
{
  "hasCompletedOnboarding": true
}
```

## Migration Guide

### From Standard API to Coding Plan

1. **Sign up** for Coding Plan (Ark or Bailian)
2. **Get API key** (format: `sk-sp-xxxxx`)
3. **Update config**:
   ```python
   LLM_CONFIG.coding_plan_api_key = "sk-sp-xxxxx"
   LLM_CONFIG.coding_plan_provider = "ark"
   ```
4. **Route specific tasks**:
   ```python
   # Coding tasks use Coding Plan
   if task_type in ["code_generation", "code_review"]:
       llm = LLMRouter.coding_plan_ark(...)
   else:
       llm = LLMRouter.standard_kimi(...)
   ```

### From Coding Plan to Standard API

If you hit rate limits on Coding Plan:

```python
# Fallback to Standard API
if config.standard_api_key:
    llm = LLMRouter.standard_kimi(
        api_key=config.standard_api_key
    )
else:
    llm = LLMRouter.coding_plan_ark(...)
```

## Cost Analysis

### Break-Even Calculation

**Coding Plan Lite**: ¥40/month (~$5.50)
**Standard API**: ~¥0.015/1K tokens (Kimi 32k)

Break-even: 40 / 0.015 * 1000 = **2.67M tokens/month**

| Monthly Usage | Standard API | Coding Plan | Winner |
|---------------|--------------|-------------|--------|
| 1M tokens | ¥15 | ¥40 | Standard |
| 2M tokens | ¥30 | ¥40 | Standard |
| 3M tokens | ¥45 | ¥40 | Coding Plan |
| 5M tokens | ¥75 | ¥40 | Coding Plan |

### Real-World Example

**Daily DIKIWI processing**:
- 50 messages/day
- Average 10K tokens/message (full Monica conversations)
- 500K tokens/day
- 15M tokens/month

**Standard API**: 15M * ¥0.015/1K = **¥225/month**
**Coding Plan Pro**: **¥200/month**

→ Coding Plan saves ¥25/month in this scenario

## Recommendations

### For DIKIWI-Only Users

Use **Standard API** (Kimi) unless you process >2.5M tokens/month.

```python
config = LLMConfig(
    standard_api_key="your-key",
    standard_model="moonshot-v1-32k",
)
```

### For Mixed Users

Configure both and let the router decide:

```python
config = LLMConfig(
    standard_api_key="sk-...",
    coding_plan_api_key="sk-sp-...",
    coding_plan_provider="ark",
)

# Auto-routing
llm = LLMRouter.for_task("data_extraction", config)  # → Standard
llm = LLMRouter.for_task("code_generation", config)   # → Coding Plan
```

### For Heavy Coders

Use **Coding Plan** with Claude Code:

```bash
export ANTHROPIC_AUTH_TOKEN="sk-sp-xxxxx"
export ANTHROPIC_BASE_URL="https://ark.cn-beijing.volces.com/api/coding"
claude
```

## Summary

| You Should Use | If |
|----------------|-----|
| **Standard API** | Processing >100 messages/day, batch operations, cost-conscious at lower volumes |
| **Coding Plan** | Interactive coding with Claude Code, >3M tokens/month, want predictable costs |
| **Both** | Mixed workloads, want optimization per task type |
