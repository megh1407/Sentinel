"""
wire_format.py

Implements the Confluent wire format that every message on a SENTINEL Kafka
topic actually uses: a 1-byte magic byte (0x0), a 4-byte big-endian schema
ID, followed by the Avro binary payload. This is the format
sentinel_eventbus's EventProducer/EventConsumer (Phase 1 Core Runtime Spec,
Part 4) read and write -- this module is their shared low-level codec, kept
separate so it can be tested in complete isolation from any Kafka client.
"""
from __future__ import annotations

import io
import struct
from typing import TypeVar

from fastavro import schemaless_reader, schemaless_writer
from pydantic import BaseModel

MAGIC_BYTE = b"\x00"
T = TypeVar("T", bound=BaseModel)


def encode(model_instance: BaseModel, avro_schema: dict, schema_id: int) -> bytes:
    """Serializes a Pydantic model instance to Confluent wire format bytes,
    ready to hand directly to a Kafka producer as the message value.

    model_instance.model_dump(mode="json") produces JSON-safe primitives
    (UUID -> str, datetime -> ISO string) which fastavro's Avro writer does
    NOT accept for logicalType uuid/timestamp-millis fields (it wants native
    uuid.UUID / datetime.datetime objects) -- so this function uses
    model_dump(mode="python") instead, which preserves those native types.
    """
    raw = model_instance.model_dump(mode="python")
    buf = io.BytesIO()
    buf.write(MAGIC_BYTE)
    buf.write(struct.pack(">I", schema_id))
    schemaless_writer(buf, avro_schema, raw)
    return buf.getvalue()


def decode(payload: bytes, model_cls: type[T], writer_schema: dict, reader_schema: dict | None = None) -> tuple[T, int]:
    """Deserializes Confluent wire-format bytes into a validated Pydantic
    model instance. Returns (instance, embedded_schema_id) so the caller
    (EventConsumer) can cross-check the embedded schema_id against what it
    expects, and raise a ValidationError (fatal, per sentinel_common.errors)
    on a mismatch rather than silently trusting the byte stream.

    If `reader_schema` is provided and differs from `writer_schema` (i.e.
    the message was produced by an older/newer producer than this consumer
    is running), Avro's schema resolution (Part 5/Part 7 of the contract
    spec) is applied automatically -- this is what makes multi-version
    coexistence during a rolling deploy actually work at the byte level,
    not just in theory.
    """
    if payload[:1] != MAGIC_BYTE:
        raise ValueError(
            f"payload does not start with the Confluent magic byte (0x00) -- "
            f"got {payload[:1]!r}. This is not a validly-framed SENTINEL event."
        )
    schema_id = struct.unpack(">I", payload[1:5])[0]
    body = io.BytesIO(payload[5:])
    record = schemaless_reader(body, writer_schema, reader_schema)
    instance = model_cls.model_validate(record)
    return instance, schema_id
