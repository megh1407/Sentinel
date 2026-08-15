"""
postgres_repositories.py

Real SQLAlchemy 2.x repositories, tested against an actual live Postgres
instance (this environment's local postgresql service). Implements the
transaction-context-manager pattern and connection pooling from the Phase 1
Core Runtime spec Part 5.2.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from sentinel_common.errors import StateError


class Base(DeclarativeBase):
    pass


class HelloSeenRecord(Base):
    """The trivial table backing HelloAgent's Postgres-side proof (in
    addition to the Redis-side proof) -- deliberately minimal, but a real
    table with a real primary key and a real unique constraint."""
    __tablename__ = "hello_seen_events"
    __table_args__ = {"schema": "hello_agent"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, unique=True, nullable=False)
    seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)


def build_engine(dsn: str, pool_size: int = 5, max_overflow: int = 10):
    return create_engine(dsn, pool_size=pool_size, max_overflow=max_overflow, pool_pre_ping=True)


def build_session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


class PostgresRepository:
    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            raise StateError(f"Postgres transaction failed: {e}") from e
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


class HelloSeenRepository(PostgresRepository):
    def ensure_schema(self) -> None:
        """Creates the hello_agent schema/table if they don't exist. In a
        real deployment this would be an Alembic migration
        (Phase 1 Core Runtime spec Part 5.2); done inline here for a
        minimal, dependency-free proof."""
        with self.transaction() as session:
            session.execute(text("CREATE SCHEMA IF NOT EXISTS hello_agent"))
        # Scoped to this repo's own table -- Base is shared across repositories
        # (ZoneRepository etc.), so an unscoped create_all() would also try to
        # create zone_intelligence's tables/schema, which this repo shouldn't do.
        Base.metadata.create_all(self._session_factory.kw["bind"], tables=[HelloSeenRecord.__table__])

    def mark_seen(self, event_id: str) -> None:
        with self.transaction() as session:
            existing = session.query(HelloSeenRecord).filter_by(event_id=event_id).first()
            if existing is None:
                session.add(HelloSeenRecord(event_id=event_id, seen_at=datetime.now(timezone.utc)))
            # idempotent: re-marking an already-seen event_id is a safe no-op

    def count_seen(self) -> int:
        with self.transaction() as session:
            return session.query(HelloSeenRecord).count()

    def was_seen(self, event_id: str) -> bool:
        with self.transaction() as session:
            return session.query(HelloSeenRecord).filter_by(event_id=event_id).first() is not None


class ZoneHistoryRecord(Base):
    """One row per ZoneState publish -- durable history beyond Redis's TTL
    (spec Part 7's zone_history table). Redis stays the fast live-read
    path; this is the audit trail Redis was never meant to keep forever."""
    __tablename__ = "zone_history"
    __table_args__ = {"schema": "zone_intelligence"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_state_event_id = Column(String, unique=True, nullable=False)
    zone_id = Column(String, nullable=False, index=True)
    site_id = Column(String, nullable=False)
    occupancy_count = Column(Integer, nullable=False)
    current_risk_level = Column(String, nullable=False)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AnomalyRecord(Base):
    """One row per ZoneAnomalyDetected publish (spec Part 7's anomalies
    table) -- durable beyond Redis, and queryable by zone/type/severity in
    a way a Redis sorted set never could be."""
    __tablename__ = "anomalies"
    __table_args__ = {"schema": "zone_intelligence"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    anomaly_event_id = Column(String, unique=True, nullable=False)
    zone_id = Column(String, nullable=False, index=True)
    anomaly_type = Column(String, nullable=False, index=True)
    severity = Column(String, nullable=False)
    rule_id = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    summary = Column(String, nullable=True)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AuditEventRecord(Base):
    """One row per processed input event (spec Part 7's audit_events table)
    -- the "what did we receive and what did it cause" trail, independent
    of whether that event produced an anomaly."""
    __tablename__ = "audit_events"
    __table_args__ = {"schema": "zone_intelligence"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_event_id = Column(String, unique=True, nullable=False)
    source_event_type = Column(String, nullable=False)
    zone_id = Column(String, nullable=True, index=True)
    correlation_id = Column(String, nullable=False)
    causation_id = Column(String, nullable=True)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ZoneRepository(PostgresRepository):
    """Postgres-backed durability for Zone Intelligence Agent (spec Part 7 +
    the ZoneRepository box in Part 17's class diagram). Redis
    (ZoneStateRepository et al, in redis_repositories.py) remains the fast
    live-read path with a TTL; this is what survives past that TTL and
    supports queries Redis can't do (by zone over time, by anomaly type,
    audit trail). Real SQLAlchemy 2.x, tested against a live local Postgres
    -- same proof standard as HelloSeenRepository."""

    def ensure_schema(self) -> None:
        with self.transaction() as session:
            session.execute(text("CREATE SCHEMA IF NOT EXISTS zone_intelligence"))
        # Scoped to this repo's own tables -- Base is shared across repositories
        # (HelloSeenRepository etc.), so an unscoped create_all() would also try
        # to create hello_agent's table/schema, which this repo has no business doing.
        Base.metadata.create_all(
            self._session_factory.kw["bind"],
            tables=[ZoneHistoryRecord.__table__, AnomalyRecord.__table__, AuditEventRecord.__table__],
        )

    def record_zone_state(self, zone_state_event_id: str, zone_id: str, site_id: str,
                           occupancy_count: int, current_risk_level: str) -> None:
        with self.transaction() as session:
            existing = session.query(ZoneHistoryRecord).filter_by(zone_state_event_id=zone_state_event_id).first()
            if existing is None:  # idempotent on the ZoneState's own event_id
                session.add(ZoneHistoryRecord(
                    zone_state_event_id=zone_state_event_id, zone_id=zone_id, site_id=site_id,
                    occupancy_count=occupancy_count, current_risk_level=current_risk_level,
                    recorded_at=datetime.now(timezone.utc),
                ))

    def record_anomaly(self, anomaly_event_id: str, zone_id: str, anomaly_type: str, severity: str,
                        rule_id: str | None, confidence: float | None, summary: str | None) -> None:
        with self.transaction() as session:
            existing = session.query(AnomalyRecord).filter_by(anomaly_event_id=anomaly_event_id).first()
            if existing is None:
                session.add(AnomalyRecord(
                    anomaly_event_id=anomaly_event_id, zone_id=zone_id, anomaly_type=anomaly_type,
                    severity=severity, rule_id=rule_id, confidence=confidence, summary=summary,
                    recorded_at=datetime.now(timezone.utc),
                ))

    def record_audit_event(self, source_event_id: str, source_event_type: str, zone_id: str | None,
                            correlation_id: str, causation_id: str | None) -> None:
        with self.transaction() as session:
            existing = session.query(AuditEventRecord).filter_by(source_event_id=source_event_id).first()
            if existing is None:
                session.add(AuditEventRecord(
                    source_event_id=source_event_id, source_event_type=source_event_type, zone_id=zone_id,
                    correlation_id=correlation_id, causation_id=causation_id,
                    recorded_at=datetime.now(timezone.utc),
                ))

    def count_anomalies_by_type(self, zone_id: str, anomaly_type: str) -> int:
        with self.transaction() as session:
            return session.query(AnomalyRecord).filter_by(zone_id=zone_id, anomaly_type=anomaly_type).count()

    def get_zone_history(self, zone_id: str, limit: int = 100) -> list[ZoneHistoryRecord]:
        with self.transaction() as session:
            return (session.query(ZoneHistoryRecord).filter_by(zone_id=zone_id)
                    .order_by(ZoneHistoryRecord.recorded_at.desc()).limit(limit).all())


class RiskAssessmentRecord(Base):
    """One row per finalized SystemRiskAssessment -- the durable audit trail
    behind the dashboard's History page. Redis (state_cache.py /
    CachingEventPublisher) stays the fast live-read path with no retention
    guarantee across restarts/resets; this is what survives it."""
    __tablename__ = "risk_assessments"
    __table_args__ = {"schema": "risk_orchestrator"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(String, unique=True, nullable=False)
    zone_id = Column(String, nullable=False, index=True)
    site_id = Column(String, nullable=True)
    global_score = Column(Float, nullable=False)
    severity = Column(String, nullable=False, index=True)
    decision_category = Column(String, nullable=False)
    escalation_required = Column(String, nullable=False)
    manual_review_required = Column(String, nullable=False)
    explanation = Column(String, nullable=True)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ActionRequestRecord(Base):
    """One row per ResponseAgent decision -- the Response Agent's half of
    the same audit trail, keyed to the RiskAssessmentRecord that caused it
    via assessment_id (Kafka's causation_id, not a DB foreign key, since
    the two are written from two independent in-process callbacks)."""
    __tablename__ = "action_requests"
    __table_args__ = {"schema": "risk_orchestrator"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_id = Column(String, unique=True, nullable=False)
    assessment_id = Column(String, nullable=False, index=True)
    zone_id = Column(String, nullable=False, index=True)
    action_type = Column(String, nullable=False)
    urgency = Column(String, nullable=False)
    classification = Column(String, nullable=False)
    explanation = Column(String, nullable=True)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class HistoryRepository(PostgresRepository):
    """Postgres-backed durability for the Risk Orchestrator + Response
    Agent's decisions, feeding the dashboard's History page with real,
    persisted records rather than fabricated fixtures."""

    def ensure_schema(self) -> None:
        with self.transaction() as session:
            session.execute(text("CREATE SCHEMA IF NOT EXISTS risk_orchestrator"))
        Base.metadata.create_all(
            self._session_factory.kw["bind"],
            tables=[RiskAssessmentRecord.__table__, ActionRequestRecord.__table__],
        )

    def record_risk_assessment(self, assessment_id: str, zone_id: str, site_id: str | None,
                                global_score: float, severity: str, decision_category: str,
                                escalation_required: bool, manual_review_required: bool,
                                explanation: str | None) -> None:
        with self.transaction() as session:
            existing = session.query(RiskAssessmentRecord).filter_by(assessment_id=assessment_id).first()
            if existing is None:  # idempotent -- same assessment_id can arrive more than once
                session.add(RiskAssessmentRecord(
                    assessment_id=assessment_id, zone_id=zone_id, site_id=site_id,
                    global_score=global_score, severity=severity, decision_category=decision_category,
                    escalation_required=str(escalation_required), manual_review_required=str(manual_review_required),
                    explanation=explanation, recorded_at=datetime.now(timezone.utc),
                ))

    def record_action_request(self, action_id: str, assessment_id: str, zone_id: str,
                               action_type: str, urgency: str, classification: str,
                               explanation: str | None) -> None:
        with self.transaction() as session:
            existing = session.query(ActionRequestRecord).filter_by(action_id=action_id).first()
            if existing is None:
                session.add(ActionRequestRecord(
                    action_id=action_id, assessment_id=assessment_id, zone_id=zone_id,
                    action_type=action_type, urgency=urgency, classification=classification,
                    explanation=explanation, recorded_at=datetime.now(timezone.utc),
                ))

    def get_history(self, limit: int = 100) -> list[dict]:
        """Assessments joined (in Python, not SQL -- two independent write
        paths as noted above) with their resulting action, newest first."""
        with self.transaction() as session:
            assessments = (session.query(RiskAssessmentRecord)
                            .order_by(RiskAssessmentRecord.recorded_at.desc()).limit(limit).all())
            results = []
            for a in assessments:
                action = (session.query(ActionRequestRecord)
                          .filter_by(assessment_id=a.assessment_id).first())
                results.append({
                    "assessment_id": a.assessment_id,
                    "zone_id": a.zone_id,
                    "site_id": a.site_id,
                    "global_score": a.global_score,
                    "severity": a.severity,
                    "decision_category": a.decision_category,
                    "escalation_required": a.escalation_required == "True",
                    "manual_review_required": a.manual_review_required == "True",
                    "explanation": a.explanation,
                    "recorded_at": a.recorded_at.isoformat(),
                    "action": None if action is None else {
                        "action_id": action.action_id,
                        "action_type": action.action_type,
                        "urgency": action.urgency,
                        "classification": action.classification,
                        "explanation": action.explanation,
                    },
                })
            return results
