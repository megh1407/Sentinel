"""Wire-format request contracts.

Empty in this phase by design: this phase implements the domain layer's
own internal `domain/commands` contracts only. Wire-format request DTOs
(mapping raw Kafka bytes to `domain/events` objects) belong to the `dto/`
layer specified in Phase 3.1 §2 and are populated in a later
implementation phase, once `handlers/consumers.py` exists to use them.
"""
