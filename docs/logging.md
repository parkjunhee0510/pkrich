# Logging

## Purpose

Track pipeline execution and diagnose failures.

## Components

### Event Stream

* JSONL format
* Step-by-step events

### Summary

* Aggregated statistics
* Error and warning counts

## Requirements

* Must record all critical events
* Must not expose secrets

## Rules

* Logging must not affect pipeline flow
* Logging failures must not break execution
