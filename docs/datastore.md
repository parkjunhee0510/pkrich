# Datastore

## Purpose

Provide storage abstraction for structured data.

## Backends

### CSV

* Default backend
* Simple and transparent

### SQLite

* Optional backend
* Supports advanced queries

## Selection

* Controlled via environment variable

## Rules

* All storage must go through abstraction layer
* No direct file access outside datastore

## Constraints

* Must remain interchangeable
* Must not affect business logic
