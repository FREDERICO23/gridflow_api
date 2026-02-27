"""Celery task definitions.

The full processing pipeline tasks will be implemented in Phase 3
(File Ingestion & Processing Pipeline).

Pipeline stages per task:
  queued → parsing → normalising → enriching → quality_check → forecasting → complete
"""
