# State Management

## Purpose

Maintain derived system state across pipeline runs.

## Components

### Portfolio

* Calculate current value and P&L
* Track allocation and exposure

### Signal Tracker

* Record signals per ticker
* Update 1D / 5D / 20D performance
* Maintain historical accuracy

## Rules

* State must be derived, not arbitrary
* Must be reproducible from inputs
* Must not depend on external APIs

## Constraints

* No business logic leakage to other layers
* No formatting logic
