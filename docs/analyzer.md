# Analyzer

## Purpose

Transform structured data into research insights using LLMs.

## Input

* Must be normalized and structured
* No raw or inconsistent data

## Prompt Design

* Deterministic
* Concise
* Cost-aware

## Output

* Strict structured schema
* Markdown-ready

## Architecture

### Provider Isolation

* Model-specific logic must be isolated
* Easy provider switching

### Batching

* Support multi-ticker processing
* Dynamic batch sizing

## Fallback

* Deterministic fallback required
* Must produce valid structured output
* Must not break downstream pipeline

## Rules

* No external API calls
* No formatting logic
* No side effects
